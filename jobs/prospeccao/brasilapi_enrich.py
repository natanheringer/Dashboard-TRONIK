"""Enrich empresa_candidata via Brasil API (free, no auth required).

Fills phone, email and secondary CNAE gaps for companies that Receita Federal
or Casa dos Dados did not provide contact data for. Rate-limited to ~2.5 req/s
by default to stay well within the free tier.

Docs: https://brasilapi.com.br/docs#tag/CNPJ
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata
from jobs.prospeccao import config
from jobs.prospeccao.http_util import session as http_session

logger = logging.getLogger(__name__)

_BRASILAPI_CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
_DEFAULT_SLEEP_S = 0.4   # ~2.5 req/s — safe for free tier
_MAX_RATE_LIMIT_RETRIES = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_cnpj(raw: str) -> str:
    return "".join(c for c in raw if c.isdigit())


def _fetch_cnpj(cnpj: str) -> dict[str, Any] | None:
    """Query Brasil API for one CNPJ. Returns dict or None on miss/error."""
    url = _BRASILAPI_CNPJ_URL.format(cnpj=cnpj)
    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            resp = http_session().get(url, timeout=(10, 30))
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = 2 ** attempt * 3
                logger.warning(
                    "Brasil API rate-limited — aguardando %ds (tentativa %d/%d)",
                    wait, attempt + 1, _MAX_RATE_LIMIT_RETRIES,
                )
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None  # CNPJ not in Brasil API — normal for very old CNPJs
            logger.debug("Brasil API HTTP %s para CNPJ %s", resp.status_code, cnpj)
            return None
        except Exception as exc:
            logger.debug("Brasil API request failed para %s: %s", cnpj, exc)
            return None
    return None


def _extract_email(data: dict[str, Any]) -> str | None:
    raw = (data.get("email") or "").strip().lower()
    if raw and "@" in raw and "." in raw.rsplit("@", 1)[-1]:
        return raw
    return None


def _extract_telefone(data: dict[str, Any]) -> str | None:
    for field in ("ddd_telefone_1", "ddd_telefone_2"):
        raw = (data.get(field) or "").strip()
        if raw and len("".join(c for c in raw if c.isdigit())) >= 8:
            return raw
    return None


def _extract_cnae_secundarios(data: dict[str, Any]) -> str | None:
    entries = data.get("cnaes_secundarios") or []
    if not entries:
        return None
    seen: set[str] = set()
    codes: list[str] = []
    for entry in entries:
        digits = "".join(c for c in str(entry.get("codigo") or "") if c.isdigit())
        if len(digits) >= 4 and digits not in seen:
            seen.add(digits)
            codes.append(digits)
    return json.dumps(codes, ensure_ascii=False) if codes else None


def _extract_natureza_juridica(data: dict[str, Any]) -> str | None:
    return (data.get("descricao_natureza_juridica") or "").strip() or None


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------

def enrich_via_brasilapi(
    db: Session,
    *,
    batch_size: int = 500,
    sleep_s: float | None = None,
    only_missing_contact: bool = True,
) -> dict[str, Any]:
    """Enrich EmpresaCandidata records with Brasil API data.

    Args:
        batch_size: Max CNPJs to query per run (keeps runtime predictable).
        sleep_s: Pause between requests. Defaults to BRASILAPI_SLEEP_S env var
                 or 0.4s (~2.5 req/s, safe for free tier).
        only_missing_contact: When True, only queries companies that are
                              missing email OR phone — skips already-rich records.

    Returns:
        Stats dict with counts of enriched fields and API outcomes.
    """
    pause = sleep_s if sleep_s is not None else float(
        getattr(config, "BRASILAPI_SLEEP_S", _DEFAULT_SLEEP_S)
    )

    query = db.query(EmpresaCandidata)
    if only_missing_contact:
        query = query.filter(
            or_(
                EmpresaCandidata.email.is_(None),
                EmpresaCandidata.telefone.is_(None),
            )
        )
    empresas = query.limit(batch_size).all()

    stats: dict[str, Any] = {
        "candidatas": len(empresas),
        "consultadas": 0,
        "enriquecidas_email": 0,
        "enriquecidas_telefone": 0,
        "enriquecidas_cnae_sec": 0,
        "enriquecidas_natureza_juridica": 0,
        "nao_encontradas": 0,
        "cnpj_invalido": 0,
    }

    logger.info(
        "Brasil API enrich: %d empresas candidatas (batch=%d sleep=%.2fs)",
        len(empresas), batch_size, pause,
    )

    for empresa in empresas:
        cnpj = _clean_cnpj(empresa.cnpj or "")
        if len(cnpj) != 14:
            stats["cnpj_invalido"] += 1
            continue

        data = _fetch_cnpj(cnpj)
        stats["consultadas"] += 1

        if data is None:
            stats["nao_encontradas"] += 1
            time.sleep(pause)
            continue

        # Merge inteligente: nunca sobrescreve dado existente com None/vazio
        novo_email = _extract_email(data)
        if novo_email and not empresa.email:
            empresa.email = novo_email
            stats["enriquecidas_email"] += 1

        novo_tel = _extract_telefone(data)
        if novo_tel and not empresa.telefone:
            empresa.telefone = novo_tel
            stats["enriquecidas_telefone"] += 1

        novo_cnae_sec = _extract_cnae_secundarios(data)
        if novo_cnae_sec and not empresa.cnae_secundarios_json:
            empresa.cnae_secundarios_json = novo_cnae_sec
            stats["enriquecidas_cnae_sec"] += 1

        nova_natureza = _extract_natureza_juridica(data)
        if nova_natureza and not empresa.natureza_juridica:
            empresa.natureza_juridica = nova_natureza
            stats["enriquecidas_natureza_juridica"] += 1

        time.sleep(pause)

    db.flush()
    logger.info("Brasil API enrich concluído: %s", stats)
    return stats
