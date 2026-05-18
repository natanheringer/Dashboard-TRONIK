"""Read-model helpers for publishing prospection scores."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case
from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato, ModeloProspeccao, ScoreProspeccao


def resolve_model(db: Session, model_version: str | None = None) -> ModeloProspeccao | None:
    """Resolve prospection model row: explicit version or newest active model."""
    query = db.query(ModeloProspeccao)
    if model_version:
        return query.filter(ModeloProspeccao.versao == model_version).first()
    return query.filter(ModeloProspeccao.ativo.is_(True)).order_by(ModeloProspeccao.treinado_em.desc()).first()


def serialize_published_score_row(
    score: ScoreProspeccao,
    empresa: EmpresaCandidata | None,
    local: LocalCandidato | None,
    **extras: Any,
) -> dict[str, Any]:
    """Single shape for dashboard API, CRM bridge, and explain — no duplicated field lists."""
    payload = score.to_dict()
    payload["empresa"] = empresa.to_dict() if empresa else None
    payload["local"] = local.to_dict() if local else None
    if extras:
        payload.update(extras)
    return payload


def percentile_map_for_qid(db: Session, model_id: int, qid: str) -> dict[int, float]:
    """Map score.id -> percentile (0–100) within the same QID for this model."""
    qid_scores = (
        db.query(ScoreProspeccao.id, ScoreProspeccao.score)
        .filter(
            ScoreProspeccao.modelo_id == model_id,
            ScoreProspeccao.qid == qid,
        )
        .order_by(ScoreProspeccao.score.desc())
        .all()
    )
    if not qid_scores:
        return {}
    out: dict[int, float] = {}
    for idx, (score_id, _) in enumerate(qid_scores):
        out[score_id] = round(100 * (1 - idx / len(qid_scores)), 1)
    return out


def list_published_scores(
    db: Session,
    *,
    limite: int = 50,
    qid: str | None = None,
    prioridade: str | None = None,
    model_version: str | None = None,
) -> list[dict[str, Any]]:
    """Publish prospection scores with embedded company and location details for dashboard/Nik.

    Query filters by active model (or specified version) and joins company and location data.
    Returned payload includes: score, ranking_contexto, prioridade, motivos, score_percentil,
    empresa (razao_social, cnae_principal, cnae_secundarios, porte, bairro, cep, endereco_normalizado,
    email, telefone), local (endereco, latitude, longitude, ra, bairro, geocode_quality).

    score_percentil: Percentile rank (0-100) within the same QID group, showing relative performance.

    Ordering:
    - With ``qid``: listwise order (``ranking_contexto`` ascending).
    - Without ``qid``: global queue for operators — priority tier (alta → media → baixa), then score
      descending, then rank within context — so ``limite`` is a true top-N across the published pool.

    Args:
        db: SQLAlchemy session
        limite: Max results (default 50)
        qid: Filter by listwise query id (e.g., 'bairro:brasilia:centro', 'ra:RA I')
        prioridade: Filter by priority tier ('alta', 'media', 'baixa')
        model_version: Specific model version; if None, uses latest active model

    Returns:
        List of score dicts with nested empresa/local details and percentile
    """
    model = resolve_model(db, model_version)
    if not model:
        return []

    prioridade_ordem = case(
        (ScoreProspeccao.prioridade == "alta", 0),
        (ScoreProspeccao.prioridade == "media", 1),
        (ScoreProspeccao.prioridade == "baixa", 2),
        else_=3,
    )

    query = (
        db.query(ScoreProspeccao, EmpresaCandidata, LocalCandidato)
        .outerjoin(EmpresaCandidata, ScoreProspeccao.empresa_id == EmpresaCandidata.id)
        .outerjoin(LocalCandidato, ScoreProspeccao.local_id == LocalCandidato.id)
        .filter(ScoreProspeccao.modelo_id == model.id)
    )
    if qid:
        query = query.filter(ScoreProspeccao.qid == qid).order_by(ScoreProspeccao.ranking_contexto.asc())
    else:
        query = query.order_by(
            prioridade_ordem,
            ScoreProspeccao.score.desc(),
            ScoreProspeccao.ranking_contexto.asc(),
            ScoreProspeccao.qid.asc(),
        )
    if prioridade:
        query = query.filter(ScoreProspeccao.prioridade == prioridade)

    rows = []
    percentile_cache: dict[str, dict[int, float]] = {}

    for score, empresa, local in query.limit(limite).all():
        if score.qid not in percentile_cache:
            percentile_cache[score.qid] = percentile_map_for_qid(db, model.id, score.qid)
        pct_map = percentile_cache[score.qid]
        payload = serialize_published_score_row(
            score,
            empresa,
            local,
            score_percentil=pct_map.get(score.id, 0.0),
        )
        rows.append(payload)

    return rows
