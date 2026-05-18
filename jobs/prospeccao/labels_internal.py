"""Ground-truth relevance signals from Tronik operational DB (parceiro / coleta / contrato).

Joins prospection candidates (empresa_candidata) to internal ops via:
- normalized parceiro nome and coletor localizacao
- CNPJ extracted from coletor notes / pipeline observacoes
- CRM pipeline won deals (fechado / ganho) keyed by client name (coletor.localizacao)
- weak CNPJ substring in coletor.localizacao when parceiro has no CNPJ

Used by build-features when ``use_internal_labels=True``: internal continuous score
replaces the heuristic bootstrap where a match exists; listwise equal-frequency binning
per qid is unchanged so XGBRanker training stays compatible.

Training labels default to **ops-only** signals. Optional ``apply_crm_persisted_boost``
can add a bonus when ``empresa.pipeline_id`` points at a CRM row already marked won —
that encodes deal outcome, is not a model feature, and would leak label information
into the ranker targets if enabled during ``build-features``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import (
    Coleta,
    Coletor,
    ContratoRecorrente,
    EmpresaCandidata,
    LocalCandidato,
    Parceiro,
    Pipeline,
)

logger = logging.getLogger(__name__)

_NAME_STOPWORDS = frozenset(
    {
        "ltda",
        "ltda.",
        "me",
        "epp",
        "sa",
        "s/a",
        "eireli",
        "filial",
        "matriz",
    },
)

_PIPELINE_WON_STATUSES = frozenset({"fechado", "ganho", "won", "fechado_ganho"})
_CRM_PERSISTED_LINK_BOOST = 15.0

_CNPJ_RE = re.compile(
    r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\b\d{14}\b",
)


@dataclass
class InternalSiteSignals:
    """Aggregated ops signals for one internal site (coletor / parceiro)."""

    coletor_id: int | None = None
    parceiro_id: int | None = None
    parceiro_ativo: bool = False
    coleta_count: int = 0
    volume_total_kg: float = 0.0
    last_coleta_at: datetime | None = None
    has_active_contract: bool = False
    contract_valor_mensal: float = 0.0
    pipeline_won: bool = False
    match_keys: set[str] = field(default_factory=set)


@dataclass
class InternalLabelIndex:
    """Lookup tables for operational joins."""

    by_norm_name: dict[str, InternalSiteSignals] = field(default_factory=dict)
    by_norm_localizacao: dict[str, InternalSiteSignals] = field(default_factory=dict)
    by_cnpj: dict[str, InternalSiteSignals] = field(default_factory=dict)
    by_pipeline_won: dict[str, InternalSiteSignals] = field(default_factory=dict)
    fechado_pipeline_ids: frozenset[int] = field(default_factory=frozenset)
    localizacao_digit_blobs: list[tuple[str, InternalSiteSignals]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def normalize_org_name(value: str | None) -> str:
    """Lowercase, strip accents and legal suffix noise for fuzzy name joins."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in text.split() if t and t not in _NAME_STOPWORDS]
    return " ".join(tokens).strip()


def normalize_cnpj(value: str | None) -> str:
    """Digits-only CNPJ (14 chars) or empty when invalid."""
    if not value:
        return ""
    digits = "".join(c for c in str(value) if c.isdigit())
    return digits if len(digits) == 14 else ""


def extract_cnpjs_from_text(text: str | None) -> set[str]:
    """Find valid 14-digit CNPJs embedded in free text (notes / observacoes)."""
    if not text:
        return set()
    found: set[str] = set()
    for match in _CNPJ_RE.finditer(str(text)):
        cnpj = normalize_cnpj(match.group(0))
        if cnpj:
            found.add(cnpj)
    return found


def _digits_only(text: str | None) -> str:
    if not text:
        return ""
    return "".join(c for c in str(text) if c.isdigit())


def _coletor_notes_text(coletor: Coletor, pipeline_obs_by_coletor: dict[int, list[str]]) -> str:
    parts: list[str] = []
    obs = getattr(coletor, "observacoes", None)
    if obs:
        parts.append(str(obs))
    for note in pipeline_obs_by_coletor.get(coletor.id, []):
        parts.append(note)
    return "\n".join(parts)


def _merge_signals(existing: InternalSiteSignals, incoming: InternalSiteSignals) -> InternalSiteSignals:
    last = existing.last_coleta_at
    if incoming.last_coleta_at and (last is None or incoming.last_coleta_at > last):
        last = incoming.last_coleta_at
    return InternalSiteSignals(
        coletor_id=existing.coletor_id or incoming.coletor_id,
        parceiro_id=existing.parceiro_id or incoming.parceiro_id,
        parceiro_ativo=existing.parceiro_ativo or incoming.parceiro_ativo,
        coleta_count=existing.coleta_count + incoming.coleta_count,
        volume_total_kg=existing.volume_total_kg + incoming.volume_total_kg,
        last_coleta_at=last,
        has_active_contract=existing.has_active_contract or incoming.has_active_contract,
        contract_valor_mensal=max(existing.contract_valor_mensal, incoming.contract_valor_mensal),
        pipeline_won=existing.pipeline_won or incoming.pipeline_won,
        match_keys=existing.match_keys | incoming.match_keys,
    )


def _register(index: dict[str, InternalSiteSignals], key: str, signals: InternalSiteSignals) -> None:
    if not key:
        return
    signals.match_keys.add(key)
    if key in index:
        index[key] = _merge_signals(index[key], signals)
    else:
        index[key] = signals


def build_internal_label_index(db: Session, cutoff_date: datetime | None = None) -> InternalLabelIndex:
    """Scan parceiro / coletor / coleta / contrato / pipeline and build join indexes.

    Args:
        db: Database session.
        cutoff_date: If provided, filter coletas and contratos to this datetime (prevents data leakage).
    """
    by_norm_name: dict[str, InternalSiteSignals] = {}
    by_norm_localizacao: dict[str, InternalSiteSignals] = {}
    by_cnpj: dict[str, InternalSiteSignals] = {}
    by_pipeline_won: dict[str, InternalSiteSignals] = {}
    localizacao_digit_blobs: list[tuple[str, InternalSiteSignals]] = []
    now = datetime.now(timezone.utc)

    parceiros = {p.id: p for p in db.query(Parceiro).all()}
    for parceiro in parceiros.values():
        key = normalize_org_name(parceiro.nome)
        _register(
            by_norm_name,
            key,
            InternalSiteSignals(
                parceiro_id=parceiro.id,
                parceiro_ativo=bool(parceiro.ativo),
            ),
        )

    coleta_query = db.query(
        Coleta.coletor_id.label("coletor_id"),
        func.count(Coleta.id).label("coleta_count"),
        func.coalesce(func.sum(Coleta.volume_estimado), 0.0).label("volume_total"),
        func.max(Coleta.data_hora).label("last_coleta_at"),
    )
    if cutoff_date is not None:
        coleta_query = coleta_query.filter(Coleta.data_hora <= cutoff_date)
    coleta_agg = coleta_query.group_by(Coleta.coletor_id).all()
    coleta_by_coletor = {row.coletor_id: row for row in coleta_agg}

    contrato_query = db.query(
        ContratoRecorrente.coletor_id.label("coletor_id"),
        func.max(ContratoRecorrente.valor_mensal).label("valor_mensal"),
    ).filter(ContratoRecorrente.status == "ativo")
    if cutoff_date is not None:
        contrato_query = contrato_query.filter(ContratoRecorrente.created_at <= cutoff_date)
    contrato_agg = contrato_query.group_by(ContratoRecorrente.coletor_id).all()
    contrato_by_coletor = {row.coletor_id: row for row in contrato_agg}

    pipeline_obs_by_coletor: dict[int, list[str]] = {}
    fechado_pipeline_ids: set[int] = set()
    pipeline_won_rows = 0
    for pipe in db.query(Pipeline).all():
        status = (pipe.status or "").strip().lower()
        if status not in _PIPELINE_WON_STATUSES:
            continue
        fechado_pipeline_ids.add(pipe.id)
        pipeline_won_rows += 1
        if pipe.coletor_id and pipe.observacoes:
            pipeline_obs_by_coletor.setdefault(pipe.coletor_id, []).append(str(pipe.observacoes))

    coletores = db.query(Coletor).all()
    coletor_by_id = {c.id: c for c in coletores}
    cnpj_from_notes = 0

    for coletor in coletores:
        agg = coleta_by_coletor.get(coletor.id)
        contrato = contrato_by_coletor.get(coletor.id)
        parceiro = parceiros.get(coletor.parceiro_id) if coletor.parceiro_id else None
        signals = InternalSiteSignals(
            coletor_id=coletor.id,
            parceiro_id=coletor.parceiro_id,
            parceiro_ativo=bool(parceiro.ativo) if parceiro else False,
            coleta_count=int(agg.coleta_count) if agg else 0,
            volume_total_kg=float(agg.volume_total) if agg else 0.0,
            last_coleta_at=agg.last_coleta_at if agg else None,
            has_active_contract=contrato is not None,
            contract_valor_mensal=float(contrato.valor_mensal) if contrato else 0.0,
        )

        loc_key = normalize_org_name(coletor.localizacao)
        _register(by_norm_localizacao, loc_key, signals)
        if parceiro:
            _register(by_norm_name, normalize_org_name(parceiro.nome), signals)

        loc_digits = _digits_only(coletor.localizacao)
        if loc_digits:
            localizacao_digit_blobs.append((loc_digits, signals))

        notes = _coletor_notes_text(coletor, pipeline_obs_by_coletor)
        for cnpj in extract_cnpjs_from_text(notes):
            cnpj_from_notes += 1
            _register(by_cnpj, cnpj, signals)
        for cnpj in extract_cnpjs_from_text(coletor.localizacao):
            _register(by_cnpj, cnpj, signals)

    for pipe in db.query(Pipeline).all():
        status = (pipe.status or "").strip().lower()
        if status not in _PIPELINE_WON_STATUSES:
            continue
        coletor = coletor_by_id.get(pipe.coletor_id) if pipe.coletor_id else None
        base = InternalSiteSignals(
            coletor_id=pipe.coletor_id,
            parceiro_id=coletor.parceiro_id if coletor else None,
            pipeline_won=True,
        )
        if coletor:
            agg = coleta_by_coletor.get(coletor.id)
            contrato = contrato_by_coletor.get(coletor.id)
            parceiro = parceiros.get(coletor.parceiro_id) if coletor.parceiro_id else None
            base = InternalSiteSignals(
                coletor_id=coletor.id,
                parceiro_id=coletor.parceiro_id,
                parceiro_ativo=bool(parceiro.ativo) if parceiro else False,
                coleta_count=int(agg.coleta_count) if agg else 0,
                volume_total_kg=float(agg.volume_total) if agg else 0.0,
                last_coleta_at=agg.last_coleta_at if agg else None,
                has_active_contract=contrato is not None,
                contract_valor_mensal=float(contrato.valor_mensal) if contrato else 0.0,
                pipeline_won=True,
            )
            _register(by_pipeline_won, normalize_org_name(coletor.localizacao), base)
        if pipe.observacoes:
            _register(by_pipeline_won, normalize_org_name(pipe.observacoes), base)
        for cnpj in extract_cnpjs_from_text(pipe.observacoes):
            _register(by_cnpj, cnpj, base)

    stats = {
        "parceiros": len(parceiros),
        "coletores": len(coletores),
        "index_keys_parceiro": len(by_norm_name),
        "index_keys_localizacao": len(by_norm_localizacao),
        "index_keys_cnpj": len(by_cnpj),
        "index_keys_pipeline_won": len(by_pipeline_won),
        "localizacao_digit_blobs": len(localizacao_digit_blobs),
        "pipeline_won_rows": pipeline_won_rows,
        "fechado_pipeline_ids": len(fechado_pipeline_ids),
        "cnpj_note_registrations": cnpj_from_notes,
        "coletas_agg_rows": len(coleta_by_coletor),
        "contratos_ativos_coletores": len(contrato_by_coletor),
        "built_at": now.isoformat(),
    }
    logger.info("labels_internal: index built %s", stats)
    return InternalLabelIndex(
        by_norm_name=by_norm_name,
        by_norm_localizacao=by_norm_localizacao,
        by_cnpj=by_cnpj,
        by_pipeline_won=by_pipeline_won,
        fechado_pipeline_ids=frozenset(fechado_pipeline_ids),
        localizacao_digit_blobs=localizacao_digit_blobs,
        stats=stats,
    )


def internal_relevance_continuous(
    signals: InternalSiteSignals,
    *,
    cnpj_match: bool = False,
) -> float:
    """Unbounded ops score: contracts > recency > volume > coleta > parceiro.

    Note: pipeline_won is outcome data and should not contribute to training labels.
    """
    score = 0.0
    if signals.parceiro_ativo:
        score += 5.0
    if cnpj_match:
        score += 12.0
    if signals.has_active_contract:
        score += 40.0 + min(signals.contract_valor_mensal / 500.0, 30.0)
    if signals.coleta_count > 0:
        score += min(signals.coleta_count * 3.0, 45.0)
    if signals.volume_total_kg > 0:
        score += min(signals.volume_total_kg / 10.0, 25.0)
    if signals.last_coleta_at:
        days = max(0, (datetime.now(timezone.utc) - signals.last_coleta_at).days)
        if days <= 30:
            score += 20.0
        elif days <= 90:
            score += 12.0
        elif days <= 365:
            score += 5.0
    return round(score, 4)


def _lookup_weak_cnpj_in_localizacao(
    cnpj: str,
    index: InternalLabelIndex,
) -> InternalSiteSignals | None:
    if not cnpj:
        return None
    for loc_digits, signals in index.localizacao_digit_blobs:
        if cnpj in loc_digits:
            return signals
    return None


def _lookup_weak_coletor_id_in_localizacao(
    cnpj: str,
    index: InternalLabelIndex,
) -> InternalSiteSignals | None:
    """Weak: CNPJ digits contain coletor id token referenced in localizacao text."""
    if not cnpj:
        return None
    for loc_digits, signals in index.localizacao_digit_blobs:
        coletor_id = signals.coletor_id
        if not coletor_id:
            continue
        cid = str(coletor_id)
        if cid in loc_digits and cid in cnpj:
            return signals
    return None


def lookup_internal_signals(
    empresa: EmpresaCandidata,
    local: LocalCandidato | None,
    index: InternalLabelIndex,
) -> tuple[InternalSiteSignals | None, str | None]:
    """Match candidate to ops index (CNPJ > names > pipeline won > weak localizacao)."""
    cnpj = normalize_cnpj(empresa.cnpj)
    if cnpj and cnpj in index.by_cnpj:
        return index.by_cnpj[cnpj], "cnpj"

    name_candidates: list[tuple[str, str]] = []
    if empresa.razao_social:
        name_candidates.append(("razao_social", normalize_org_name(empresa.razao_social)))
    if empresa.nome_fantasia:
        name_candidates.append(("nome_fantasia", normalize_org_name(empresa.nome_fantasia)))
    if local and local.endereco:
        name_candidates.append(("local_endereco", normalize_org_name(local.endereco)))

    for source, key in name_candidates:
        if not key:
            continue
        if key in index.by_norm_name:
            return index.by_norm_name[key], source
        if key in index.by_norm_localizacao:
            return index.by_norm_localizacao[key], f"{source}_localizacao"
        if key in index.by_pipeline_won:
            return index.by_pipeline_won[key], f"{source}_pipeline_won"

    weak = _lookup_weak_cnpj_in_localizacao(cnpj, index)
    if weak:
        return weak, "cnpj_in_localizacao_weak"

    weak_id = _lookup_weak_coletor_id_in_localizacao(cnpj, index)
    if weak_id:
        return weak_id, "coletor_id_in_localizacao_weak"

    return None, None


def lookup_internal_score(
    empresa: EmpresaCandidata,
    local: LocalCandidato | None,
    index: InternalLabelIndex,
    *,
    apply_crm_persisted_boost: bool = False,
) -> tuple[float | None, dict[str, Any]]:
    """Return continuous relevance and metadata when ops data matches this candidate.

    ``apply_crm_persisted_boost``: when True, adds a fixed bonus if the candidate row
    is already linked (``pipeline_id``) to a CRM pipeline in a won state. Keep False
    when this score feeds training labels to avoid outcome leakage.
    """
    signals, match_source = lookup_internal_signals(empresa, local, index)
    if not signals:
        return None, {"matched": False}

    cnpj = normalize_cnpj(empresa.cnpj)
    cnpj_match = bool(cnpj and match_source in ("cnpj", "cnpj_in_localizacao_weak"))
    logger.info(
        "labels_internal: internal match cnpj=%s source=%s coletor_id=%s parceiro_id=%s",
        cnpj or empresa.cnpj,
        match_source,
        signals.coletor_id,
        signals.parceiro_id,
    )
    score = internal_relevance_continuous(signals, cnpj_match=cnpj_match)
    meta: dict[str, Any] = {
        "matched": True,
        "match_source": match_source,
        "coletor_id": signals.coletor_id,
        "parceiro_id": signals.parceiro_id,
        "coleta_count": signals.coleta_count,
        "has_active_contract": signals.has_active_contract,
        "pipeline_won": signals.pipeline_won,
        "cnpj_match": cnpj_match,
    }
    pipeline_id = getattr(empresa, "pipeline_id", None)
    if (
        apply_crm_persisted_boost
        and pipeline_id
        and pipeline_id in index.fechado_pipeline_ids
    ):
        score = round(score + _CRM_PERSISTED_LINK_BOOST, 4)
        meta["crm_persisted_link"] = True
        meta["pipeline_id"] = pipeline_id
    return score, meta

