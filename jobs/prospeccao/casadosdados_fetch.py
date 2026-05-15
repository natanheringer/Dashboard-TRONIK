"""Targeted CNPJ fetch via Casa dos Dados v5 API.

Requires an API key (set TRONIK_CASADOSDADOS_API_KEY env var).
Get yours at https://portal.casadosdados.com.br/plataforma/api/chave

Fetches in proximity order from sede (Recanto das Emas):
  Tier 1 → adjacent RAs (Samambaia, Riacho Fundo II …)
  Tier 2 → nearby RAs (Taguatinga, Ceilândia, Gama …)
  Tier 3 → rest of DF
  Tier 4 → inner ring Entorno (Valparaíso, Novo Gama …)
  Tier 5 → outer ring Entorno
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato
from jobs.prospeccao import config
from jobs.prospeccao.http_util import session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _ensure_api_key() -> str:
    key = config.CASADOSDADOS_API_KEY
    if not key:
        raise RuntimeError(
            "TRONIK_CASADOSDADOS_API_KEY not set. "
            "Get your key at https://portal.casadosdados.com.br/plataforma/api/chave\n"
            "Then: $env:TRONIK_CASADOSDADOS_API_KEY = 'your-key-here'"
        )
    return key


def _search_page(
    api_key: str,
    *,
    uf: str,
    municipio: str = "",
    bairro: str = "",
    situacao_cadastral: list[str] | None = None,
    pagina: int = 1,
    limite: int | None = None,
) -> dict[str, Any]:
    """POST one page to Casa dos Dados v5 CNPJ search API."""
    body: dict[str, Any] = {
        "uf": [uf],
        "situacao_cadastral": situacao_cadastral or ["ATIVA"],
        "pagina": pagina,
        "limite": limite or config.CASADOSDADOS_LIMIT_PER_PAGE,
    }
    if municipio:
        body["municipio"] = [municipio]
    if bairro:
        body["bairro"] = [bairro]

    resp = session().post(
        config.CASADOSDADOS_API_BASE,
        json=body,
        headers={"api-key": api_key},
        timeout=(config.HTTP_CONNECT_TIMEOUT_S, config.HTTP_READ_TIMEOUT_S),
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_all_pages(
    api_key: str,
    *,
    uf: str,
    municipio: str = "",
    bairro: str = "",
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Paginate through all results for a single query."""
    max_pg = max_pages or config.CASADOSDADOS_MAX_PAGES_PER_QUERY
    all_results: list[dict[str, Any]] = []
    label = bairro or municipio or uf

    for page in range(1, max_pg + 1):
        try:
            data = _search_page(api_key, uf=uf, municipio=municipio, bairro=bairro, pagina=page)
        except Exception:
            logger.exception("API error at page %d for %s", page, label)
            break

        results = data.get("cnpjs", [])
        if not results:
            break

        all_results.extend(results)
        total = data.get("total", "?")

        if page == 1:
            logger.info("Query %s: %s total results (fetching up to %d pages)", label, total, max_pg)

        if page % 10 == 0:
            logger.info("  %s page %d: %d results so far", label, page, len(all_results))

        if len(results) < config.CASADOSDADOS_LIMIT_PER_PAGE:
            break

        time.sleep(config.CASADOSDADOS_PAGE_SLEEP_S)

    logger.info("Query %s: fetched %d results", label, len(all_results))
    return all_results


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

def _build_fetch_plan(tiers: str = "all") -> list[dict[str, str]]:
    """Build ordered list of {uf, municipio, bairro} queries by proximity tier."""
    plan: list[dict[str, str]] = []

    tier_map = {
        "t1": config.SEDE_TIER_1,
        "t2": config.SEDE_TIER_2,
        "t3": config.SEDE_TIER_3,
    }

    inner_names = [
        config.RIDE_ENTORNO_MUNICIPIOS[code]
        for code in config.ENTORNO_INNER_RING
    ]
    outer_names = [
        name for code, name in config.RIDE_ENTORNO_MUNICIPIOS.items()
        if code not in config.ENTORNO_INNER_RING
    ]

    requested = set(t.strip() for t in tiers.lower().split(","))
    do_all = "all" in requested
    do_df = "df" in requested or do_all

    for tier_key in ("t1", "t2", "t3"):
        if do_df or do_all or tier_key in requested:
            for bairro in tier_map[tier_key]:
                plan.append({"uf": "DF", "municipio": "BRASILIA", "bairro": bairro})

    if do_all or "t4" in requested:
        for muni in inner_names:
            plan.append({"uf": "GO", "municipio": muni.upper(), "bairro": ""})

    if do_all or "t5" in requested:
        for muni in outer_names:
            plan.append({"uf": "GO", "municipio": muni.upper(), "bairro": ""})

    return plan


# ---------------------------------------------------------------------------
# Record -> DB (v5 response schema)
# ---------------------------------------------------------------------------

def _clean_cnpj(raw: str) -> str:
    return raw.replace(".", "").replace("/", "").replace("-", "").strip()


def _normalize_cep(cep: str | None) -> str | None:
    """Normaliza e valida CEP: remove caracteres não-dígitos, retorna None se inválido."""
    if not cep:
        return None
    cep_clean = "".join(c for c in cep if c.isdigit())
    if len(cep_clean) != 8:
        logger.debug("CEP inválido (comprimento != 8): %s → %s", cep, cep_clean)
        return None
    return cep_clean


def _upsert_from_record(db: Session, rec: dict[str, Any]) -> tuple[bool, bool]:
    """Upsert one v5 API record into empresa_candidata + local_candidato.

    Implementa merge inteligente: não sobrescreve campos válidos da Receita com None.
    """
    cnpj = _clean_cnpj(str(rec.get("cnpj", "")))
    if not cnpj or len(cnpj) < 8:
        return False, False

    endereco = rec.get("endereco", {}) or {}
    sit = rec.get("situacao_cadastral", {}) or {}
    porte_obj = rec.get("porte_empresa", {}) or {}
    ibge_data = endereco.get("ibge", {}) or {}

    empresa = db.query(EmpresaCandidata).filter_by(cnpj=cnpj).first()
    is_new_empresa = empresa is None
    if is_new_empresa:
        empresa = EmpresaCandidata(
            cnpj=cnpj,
            razao_social=rec.get("razao_social", cnpj),
            origem="casadosdados",
        )
        db.add(empresa)
        logger.debug("Empresa criada via Casa dos Dados: CNPJ=%s", cnpj)
    else:
        logger.debug("Empresa existente enriquecida via Casa dos Dados: CNPJ=%s", cnpj)

    empresa.razao_social = rec.get("razao_social") or empresa.razao_social
    empresa.nome_fantasia = rec.get("nome_fantasia") or empresa.nome_fantasia
    empresa.situacao_cadastral = sit.get("situacao_cadastral") or empresa.situacao_cadastral
    empresa.porte = porte_obj.get("descricao") or empresa.porte
    empresa.natureza_juridica = rec.get("descricao_natureza_juridica") or empresa.natureza_juridica

    data_abertura = rec.get("data_abertura")
    if data_abertura:
        try:
            if isinstance(data_abertura, str) and len(data_abertura) >= 10:
                empresa.data_abertura = datetime.strptime(data_abertura[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    bairro = (endereco.get("bairro") or "").strip()
    empresa.bairro = bairro or empresa.bairro

    # Normalizar e validar CEP
    cep_novo = _normalize_cep(endereco.get("cep"))
    empresa.cep = cep_novo or empresa.cep

    empresa.uf = (endereco.get("uf") or "").strip().upper() or empresa.uf
    empresa.municipio = (endereco.get("municipio") or "").strip() or empresa.municipio

    logradouro = (endereco.get("logradouro") or "").strip()
    tipo_logr = (endereco.get("tipo_logradouro") or "").strip()
    numero = (endereco.get("numero") or "").strip()
    complemento = (endereco.get("complemento") or "").strip()
    parts = [p for p in [tipo_logr, logradouro, numero, complemento] if p]
    full_addr = " ".join(parts)
    if bairro:
        full_addr += f", {bairro}"
    empresa.endereco_normalizado = full_addr or empresa.endereco_normalizado

    # Merge inteligente: campos de contato e CNAE secundária
    # Não sobrescrever com None/vazio se já tem valor (provavelmente da Receita)
    novo_email = rec.get("email", "").strip() if rec.get("email") else None
    empresa.email = novo_email or empresa.email

    novo_telefone = rec.get("telefone", "").strip() if rec.get("telefone") else None
    empresa.telefone = novo_telefone or empresa.telefone

    novo_cnae_sec = rec.get("cnae_secundarios_json") or rec.get("cnaes_secundarias")
    if novo_cnae_sec:
        empresa.cnae_secundarios_json = novo_cnae_sec

    # Marcar origem: se é nova, vem de Casa dos Dados; se é enriquecimento, deixar como está
    if is_new_empresa:
        empresa.origem = "casadosdados"

    db.flush()

    # local_candidato
    existing_local = (
        db.query(LocalCandidato)
        .filter_by(empresa_id=empresa.id, origem="casadosdados")
        .first()
    )
    is_new_local = existing_local is None
    local = existing_local or LocalCandidato(
        empresa_id=empresa.id,
        origem="casadosdados",
    )

    local.endereco = full_addr or local.endereco
    local.bairro = bairro or local.bairro
    local.cep = empresa.cep

    lat = ibge_data.get("latitude")
    lon = ibge_data.get("longitude")
    if lat and lon:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            if -180 <= lon_f <= 180 and -90 <= lat_f <= 90:
                local.latitude = lat_f
                local.longitude = lon_f
                local.geocode_quality = 0.9
                logger.debug("Coordenadas IBGE validadas e setadas: CNPJ=%s, lat=%.4f, lon=%.4f", cnpj, lat_f, lon_f)
            else:
                logger.warning("Coordenadas IBGE fora do intervalo válido: CNPJ=%s, lat=%.4f, lon=%.4f", cnpj, lat_f, lon_f)
        except (ValueError, TypeError) as e:
            logger.debug("Erro ao converter coordenadas IBGE para float: CNPJ=%s, erro=%s", cnpj, e)
    else:
        logger.debug("Coordenadas IBGE ausentes ou incompletas: CNPJ=%s", cnpj)

    if is_new_local:
        db.add(local)

    return is_new_empresa, is_new_local


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fetch_targeted(
    db: Session,
    *,
    tiers: str = "all",
    max_pages_per_query: int | None = None,
) -> dict[str, Any]:
    """Fetch DF + Entorno candidates from Casa dos Dados API, prioritized by proximity.

    tiers: comma-separated tier selection
      "all"        — full pipeline (t1 through t5)
      "df"         — all DF tiers (t1+t2+t3)
      "t1"         — only adjacent to sede
      "t1,t2"      — sede + nearby
    """
    api_key = _ensure_api_key()
    plan = _build_fetch_plan(tiers)
    logger.info("Fetch plan: %d queries across tiers=%s", len(plan), tiers)

    stats: dict[str, Any] = {
        "queries_run": 0,
        "total_api_results": 0,
        "empresas_created": 0,
        "empresas_updated": 0,
        "locais_created": 0,
        "tier_breakdown": {},
        "errors": [],
    }

    batch_count = 0

    for i, query in enumerate(plan):
        label = query.get("bairro") or query.get("municipio") or query["uf"]
        tier_label = _tier_label_for(query)

        try:
            results = _fetch_all_pages(
                api_key,
                uf=query["uf"],
                municipio=query.get("municipio", ""),
                bairro=query.get("bairro", ""),
                max_pages=max_pages_per_query,
            )
        except Exception as e:
            logger.exception("Failed query %s", label)
            stats["errors"].append({"query": label, "error": str(e)})
            continue

        stats["queries_run"] += 1
        stats["total_api_results"] += len(results)

        new_emp = 0
        new_loc = 0
        for rec in results:
            is_new_e, is_new_l = _upsert_from_record(db, rec)
            if is_new_e:
                new_emp += 1
            if is_new_l:
                new_loc += 1
            batch_count += 1
            if batch_count >= 200:
                db.flush()
                batch_count = 0

        stats["empresas_created"] += new_emp
        stats["empresas_updated"] += len(results) - new_emp
        stats["locais_created"] += new_loc
        stats["tier_breakdown"][label] = {
            "api_results": len(results),
            "new_empresas": new_emp,
            "new_locais": new_loc,
            "tier": tier_label,
        }

        logger.info(
            "[%d/%d] %s: %d results, +%d empresas, +%d locais",
            i + 1, len(plan), label, len(results), new_emp, new_loc,
        )

    if batch_count:
        db.flush()

    db.commit()
    logger.info("Targeted fetch complete: %s", {k: v for k, v in stats.items() if k != "tier_breakdown"})
    return stats


def _tier_label_for(query: dict[str, str]) -> str:
    bairro = query.get("bairro", "")
    if bairro and bairro in config.SEDE_TIER_1:
        return "t1"
    if bairro and bairro in config.SEDE_TIER_2:
        return "t2"
    if bairro and bairro in config.SEDE_TIER_3:
        return "t3"
    if query["uf"] == "GO":
        muni = query.get("municipio", "").strip().upper()
        inner_upper = {
            config.RIDE_ENTORNO_MUNICIPIOS[c].upper() for c in config.ENTORNO_INNER_RING
        }
        if muni in inner_upper:
            return "t4"
        return "t5"
    return "df"
