"""Health report for the REE prospection ranker (API, cron, monitor CLI)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import ModeloProspeccao, ScoreProspeccao

_NDCG_KEYS = (
    "validation_ndcg_mean",
    "train_ndcg_mean",
    "validation_ndcg@20",
    "train_ndcg@20",
)


def _resolve_model(db: Session, model_version: str | None = None) -> ModeloProspeccao | None:
    query = db.query(ModeloProspeccao)
    if model_version:
        return query.filter(ModeloProspeccao.versao == model_version).first()
    return query.filter(ModeloProspeccao.ativo.is_(True)).order_by(ModeloProspeccao.treinado_em.desc()).first()


def build_pipeline_health_report(
    db: Session,
    *,
    model_version: str | None = None,
) -> dict[str, Any]:
    """JSON-serializable health snapshot for /api/prospeccao/saude and monitor CLI."""
    model = _resolve_model(db, model_version)
    if not model:
        return {
            "modelo_ativo": False,
            "algoritmo": None,
            "scores_publicados": 0,
            "ultimo_treino": None,
            "metricas": {},
            "warning": "Nenhum modelo de prospecção ativo no banco.",
            "warnings": ["Nenhum modelo de prospecção ativo no banco."],
        }

    metricas_brutas = json.loads(model.metricas_json) if model.metricas_json else {}
    metricas = {
        k: metricas_brutas[k]
        for k in _NDCG_KEYS
        if k in metricas_brutas and metricas_brutas[k] is not None
    }
    if not metricas and metricas_brutas:
        metricas = {
            k: v
            for k, v in metricas_brutas.items()
            if "ndcg" in k.lower() and v is not None
        }

    scores_publicados = (
        db.query(func.count(ScoreProspeccao.id))
        .filter(ScoreProspeccao.modelo_id == model.id)
        .scalar()
        or 0
    )

    warnings: list[str] = []
    warning: str | None = None
    if model.algoritmo == "heuristic_bootstrap":
        warning = (
            "Modelo heuristic_bootstrap ativo — grupos rotulados insuficientes para XGBRanker; "
            "scores usam heurística até novo treino."
        )
        warnings.append(warning)
    if scores_publicados == 0:
        warnings.append("Nenhum score publicado para o modelo ativo.")

    return {
        "modelo_ativo": bool(model.ativo),
        "versao": model.versao,
        "algoritmo": model.algoritmo,
        "pipeline_version": model.pipeline_version,
        "scores_publicados": int(scores_publicados),
        "ultimo_treino": model.treinado_em.isoformat() if model.treinado_em else None,
        "metricas": metricas,
        "warning": warning,
        "warnings": warnings,
    }
