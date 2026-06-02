"""Read-model helpers for publishing prospection scores."""

from __future__ import annotations

from typing import Any

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
    return _batch_percentile_map(db, model_id, {qid}).get(qid, {})


def _batch_percentile_map(
    db: Session, model_id: int, qids: set[str]
) -> dict[str, dict[int, float]]:
    """Compute percentile maps for multiple QIDs in a single query."""
    if not qids:
        return {}
    all_rows = (
        db.query(ScoreProspeccao.id, ScoreProspeccao.score, ScoreProspeccao.qid)
        .filter(
            ScoreProspeccao.modelo_id == model_id,
            ScoreProspeccao.qid.in_(qids),
        )
        .order_by(ScoreProspeccao.qid, ScoreProspeccao.score.desc())
        .all()
    )
    # Group by qid and compute percentile rank within each group
    from itertools import groupby
    result: dict[str, dict[int, float]] = {}
    for qid, rows in groupby(all_rows, key=lambda r: r[2]):
        group = list(rows)
        n = len(group)
        result[qid] = {row[0]: round(100 * (1 - i / n), 1) for i, row in enumerate(group)}
    return result


def _fetch_tier(
    db: Session,
    model_id: int,
    prioridade: str,
    limite: int,
) -> list[tuple]:
    """Fetch top-N rows for one priority tier ordered by score desc.

    Uses idx_score_prospeccao_modelo_prio_score to avoid full-table sort.
    """
    return (
        db.query(ScoreProspeccao, EmpresaCandidata, LocalCandidato)
        .outerjoin(EmpresaCandidata, ScoreProspeccao.empresa_id == EmpresaCandidata.id)
        .outerjoin(LocalCandidato, ScoreProspeccao.local_id == LocalCandidato.id)
        .filter(
            ScoreProspeccao.modelo_id == model_id,
            ScoreProspeccao.prioridade == prioridade,
        )
        .order_by(ScoreProspeccao.score.desc())
        .limit(limite)
        .all()
    )


def list_published_scores(
    db: Session,
    *,
    limite: int = 50,
    qid: str | None = None,
    prioridade: str | None = None,
    model_version: str | None = None,
) -> list[dict[str, Any]]:
    """Publish prospection scores with embedded company and location details for dashboard/Nik.

    Ordering:
    - With ``qid``: listwise order (``ranking_contexto`` ascending).
    - Without ``qid`` + single prioridade: top-N by score desc for that tier.
    - Without ``qid`` + no prioridade filter: priority tiers in alta→media→baixa order,
      each tier fetched independently so idx_score_prospeccao_modelo_prio_score is used
      instead of a full-table CASE sort on 1M+ rows.
    """
    model = resolve_model(db, model_version)
    if not model:
        return []

    base_query = (
        db.query(ScoreProspeccao, EmpresaCandidata, LocalCandidato)
        .outerjoin(EmpresaCandidata, ScoreProspeccao.empresa_id == EmpresaCandidata.id)
        .outerjoin(LocalCandidato, ScoreProspeccao.local_id == LocalCandidato.id)
        .filter(ScoreProspeccao.modelo_id == model.id)
    )

    if qid:
        result_rows = (
            base_query
            .filter(ScoreProspeccao.qid == qid)
            .order_by(ScoreProspeccao.ranking_contexto.asc())
            .limit(limite)
            .all()
        )
    elif prioridade:
        result_rows = (
            base_query
            .filter(ScoreProspeccao.prioridade == prioridade)
            .order_by(ScoreProspeccao.score.desc())
            .limit(limite)
            .all()
        )
    else:
        # Tier-by-tier fetch: avoids CASE expression on 1M+ rows.
        # Each sub-query uses idx_score_prospeccao_modelo_prio_score.
        result_rows = []
        remaining = limite
        for tier in ("alta", "media", "baixa"):
            if remaining <= 0:
                break
            tier_rows = _fetch_tier(db, model.id, tier, remaining)
            result_rows.extend(tier_rows)
            remaining -= len(tier_rows)

    if not result_rows:
        return []

    # Batch-compute percentiles for all unique QIDs in a single query
    unique_qids = {score.qid for score, _, _ in result_rows}
    percentile_cache = _batch_percentile_map(db, model.id, unique_qids)

    rows = []
    for score, empresa, local in result_rows:
        pct_map = percentile_cache.get(score.qid, {})
        payload = serialize_published_score_row(
            score,
            empresa,
            local,
            score_percentil=pct_map.get(score.id, 0.0),
        )
        rows.append(payload)

    return rows
