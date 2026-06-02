"""IBRAM/SEMA-DF — Cadastro de Geradores de Resíduos Perigosos (e-waste).

Integra dados do Instituto Brasília Ambiental (IBRAM) para identificar
empresas oficialmente cadastradas como geradoras de resíduos perigosos,
incluindo resíduos de equipamentos elétricos e eletrônicos (REEE/e-waste).

Essas empresas são leads de alta confiança: já reconhecem a obrigação legal
de destinação adequada, estão cientes das regulamentações e têm volume
suficiente para exigir cadastro formal.

Fonte: https://www.ibram.df.gov.br/
Portal de licenciamento: https://licenciamento.ibram.df.gov.br/
Dados abertos IBRAM: https://dados.df.gov.br/ (org: ibram)

IMPORTANTE: O IBRAM não expõe API REST pública estruturada. Este módulo
suporta dois modos de ingestão:
  1. CSV exportado manualmente do portal IBRAM (--file caminho.csv)
  2. Busca via CKAN DF (org=ibram) para datasets publicados

Para acesso programático, a SEMA-DF aceita solicitações via LAI (Lei de
Acesso à Informação) para exportação da base de geradores cadastrados.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata
from jobs.prospeccao import config
from jobs.prospeccao.http_util import get_json

logger = logging.getLogger(__name__)

_CKAN_BASE = config.CKAN_BASE_URL  # https://dados.df.gov.br
_IBRAM_ORG = "ibram"

# Palavras-chave para identificar datasets de resíduos no CKAN
_RESIDUO_KEYWORDS = (
    "residuo", "resíduo", "gerador", "licenciamento", "reee",
    "eletronico", "eletrônico", "perigoso",
)

# Campos esperados em CSVs do IBRAM (nomes variam)
_CNPJ_FIELDS = ("cnpj", "CNPJ", "CnpjGerador", "nr_cnpj")
_RAZAO_FIELDS = ("razao_social", "RazaoSocial", "nome", "NomeGerador")
_TIPO_RESIDUO_FIELDS = ("tipo_residuo", "TipoResiduo", "ClasseResiduos", "codigo_residuo")
_ENDERECO_FIELDS = ("endereco", "Endereco", "logradouro", "Logradouro")


def _clean_cnpj(raw: str | None) -> str:
    if not raw:
        return ""
    return "".join(c for c in str(raw) if c.isdigit())


def _find_col(header: list[str], candidates: tuple[str, ...]) -> int | None:
    for name in candidates:
        for i, col in enumerate(header):
            if col.strip().lower() == name.lower():
                return i
    return None


def _is_eletronico_residuo(tipo: str | None) -> bool:
    if not tipo:
        return False
    t = tipo.lower()
    return any(kw in t for kw in ("eletro", "reee", "equipamento", "informatica", "bateria", "pilha"))


# ---------------------------------------------------------------------------
# CKAN discovery
# ---------------------------------------------------------------------------

def _search_ibram_ckan_datasets() -> list[dict]:
    """Busca datasets do IBRAM no CKAN DF."""
    try:
        result = get_json(
            f"{_CKAN_BASE}/api/3/action/package_search",
            params={"q": f"organization:{_IBRAM_ORG} residuo", "rows": 20},
            timeout=30,
        )
        datasets = result.get("result", {}).get("results", [])
        logger.info("IBRAM CKAN: %d datasets encontrados para org=%s", len(datasets), _IBRAM_ORG)
        return datasets
    except Exception as exc:
        logger.warning("IBRAM CKAN search falhou: %s", exc)
        return []


def _find_best_resource_url(datasets: list[dict]) -> str | None:
    for ds in datasets:
        name = ds.get("name", "").lower()
        title = ds.get("title", "").lower()
        if not any(kw in name + title for kw in _RESIDUO_KEYWORDS):
            continue
        for r in ds.get("resources", []):
            if r.get("format", "").upper() in ("CSV", "XLS", "XLSX") and r.get("url"):
                logger.info(
                    "IBRAM dataset selecionado: '%s' — %s",
                    ds.get("title", "?"),
                    r["url"][:80],
                )
                return r["url"]
    return None


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_ibram_csv(raw: bytes, encoding: str = "utf-8") -> list[dict[str, str]]:
    for enc in (encoding, "latin-1", "utf-8-sig"):
        try:
            text = raw.decode(enc, errors="strict")
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            return list(reader)
        except UnicodeDecodeError:
            continue
    text = raw.decode("latin-1", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def _load_csv_file(path: Path) -> list[dict[str, str]]:
    return _parse_ibram_csv(path.read_bytes())


# ---------------------------------------------------------------------------
# DB sync
# ---------------------------------------------------------------------------

def _mark_empresa_ibram(
    empresa: EmpresaCandidata,
    tipo_residuo: str,
    is_eletronico: bool,
) -> None:
    tag = "IBRAM:eletronico" if is_eletronico else "IBRAM:perigoso"
    if empresa.natureza_juridica and tag in empresa.natureza_juridica:
        return
    empresa.natureza_juridica = (
        f"{empresa.natureza_juridica or ''} [{tag}:{tipo_residuo[:40]}]".strip()
    )


def sync_ibram_geradores(
    db: Session,
    *,
    csv_path: Path | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Importa cadastro de geradores de resíduos do IBRAM.

    Modos:
      - csv_path: Arquivo CSV exportado manualmente do portal IBRAM
      - url: URL direta de um recurso CSV/XLS publicado
      - Sem args: Tenta descobrir via CKAN DF (org=ibram)

    Empresas encontradas recebem marcação no campo natureza_juridica:
      [IBRAM:eletronico] — confirma geração de e-waste
      [IBRAM:perigoso]   — resíduo perigoso genérico

    Returns:
        Stats dict com contagens de registros e matches.
    """
    stats: dict[str, Any] = {
        "registros_ibram": 0,
        "cnpjs_extraidos": 0,
        "empresas_encontradas": 0,
        "marcadas_eletronico": 0,
        "marcadas_perigoso": 0,
        "fonte": None,
    }

    records: list[dict[str, str]] = []

    if csv_path and csv_path.exists():
        logger.info("IBRAM: carregando CSV local %s", csv_path.name)
        records = _load_csv_file(csv_path)
        stats["fonte"] = str(csv_path.name)

    elif url:
        from jobs.prospeccao.http_util import session as http_session
        logger.info("IBRAM: baixando %s", url[:100])
        try:
            resp = http_session().get(url, timeout=(15, 60))
            resp.raise_for_status()
            records = _parse_ibram_csv(resp.content)
            stats["fonte"] = url
        except Exception as exc:
            logger.error("IBRAM download falhou: %s", exc)
            stats["erro"] = str(exc)
            return stats

    else:
        # Descoberta automática via CKAN
        datasets = _search_ibram_ckan_datasets()
        discovered_url = _find_best_resource_url(datasets)
        if discovered_url:
            from jobs.prospeccao.http_util import session as http_session
            try:
                resp = http_session().get(discovered_url, timeout=(15, 60))
                resp.raise_for_status()
                records = _parse_ibram_csv(resp.content)
                stats["fonte"] = discovered_url
            except Exception as exc:
                logger.warning("IBRAM auto-download falhou: %s", exc)
        else:
            logger.warning(
                "IBRAM: nenhum dataset encontrado no CKAN DF. "
                "Use --file ou solicite os dados via LAI (ibram.df.gov.br). "
                "Defina TRONIK_IBRAM_GERADORES_URL para apontar diretamente."
            )
            stats["aviso"] = (
                "Dataset IBRAM não disponível automaticamente. "
                "Exporte manualmente em https://licenciamento.ibram.df.gov.br/ "
                "ou solicite via LAI e use: brasilapi-enrich --file caminho.csv"
            )
            return stats

    stats["registros_ibram"] = len(records)
    if not records:
        logger.warning("IBRAM: nenhum registro lido")
        return stats

    header = list(records[0].keys())
    col_cnpj = _find_col(header, _CNPJ_FIELDS)
    col_tipo = _find_col(header, _TIPO_RESIDUO_FIELDS)

    if col_cnpj is None:
        logger.error("IBRAM: coluna CNPJ não encontrada. Colunas: %s", header[:15])
        stats["erro"] = "Coluna CNPJ não encontrada"
        return stats

    cnpj_index: dict[str, str] = {}
    for row in records:
        vals = list(row.values())
        cnpj = _clean_cnpj(vals[col_cnpj])
        if len(cnpj) != 14:
            continue
        tipo = vals[col_tipo].strip() if col_tipo is not None else "residuo_perigoso"
        cnpj_index[cnpj] = tipo

    stats["cnpjs_extraidos"] = len(cnpj_index)

    # Cruzar com banco em batches
    cnpjs_list = list(cnpj_index.keys())
    for i in range(0, len(cnpjs_list), 500):
        batch = cnpjs_list[i : i + 500]
        empresas = (
            db.query(EmpresaCandidata)
            .filter(EmpresaCandidata.cnpj.in_(batch))
            .all()
        )
        stats["empresas_encontradas"] += len(empresas)
        for empresa in empresas:
            cnpj = _clean_cnpj(empresa.cnpj)
            tipo = cnpj_index.get(cnpj, "")
            is_eletro = _is_eletronico_residuo(tipo)
            _mark_empresa_ibram(empresa, tipo or "residuo_perigoso", is_eletro)
            if is_eletro:
                stats["marcadas_eletronico"] += 1
            else:
                stats["marcadas_perigoso"] += 1

    db.flush()
    logger.info("IBRAM sync concluído: %s", stats)
    return stats
