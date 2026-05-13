"""Service layer for the REE prospection ranking read model."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato, ModeloProspeccao, ScoreProspeccao
from jobs.prospeccao.publish_scores import list_published_scores


def buscar_candidatos_prospeccao(
    db: Session,
    *,
    limite: int = 50,
    qid: str | None = None,
    prioridade: str | None = None,
    model_version: str | None = None,
) -> list[dict[str, Any]]:
    """Return the same ranked candidate queue used by dashboard and Nik."""
    return list_published_scores(
        db,
        limite=limite,
        qid=qid,
        prioridade=prioridade,
        model_version=model_version,
    )


def _resolve_model(db: Session, model_version: str | None = None) -> ModeloProspeccao | None:
    query = db.query(ModeloProspeccao)
    if model_version:
        return query.filter(ModeloProspeccao.versao == model_version).first()
    return query.filter(ModeloProspeccao.ativo.is_(True)).order_by(ModeloProspeccao.treinado_em.desc()).first()


def explicar_candidato(db: Session, score_id: int, model_version: str | None = None) -> dict[str, Any] | None:
    model = _resolve_model(db, model_version)
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
    payload = score.to_dict()
    payload["empresa"] = empresa.to_dict() if empresa else None
    payload["local"] = local.to_dict() if local else None
    return {
        "score": payload,
        "explicacao": payload.get("motivos", []),
    }
