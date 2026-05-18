"""Parse Receita Federal CNPJ ZIPs into empresa_candidata + local_candidato.

Streaming CSV reader: processes multi-GB files one row at a time.
Filters to DF + RIDE Entorno (GO) at parse time.

Expected raw files in data/raw/prospeccao/receita_cnpj/:
  Empresas0.zip … Empresas9.zip
  Estabelecimentos0.zip … Estabelecimentos9.zip
  Municipios.zip, Cnaes.zip, Naturezas.zip
"""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato
from jobs.prospeccao import config

logger = logging.getLogger(__name__)

RECEITA_DIR_KEY = "receita"

# Column indices for Estabelecimentos CSV (no header, semicolon-separated, latin-1)
class _Est:
    CNPJ_BASICO = 0
    CNPJ_ORDEM = 1
    CNPJ_DV = 2
    MATRIZ_FILIAL = 3
    NOME_FANTASIA = 4
    SITUACAO_CADASTRAL = 5
    DATA_SITUACAO = 6
    MOTIVO_SITUACAO = 7
    CIDADE_EXTERIOR = 8
    CODIGO_PAIS = 9
    DATA_INICIO = 10
    CNAE_PRINCIPAL = 11
    CNAE_SECUNDARIA = 12
    TIPO_LOGRADOURO = 13
    LOGRADOURO = 14
    NUMERO = 15
    COMPLEMENTO = 16
    BAIRRO = 17
    CEP = 18
    UF = 19
    CODIGO_MUNICIPIO = 20
    DDD1 = 21
    TELEFONE1 = 22
    DDD2 = 23
    TELEFONE2 = 24
    DDD_FAX = 25
    FAX = 26
    EMAIL = 27
    SITUACAO_ESPECIAL = 28
    DATA_SITUACAO_ESPECIAL = 29


# Column indices for Empresas CSV
class _Emp:
    CNPJ_BASICO = 0
    RAZAO_SOCIAL = 1
    NATUREZA_JURIDICA = 2
    QUALIFICACAO_RESP = 3
    CAPITAL_SOCIAL = 4
    PORTE = 5
    ENTE_FEDERATIVO = 6


# ---------------------------------------------------------------------------
# Lookup table parsers
# ---------------------------------------------------------------------------

def _iter_csv_in_zip(zip_path: Path) -> Iterator[list[str]]:
    """Yield rows from the first CSV inside a ZIP (latin-1, semicolon).

    NOTE: Uses errors='replace' for encoding issues. A warning is logged if
    encoding replacement occurs, as it may indicate data quality issues.
    """
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.startswith("__MACOSX")]
        if not names:
            return
        with zf.open(names[0]) as raw:
            reader = csv.reader(
                io.TextIOWrapper(raw, encoding=config.RECEITA_CSV_ENCODING, errors="replace"),
                delimiter=config.RECEITA_CSV_SEPARATOR,
            )
            yield from reader
    # Log warning about encoding replacement
    logger.warning(
        "File %s processed with encoding error replacement — check for data quality issues",
        zip_path.name,
    )


def parse_municipios_lookup(receita_dir: Path) -> dict[str, tuple[str, str]]:
    """Build {receita_code: (name, receita_code)} from Municipios.zip.

    The Receita municipal code is NOT the IBGE code. The mapping to IBGE
    requires the Tesouro Nacional TABMUN.csv. For now we store the Receita
    code and the municipality name, which is enough for DF/Entorno filtering.
    """
    path = receita_dir / "Municipios.zip"
    if not path.exists():
        logger.warning("Municipios.zip not found at %s", path)
        return {}
    lookup: dict[str, str] = {}
    for row in _iter_csv_in_zip(path):
        if len(row) >= 2:
            lookup[row[0].strip()] = row[1].strip()
    logger.info("Municipios lookup: %d entries", len(lookup))
    return lookup


def parse_cnaes_lookup(receita_dir: Path) -> dict[str, str]:
    """Build {cnae_code: description} from Cnaes.zip."""
    path = receita_dir / "Cnaes.zip"
    if not path.exists():
        logger.warning("Cnaes.zip not found at %s", path)
        return {}
    lookup: dict[str, str] = {}
    for row in _iter_csv_in_zip(path):
        if len(row) >= 2:
            lookup[row[0].strip()] = row[1].strip()
    logger.info("Cnaes lookup: %d entries", len(lookup))
    return lookup


def parse_naturezas_lookup(receita_dir: Path) -> dict[str, str]:
    """Build {natureza_code: description} from Naturezas.zip."""
    path = receita_dir / "Naturezas.zip"
    if not path.exists():
        return {}
    lookup: dict[str, str] = {}
    for row in _iter_csv_in_zip(path):
        if len(row) >= 2:
            lookup[row[0].strip()] = row[1].strip()
    logger.info("Naturezas lookup: %d entries", len(lookup))
    return lookup


# ---------------------------------------------------------------------------
# Empresas loader (keyed by cnpj_basico)
# ---------------------------------------------------------------------------

def load_empresas_dict(receita_dir: Path) -> dict[str, dict[str, str]]:
    """Stream all Empresas*.zip and build {cnpj_basico: {razao_social, porte, natureza, ...}}.

    Only loads DF-relevant entries? No -- we cannot filter here because
    the UF lives in Estabelecimentos, not Empresas. We load all into memory
    (dict of small dicts). For ~60M companies this is ~8-12 GB RAM.

    To keep memory bounded, we only store the fields we actually need.
    """
    empresas: dict[str, dict[str, str]] = {}
    for i in range(10):
        path = receita_dir / f"Empresas{i}.zip"
        if not path.exists():
            logger.debug("Empresas%d.zip not found, skipping", i)
            continue
        count = 0
        for row in _iter_csv_in_zip(path):
            if len(row) < 6:
                continue
            basico = row[_Emp.CNPJ_BASICO].strip()
            empresas[basico] = {
                "razao_social": row[_Emp.RAZAO_SOCIAL].strip(),
                "natureza_juridica": row[_Emp.NATUREZA_JURIDICA].strip(),
                "porte": row[_Emp.PORTE].strip(),
                "capital_social": row[_Emp.CAPITAL_SOCIAL].strip(),
            }
            count += 1
        logger.info("Empresas%d.zip: %d rows loaded", i, count)
    logger.info("Total empresas in memory: %d", len(empresas))
    return empresas


def load_empresas_dict_filtered(
    receita_dir: Path,
    needed_basicos: set[str],
) -> dict[str, dict[str, str]]:
    """Memory-efficient: only load empresa rows whose cnpj_basico is in needed_basicos."""
    empresas: dict[str, dict[str, str]] = {}
    for i in range(10):
        path = receita_dir / f"Empresas{i}.zip"
        if not path.exists():
            continue
        for row in _iter_csv_in_zip(path):
            if len(row) < 6:
                continue
            basico = row[_Emp.CNPJ_BASICO].strip()
            if basico in needed_basicos:
                empresas[basico] = {
                    "razao_social": row[_Emp.RAZAO_SOCIAL].strip(),
                    "natureza_juridica": row[_Emp.NATUREZA_JURIDICA].strip(),
                    "porte": row[_Emp.PORTE].strip(),
                    "capital_social": row[_Emp.CAPITAL_SOCIAL].strip(),
                }
    logger.info("Filtered empresas loaded: %d of %d needed", len(empresas), len(needed_basicos))
    return empresas


# ---------------------------------------------------------------------------
# UF/RIDE filter
# ---------------------------------------------------------------------------

_RIDE_MUNICIPIO_NAMES_LOWER: set[str] = {
    name.lower() for name in config.RIDE_ENTORNO_MUNICIPIOS.values()
}


def _is_target_uf(uf: str) -> bool:
    return uf in ("DF", "GO")


def _is_ride_municipio(municipio_name: str) -> bool:
    return municipio_name.strip().lower() in _RIDE_MUNICIPIO_NAMES_LOWER


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw or raw == "00000000" or len(raw) < 8:
        return None
    try:
        return datetime.strptime(raw[:8], "%Y%m%d")
    except ValueError:
        return None


def _format_phone(ddd: str, tel: str) -> str | None:
    ddd = ddd.strip()
    tel = tel.strip()
    if not tel:
        return None
    if ddd:
        return f"({ddd}) {tel}"
    return tel


def _parse_secondary_cnaes(raw: str) -> list[str]:
    """Comma-separated CNAE codes in a single field.

    Validates digits only, deduplicates, and ignores invalid entries (< 4 digits).
    """
    if not raw or not raw.strip():
        return []
    seen: set[str] = set()
    result: list[str] = []
    for part in raw.split(","):
        c = "".join(ch for ch in part if ch.isdigit())
        if len(c) >= 4 and c not in seen:
            seen.add(c)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Two-pass pipeline
# ---------------------------------------------------------------------------

def _build_address(row: list[str]) -> str:
    parts = []
    tipo = row[_Est.TIPO_LOGRADOURO].strip()
    logr = row[_Est.LOGRADOURO].strip()
    num = row[_Est.NUMERO].strip()
    compl = row[_Est.COMPLEMENTO].strip()
    bairro = row[_Est.BAIRRO].strip()
    if tipo:
        parts.append(tipo)
    if logr:
        parts.append(logr)
    if num:
        parts.append(num)
    if compl:
        parts.append(f"- {compl}")
    addr = " ".join(parts)
    if bairro:
        addr += f", {bairro}"
    return addr or None


def parse_estabelecimentos_to_db(
    db: Session,
    receita_dir: Path,
    *,
    municipios_lookup: dict[str, str] | None = None,
    naturezas_lookup: dict[str, str] | None = None,
    two_pass: bool = True,
) -> dict[str, Any]:
    """Parse Estabelecimentos ZIPs, filter DF+RIDE, join Empresas, write DB rows.

    Two-pass approach (default, memory-efficient):
      Pass 1: scan Estabelecimentos to collect cnpj_basicos for DF+RIDE rows
      Pass 2: load only needed Empresas, then re-scan Estabelecimentos and write DB rows

    Set two_pass=False to load ALL Empresas into memory first (faster but ~12 GB RAM).
    """
    muni = municipios_lookup or parse_municipios_lookup(receita_dir)
    natj = naturezas_lookup or parse_naturezas_lookup(receita_dir)

    stats: dict[str, Any] = {
        "empresas_created": 0,
        "empresas_updated": 0,
        "locais_created": 0,
        "total_rows_scanned": 0,
        "rows_filtered_in": 0,
        "rows_skipped_uf": 0,
        "rows_skipped_go_not_ride": 0,
        "rows_df": 0,
        "rows_go_ride": 0,
        "files_processed": 0,
    }

    # --- Pass 1: collect needed cnpj_basicos ---
    needed_basicos: set[str] = set()
    if two_pass:
        logger.info("Pass 1: scanning Estabelecimentos for DF+RIDE rows")
        for i in range(10):
            path = receita_dir / f"Estabelecimentos{i}.zip"
            if not path.exists():
                continue
            for row in _iter_csv_in_zip(path):
                if len(row) <= _Est.EMAIL:
                    continue
                uf = row[_Est.UF].strip().upper()
                if not _is_target_uf(uf):
                    continue
                if uf == "GO":
                    muni_code = row[_Est.CODIGO_MUNICIPIO].strip()
                    muni_name = muni.get(muni_code, "")
                    if not _is_ride_municipio(muni_name):
                        continue
                needed_basicos.add(row[_Est.CNPJ_BASICO].strip())
        logger.info("Pass 1 done: %d unique cnpj_basicos in DF+RIDE", len(needed_basicos))

    # --- Load Empresas ---
    if two_pass and needed_basicos:
        empresas = load_empresas_dict_filtered(receita_dir, needed_basicos)
    elif not two_pass:
        empresas = load_empresas_dict(receita_dir)
    else:
        empresas = {}

    # --- Pass 2: parse + write ---
    logger.info("Pass 2: parsing Estabelecimentos and writing to DB")
    batch_size = 500
    pending = 0

    for i in range(10):
        path = receita_dir / f"Estabelecimentos{i}.zip"
        if not path.exists():
            continue
        stats["files_processed"] += 1
        for row in _iter_csv_in_zip(path):
            stats["total_rows_scanned"] += 1
            if len(row) <= _Est.EMAIL:
                cnpj_temp = row[_Est.CNPJ_BASICO].strip() if row and len(row) > _Est.CNPJ_BASICO else "unknown"
                logger.debug(
                    "Row too short (%d fields, need %d), skipping CNPJ=%s",
                    len(row), _Est.EMAIL + 1, cnpj_temp,
                )
                continue

            uf = row[_Est.UF].strip().upper()
            if not _is_target_uf(uf):
                stats["rows_skipped_uf"] += 1
                continue

            muni_code = row[_Est.CODIGO_MUNICIPIO].strip()
            muni_name = muni.get(muni_code, "")

            if uf == "GO" and not _is_ride_municipio(muni_name):
                stats["rows_skipped_go_not_ride"] += 1
                continue

            if uf == "GO":
                stats["rows_go_ride"] += 1
            else:
                stats["rows_df"] += 1
            stats["rows_filtered_in"] += 1

            basico = row[_Est.CNPJ_BASICO].strip()
            ordem = row[_Est.CNPJ_ORDEM].strip()
            dv = row[_Est.CNPJ_DV].strip()
            cnpj = f"{basico}{ordem}{dv}"

            emp = empresas.get(basico, {})
            situacao_code = row[_Est.SITUACAO_CADASTRAL].strip()
            porte_code = emp.get("porte", "00")
            nat_code = emp.get("natureza_juridica", "")

            secondary_raw = row[_Est.CNAE_SECUNDARIA].strip() if len(row) > _Est.CNAE_SECUNDARIA else ""
            secondary_cnaes = _parse_secondary_cnaes(secondary_raw)

            # Upsert empresa_candidata
            empresa = db.query(EmpresaCandidata).filter_by(cnpj=cnpj).first()
            is_new_empresa = empresa is None
            razao_social = emp.get("razao_social", "").strip()
            if not razao_social:
                razao_social = cnpj
                logger.debug("Empresa %s has no razao_social — using CNPJ as fallback", cnpj)
            if is_new_empresa:
                empresa = EmpresaCandidata(cnpj=cnpj, razao_social=razao_social)
                db.add(empresa)

            empresa.razao_social = razao_social or empresa.razao_social
            empresa.nome_fantasia = row[_Est.NOME_FANTASIA].strip() or empresa.nome_fantasia
            empresa.cnae_principal = row[_Est.CNAE_PRINCIPAL].strip() or None
            empresa.cnae_secundarios_json = json.dumps(secondary_cnaes) if secondary_cnaes else None
            empresa.porte = config.RECEITA_PORTE_MAP.get(porte_code, porte_code)
            empresa.natureza_juridica = natj.get(nat_code, nat_code) if nat_code else None
            empresa.situacao_cadastral = config.RECEITA_SITUACAO_MAP.get(situacao_code, situacao_code)
            empresa.data_abertura = _parse_date(row[_Est.DATA_INICIO])
            empresa.bairro = row[_Est.BAIRRO].strip() or None
            empresa.cep = row[_Est.CEP].strip() or None
            empresa.uf = uf
            empresa.municipio = muni_name or None
            empresa.telefone = _format_phone(row[_Est.DDD1], row[_Est.TELEFONE1])
            empresa.email = row[_Est.EMAIL].strip().lower() or None
            empresa.endereco_normalizado = _build_address(row)
            empresa.origem = "receita"

            if is_new_empresa:
                stats["empresas_created"] += 1
            else:
                stats["empresas_updated"] += 1

            db.flush()

            # Upsert local_candidato (one per establishment)
            existing_local = (
                db.query(LocalCandidato)
                .filter_by(empresa_id=empresa.id, origem="receita")
                .first()
            )
            if not existing_local:
                local = LocalCandidato(
                    empresa_id=empresa.id,
                    endereco=_build_address(row),
                    bairro=row[_Est.BAIRRO].strip() or None,
                    cep=row[_Est.CEP].strip() or None,
                    origem="receita",
                )
                db.add(local)
                stats["locais_created"] += 1

            pending += 1
            if pending >= batch_size:
                db.flush()
                pending = 0

        logger.info(
            "Estabelecimentos%d.zip done: %d filtered in so far",
            i, stats["rows_filtered_in"],
        )

    if pending:
        db.flush()

    logger.info("Receita parse complete: %s", stats)
    return stats
