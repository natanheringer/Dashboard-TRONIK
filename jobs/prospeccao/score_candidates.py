"""Score prospection feature snapshots with the active ranker."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import FeatureSnapshotProspeccao, ModeloProspeccao, ScoreProspeccao
from jobs.prospeccao import config
from jobs.prospeccao.ranker_contract import FEATURE_NAMES, heuristic_score, top_reasons


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


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
                dict(zip(features, (float(v) for v in row_shap)))
                for row_shap in shap_values
            ]
        except Exception:
            pass

        return predictions, shap_maps

    return [heuristic_score(row) for row in feature_rows], None


def _priority(rank: int, group_size: int) -> str:
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
    for qid, rows in grouped.items():
        feature_rows = [json.loads(row.features_json) for row in rows]
        predictions, shap_maps = _predict_and_explain(model, feature_rows)
        explanations = shap_maps or [None] * len(rows)
        ranked = sorted(
            zip(rows, feature_rows, predictions, explanations),
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
            score_row.prioridade = _priority(rank, len(ranked))
            score_row.motivos_json = _json(top_reasons(features, shap_values=shap_vals))
            score_row.calculado_em = datetime.utcnow()

    return {
        "modelo": model.versao,
        "algoritmo": model.algoritmo,
        "pipeline_version": pipeline_version,
        "snapshots": len(snapshots),
        "scores_criados": created,
        "scores_atualizados": updated,
        "grupos": len(grouped),
    }
