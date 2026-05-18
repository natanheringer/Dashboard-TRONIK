"""Service layer for the REE prospection ranking read model."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato, ScoreProspeccao
from jobs.prospeccao.publish_scores import (
    list_published_scores,
    percentile_map_for_qid,
    resolve_model,
    serialize_published_score_row,
)


def buscar_candidatos_prospeccao(
    db: Session,
    *,
    limite: int = 50,
    qid: str | None = None,
    prioridade: str | None = None,
    model_version: str | None = None,
) -> list[dict[str, Any]]:
    """Return the same ranked candidate queue used by dashboard and Nik."""
    rows = list_published_scores(
        db,
        limite=limite,
        qid=qid,
        prioridade=prioridade,
        model_version=model_version,
    )
    for row in rows:
        if row.get("empresa_id") is None:
            emp = row.get("empresa") or {}
            if isinstance(emp, dict) and emp.get("id") is not None:
                row["empresa_id"] = emp["id"]
    return rows


def buscar_modelo_ativo(db: Session) -> dict[str, Any] | None:
    """Return summary of the active prospection ranker model."""
    model = resolve_model(db)
    if not model:
        return None
    return {
        "versao": model.versao,
        "algoritmo": model.algoritmo,
        "metricas": json.loads(model.metricas_json) if model.metricas_json else {},
        "treinado_em": model.treinado_em.isoformat() if model.treinado_em else None,
    }


def explicar_candidato(db: Session, score_id: int, model_version: str | None = None) -> dict[str, Any] | None:
    model = resolve_model(db, model_version)
    if not model:
        return None

    row = (
        db.query(ScoreProspeccao, EmpresaCandidata, LocalCandidato)
        .outerjoin(EmpresaCandidata, ScoreProspeccao.empresa_id == EmpresaCandidata.id)
        .outerjoin(LocalCandidato, ScoreProspeccao.local_id == LocalCandidato.id)
        .filter(ScoreProspeccao.id == score_id, ScoreProspeccao.modelo_id == model.id)
        .first()
    )
    if not row:
        return None

    score, empresa, local = row
    pct = percentile_map_for_qid(db, model.id, score.qid)
    payload = serialize_published_score_row(
        score,
        empresa,
        local,
        score_percentil=pct.get(score.id, 0.0),
    )
    return {
        "score": payload,
        "explicacao": payload.get("motivos", []),
    }


_METRICAS_CHAVE = (
    "validation_ndcg_mean",
    "train_ndcg_mean",
    "validation_ndcg@20",
    "train_ndcg@20",
    "n_samples",
    "n_groups",
)


def saude_prospeccao(db: Session, model_version: str | None = None) -> dict[str, Any]:
    """Health snapshot for GET /api/prospeccao/saude and monitor CLI."""
    from jobs.prospeccao.pipeline_health import build_pipeline_health_report

    return build_pipeline_health_report(db, model_version=model_version)


def status_modelo_prospeccao(db: Session, model_version: str | None = None) -> dict[str, Any] | None:
    """Versão ativa do ranker e métricas principais persistidas no banco."""
    model = resolve_model(db, model_version)
    if not model:
        return None

    metricas_brutas = json.loads(model.metricas_json) if model.metricas_json else {}
    metricas = {
        k: metricas_brutas[k]
        for k in _METRICAS_CHAVE
        if k in metricas_brutas and metricas_brutas[k] is not None
    }
    if not metricas and metricas_brutas:
        metricas = metricas_brutas

    total_scores = (
        db.query(func.count(ScoreProspeccao.id))
        .filter(ScoreProspeccao.modelo_id == model.id)
        .scalar()
        or 0
    )
    prioridade_rows = (
        db.query(ScoreProspeccao.prioridade, func.count(ScoreProspeccao.id))
        .filter(ScoreProspeccao.modelo_id == model.id)
        .group_by(ScoreProspeccao.prioridade)
        .all()
    )

    return {
        "modelo": {
            "versao": model.versao,
            "ativo": model.ativo,
            "algoritmo": model.algoritmo,
            "objetivo": model.objetivo,
            "pipeline_version": model.pipeline_version,
            "treinado_em": model.treinado_em.isoformat() if model.treinado_em else None,
        },
        "metricas": metricas,
        "total_scores": int(total_scores),
        "prioridade": {str(prioridade or "media"): int(qtd) for prioridade, qtd in prioridade_rows},
    }
