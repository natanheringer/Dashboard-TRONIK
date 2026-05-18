"""Read-model helpers for publishing prospection scores."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato, ModeloProspeccao, ScoreProspeccao


def _resolve_model(db: Session, model_version: str | None = None) -> ModeloProspeccao | None:
    query = db.query(ModeloProspeccao)
    if model_version:
        return query.filter(ModeloProspeccao.versao == model_version).first()
    return query.filter(ModeloProspeccao.ativo.is_(True)).order_by(ModeloProspeccao.treinado_em.desc()).first()


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

    Args:
        db: SQLAlchemy session
        limite: Max results (default 50)
        qid: Filter by listwise query id (e.g., 'bairro:brasilia:centro', 'ra:RA I')
        prioridade: Filter by priority tier ('alta', 'media', 'baixa')
        model_version: Specific model version; if None, uses latest active model

    Returns:
        List of score dicts with nested empresa/local details and percentile, sorted by qid, then ranking_contexto
    """
    model = _resolve_model(db, model_version)
    if not model:
        return []

    query = (
        db.query(ScoreProspeccao, EmpresaCandidata, LocalCandidato)
        .outerjoin(EmpresaCandidata, ScoreProspeccao.empresa_id == EmpresaCandidata.id)
        .outerjoin(LocalCandidato, ScoreProspeccao.local_id == LocalCandidato.id)
        .filter(ScoreProspeccao.modelo_id == model.id)
        .order_by(ScoreProspeccao.qid.asc(), ScoreProspeccao.ranking_contexto.asc())
    )
    if qid:
        query = query.filter(ScoreProspeccao.qid == qid)
    if prioridade:
        query = query.filter(ScoreProspeccao.prioridade == prioridade)

    rows = []
    # Cache percentiles per QID to avoid redundant calculations
    percentile_cache: dict[str, dict[int, float]] = {}

    for score, empresa, local in query.limit(limite).all():
        payload = score.to_dict()
        payload["empresa"] = empresa.to_dict() if empresa else None
        payload["local"] = local.to_dict() if local else None

        # Calculate score_percentil: position in QID distribution (0-100)
        if score.qid not in percentile_cache:
            qid_scores = (
                db.query(ScoreProspeccao.id, ScoreProspeccao.score)
                .filter(
                    ScoreProspeccao.modelo_id == model.id,
                    ScoreProspeccao.qid == score.qid,
                )
                .order_by(ScoreProspeccao.score.desc())
                .all()
            )
            # Build rank→percentile mapping: top rank gets 100, last gets 0
            percentile_cache[score.qid] = {}
            if qid_scores:
                for idx, (score_id, _) in enumerate(qid_scores):
                    percentile = round(100 * (1 - idx / len(qid_scores)), 1)
                    percentile_cache[score.qid][score_id] = percentile

        payload["score_percentil"] = percentile_cache[score.qid].get(score.id, 0.0)
        rows.append(payload)

    return rows
