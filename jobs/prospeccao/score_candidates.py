"""Score prospection feature snapshots with the active ranker."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import FeatureSnapshotProspeccao, ModeloProspeccao, ScoreProspeccao
from jobs.prospeccao import config
from jobs.prospeccao.ranker_contract import FEATURE_NAMES, heuristic_score

logger = logging.getLogger(__name__)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _build_enriched_motivos(
    features: dict[str, float],
    shap_vals: dict[str, float] | None,
    feature_names: list[str],
) -> list[dict[str, Any]]:
    """Build enriched reasons with SHAP context and human-readable labels.

    Returns list of dicts with feature, reason, value, and optional shap score.
    Prioritizes SHAP values when available, falls back to raw feature values.
    """
    feature_labels = {
        "cnae_ree_fit": "CNAE principal alinhado com REE",
        "cnae_secondary_max_fit": "CNAEs secundários com fit REE",
        "cnae_secondary_hit_count": "Múltiplos CNAEs secundários em REE",
        "porte_ordinal": "Porte da empresa compatível",
        "active_status": "Empresa ativa na Receita",
        "contact_richness": "Contatos disponíveis (email/telefone)",
        "data_completeness": "Perfil de dados enriquecido",
        "address_quality": "Qualidade do endereço",
        "logistics_proximity_exp": "Proximidade logística da sede",
        "age_years_log": "Histórico de operação estabelecido",
        "public_proxy_fit": "Indicador de consumidor público",
        "is_df_proper": "Localizado no DF",
        "is_entorno_inner": "Entorno próximo (< 60km)",
        "neighborhood_candidate_density": "Área com concentração de candidatos",
        "neighborhood_ree_ratio": "Região com alta concentração REE",
        "has_geocode": "Coordenadas geocodificadas disponíveis",
    }

    motivos = []

    if shap_vals:
        # Ranked by absolute SHAP contribution (top 5)
        ranked = sorted(shap_vals.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        for feat, shap_val in ranked:
            motivo = {
                "feature": feat,
                "reason": feature_labels.get(feat, feat),
                "value": round(float(features.get(feat, 0)), 4),
                "shap": round(float(shap_val), 4),
            }
            motivos.append(motivo)
    else:
        # Fallback: top features by raw value (value > 0.1)
        ranked = sorted(
            ((k, v) for k, v in features.items() if v > 0.1),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        for feat, val in ranked:
            motivo = {
                "feature": feat,
                "reason": feature_labels.get(feat, feat),
                "value": round(float(val), 4),
            }
            motivos.append(motivo)

    return motivos


def _active_model(db: Session, model_version: str | None = None) -> ModeloProspeccao:
    query = db.query(ModeloProspeccao)
    if model_version:
        model = query.filter(ModeloProspeccao.versao == model_version).first()
    else:
        model = query.filter(ModeloProspeccao.ativo.is_(True)).order_by(ModeloProspeccao.treinado_em.desc()).first()
    if not model:
        raise ValueError("No prospection model is available. Run train-ranker first.")
    return model


def _predict_and_explain(
    model: ModeloProspeccao,
    feature_rows: list[dict[str, float]],
) -> tuple[list[float], list[dict[str, float]] | None]:
    """Return (predictions, per-row SHAP value dicts or None)."""
    if model.algoritmo == "xgboost_ranker" and model.artefato_path:
        import joblib
        import numpy as np

        artifact = joblib.load(Path(config.REPO_ROOT) / model.artefato_path)
        ranker = artifact["model"]
        features = artifact.get("features", FEATURE_NAMES)
        x = np.asarray(
            [[float(row.get(name, 0.0)) for name in features] for row in feature_rows],
            dtype=float,
        )
        predictions = [float(v) for v in ranker.predict(x)]

        shap_maps: list[dict[str, float]] | None = None
        try:
            import shap

            explainer = shap.TreeExplainer(ranker)
            shap_values = explainer.shap_values(x)
            shap_maps = [
                dict(zip(features, (float(v) for v in row_shap), strict=False))
                for row_shap in shap_values
            ]
        except Exception as exc:
            logger.warning("SHAP calculation failed: %s", exc)

        return predictions, shap_maps

    return [heuristic_score(row) for row in feature_rows], None


def _priority(rank: int, group_size: int, score: float) -> str:
    """Assign priority tier based on absolute score thresholds with rank-based fallback.

    Scores are on a heuristic 0–100 scale (from heuristic_score) or 0–1 for XGBoost models.
    Absolute thresholds take precedence to prevent low-quality candidates from ranking high.

    Args:
        rank: Position in sorted group (1-indexed, lower is better)
        group_size: Total candidates in the qid group
        score: Absolute score value (0–100 heuristic or 0–1 XGBoost)

    Returns:
        Priority tier: 'alta', 'media', or 'baixa'
    """
    # Normalize XGBoost scores (0–1) to 0–100 scale for consistent thresholds
    # XGBoost produces floats ~0.1–0.9; heuristic already 0–100
    normalized_score = score if score > 10 else score * 100

    # Absolute score thresholds (primary filter)
    if normalized_score >= 70:
        return "alta"
    if normalized_score <= 20:
        return "baixa"

    # Relative rank within group (tiebreaker for middle scores 20–70)
    if rank <= 5:
        return "alta"
    if rank <= 20 or rank <= max(1, int(group_size * 0.20)):
        return "media"
    return "baixa"


def score_candidates(
    db: Session,
    *,
    model_version: str | None = None,
    pipeline_version: str | None = None,
) -> dict[str, Any]:
    model = _active_model(db, model_version)
    pipeline_version = pipeline_version or model.pipeline_version

    # Validate pipeline version compatibility
    if model.pipeline_version and pipeline_version and model.pipeline_version != pipeline_version:
        raise ValueError(
            f"Model '{model.versao}' was trained on pipeline '{model.pipeline_version}' "
            f"but requested pipeline is '{pipeline_version}'. "
            f"Use --pipeline-version {model.pipeline_version} or retrain the model."
        )

    snapshots = (
        db.query(FeatureSnapshotProspeccao)
        .filter(FeatureSnapshotProspeccao.pipeline_version == pipeline_version)
        .order_by(FeatureSnapshotProspeccao.qid.asc(), FeatureSnapshotProspeccao.id.asc())
        .all()
    )
    grouped: dict[str, list[FeatureSnapshotProspeccao]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[snapshot.qid].append(snapshot)

    created = 0
    updated = 0
    processed = 0
    scores_by_prioridade: Counter[str] = Counter()
    batch_size = 2000

    for qid, rows in grouped.items():
        feature_rows = [json.loads(row.features_json) for row in rows]
        predictions, shap_maps = _predict_and_explain(model, feature_rows)
        explanations = shap_maps or [None] * len(rows)
        ranked = sorted(
            zip(rows, feature_rows, predictions, explanations, strict=False),
            key=lambda item: item[2],
            reverse=True,
        )

        for rank, (snapshot, features, score, shap_vals) in enumerate(ranked, start=1):
            score_row = (
                db.query(ScoreProspeccao)
                .filter(
                    ScoreProspeccao.snapshot_id == snapshot.id,
                    ScoreProspeccao.modelo_id == model.id,
                )
                .first()
            )
            if not score_row:
                score_row = ScoreProspeccao(snapshot_id=snapshot.id, modelo_id=model.id)
                db.add(score_row)
                created += 1
            else:
                updated += 1

            score_row.empresa_id = snapshot.empresa_id
            score_row.local_id = snapshot.local_id
            score_row.qid = qid
            score_row.score = round(float(score), 6)
            score_row.ranking_contexto = rank
            score_row.prioridade = _priority(rank, len(ranked), float(score))
            scores_by_prioridade[score_row.prioridade] += 1
            score_row.pipeline_version = pipeline_version
            # Build enriched motivos with SHAP context and human-readable labels
            enriched_motivos = _build_enriched_motivos(features, shap_vals, FEATURE_NAMES)
            score_row.motivos_json = _json(enriched_motivos)
            score_row.calculado_em = datetime.utcnow()

            processed += 1
            if processed % batch_size == 0:
                db.commit()
                logger.info(f"Committed batch of {batch_size}. Progress: {processed}/{len(snapshots)} scores processed.")

    # Final commit for remaining records
    db.commit()

    # Log distribution of priorities
    all_scores = db.query(ScoreProspeccao).filter(
        ScoreProspeccao.modelo_id == model.id,
        ScoreProspeccao.pipeline_version == pipeline_version,
    ).all()
    prioridade_dist = Counter(s.prioridade for s in all_scores)
    logger.info("Distribuicao de prioridades: %s", dict(prioridade_dist))

    return {
        "modelo": model.versao,
        "model_version": model.versao,
        "algoritmo": model.algoritmo,
        "pipeline_version": pipeline_version,
        "snapshots": len(snapshots),
        "scores_criados": created,
        "scores_atualizados": updated,
        "grupos": len(grouped),
        "qids_processed": len(grouped),
        "scores_by_prioridade": dict(scores_by_prioridade),
        "prioridade_distribuicao": dict(prioridade_dist),
    }
