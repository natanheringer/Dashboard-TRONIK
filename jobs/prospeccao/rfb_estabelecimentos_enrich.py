"""Enrich empresa_candidata via Receita Federal Estabelecimentos dump.

Reads pipe-delimited Estabelecimentos*.csv files from Receita Federal and updates
EmpresaCandidata and LocalCandidato records with CNAE, address, CEP, and contact info
that were missing from previous enrichment stages.

The RFB files are typically sourced from:
https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato

logger = logging.getLogger(__name__)

# Columns in Estabelecimentos CSV (pipe-delimited, no header, latin-1 encoding)
RFB_COLS = [
    "cnpj_basico",
    "cnpj_ordem",
    "cnpj_dv",
    "identificador_matriz_filial",
    "nome_fantasia",
    "situacao_cadastral",
    "data_situacao_cadastral",
    "motivo_situacao_cadastral",
    "nome_cidade_exterior",
    "pais",
    "data_inicio_atividade",
    "cnae_fiscal_principal",
    "cnae_fiscal_secundaria",
    "tipo_logradouro",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "uf",
    "municipio",
    "ddd_1",
    "telefone_1",
    "ddd_2",
    "telefone_2",
    "ddd_fax",
    "fax",
    "correio_eletronico",
    "situacao_especial",
    "data_situacao_especial",
]

# Active company status code in RFB
_ATIVA = "02"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_cnpj(cnpj_basico: str, cnpj_ordem: str, cnpj_dv: str) -> str:
    """Assemble 14-digit CNPJ from RFB components (no punctuation)."""
    try:
        b = str(cnpj_basico or "").strip().zfill(8)
        o = str(cnpj_ordem or "").strip().zfill(4)
        d = str(cnpj_dv or "").strip().zfill(2)
        return b + o + d
    except Exception:
        return ""


def _clean_cep(cep: str) -> str | None:
    """Extract digits from CEP; return None if not exactly 8 digits."""
    if not cep:
        return None
    digits = "".join(c for c in str(cep).strip() if c.isdigit())
    return digits if len(digits) == 8 else None


def _clean_bairro(bairro: str) -> str | None:
    """Normalize bairro: strip, lowercase, return None if empty."""
    if not bairro:
        return None
    result = str(bairro).strip().lower()
    return result if result else None


def _build_endereco(tipo_logradouro: str, logradouro: str, numero: str) -> str | None:
    """Build normalized address from address components."""
    parts = []
    if tipo_logradouro:
        parts.append(str(tipo_logradouro).strip())
    if logradouro:
        parts.append(str(logradouro).strip())
    if numero:
        parts.append(str(numero).strip())

    result = " ".join(parts)
    return result.strip() if result else None


def _parse_cnae_secundarios(raw: str) -> list[str]:
    """Parse RFB secondary CNAEs (7 digits each) into list of 4-digit codes.

    RFB format: Each CNAE is 7 digits, concatenated without delimiter.
    Example: '47534759' = two CNAEs: '4753' and '4759' (taking first 4 of each).
    """
    if not raw or not isinstance(raw, str):
        return []

    raw = str(raw).strip()
    if not raw:
        return []

    codes = []
    # Split into 7-digit chunks
    for i in range(0, len(raw), 7):
        chunk = raw[i : i + 7]
        if len(chunk) >= 4:
            # Take first 4 digits as the CNAE code
            code = chunk[:4]
            if code.isdigit() and code not in codes:
                codes.append(code)

    return codes


def _load_rfb_files(
    dump_dir: Path,
    uf_filter: str = "DF",
) -> dict[str, dict[str, Any]]:
    """Load all Estabelecimentos*.csv files and build dict: CNPJ -> data.

    Args:
        dump_dir: Directory containing Estabelecimentos*.csv files
        uf_filter: Filter by UF (default "DF")

    Returns:
        Dict mapping 14-digit CNPJ -> enrichment dict with keys:
        cnae_principal, bairro, cep, endereco_normalizado, nome_fantasia, email

    Raises:
        ValueError: If no CSV files found
    """
    dump_dir = Path(dump_dir)
    if not dump_dir.is_dir():
        raise ValueError(f"dump_dir nao existe ou nao eh diretorio: {dump_dir}")

    # Aceita: Estabelecimentos*.csv, *.ESTABE, K3241.*.ESTABE (formato RFB nativo)
    csv_files = (
        list(dump_dir.glob("*stabelecimentos*.csv"))
        or list(dump_dir.glob("*stabelecimento*.csv"))
        or list(dump_dir.glob("*.ESTABELE"))
        or list(dump_dir.glob("*.[Ee][Ss][Tt][Aa][Bb][Ee][Ll][Ee]"))
    )

    if not csv_files:
        raise ValueError(
            f"Nenhum arquivo Estabelecimentos encontrado em {dump_dir}. "
            f"Formatos aceitos: Estabelecimentos*.csv, *.ESTABE"
        )

    rfb: dict[str, dict[str, Any]] = {}

    for csv_file in csv_files:
        logger.info("rfb-enrich: lendo arquivo %s", csv_file.name)

        # Lê em chunks para suportar arquivos grandes (Y0 tem ~6GB)
        try:
            chunks = pd.read_csv(
                csv_file,
                sep=";",
                header=None,
                names=RFB_COLS,
                encoding="latin-1",
                dtype=str,
                low_memory=False,
                chunksize=200_000,
            )
            df_parts = []
            for chunk in chunks:
                filtered = chunk[
                    (chunk["uf"].fillna("").str.upper() == uf_filter.upper())
                    & (chunk["situacao_cadastral"] == _ATIVA)
                ]
                if not filtered.empty:
                    df_parts.append(filtered)
            df = pd.concat(df_parts, ignore_index=True) if df_parts else pd.DataFrame()
        except Exception as exc:
            logger.error("rfb-enrich: erro ao ler %s: %s", csv_file.name, exc)
            continue

        if df.empty:
            logger.debug("rfb-enrich: nenhuma linha ativa para UF=%s em %s", uf_filter, csv_file.name)
            continue

        # Build CNPJ and extract data
        for _, row in df.iterrows():
            try:
                cnpj_14 = _clean_cnpj(
                    row.get("cnpj_basico", ""),
                    row.get("cnpj_ordem", ""),
                    row.get("cnpj_dv", ""),
                )

                if not cnpj_14 or len(cnpj_14) != 14:
                    continue

                # Extract and normalize fields
                cnae_principal = (
                    str(row.get("cnae_fiscal_principal") or "").strip()
                    or None
                )
                bairro = _clean_bairro(row.get("bairro", ""))
                cep = _clean_cep(row.get("cep", ""))
                endereco = _build_endereco(
                    row.get("tipo_logradouro", ""),
                    row.get("logradouro", ""),
                    row.get("numero", ""),
                )
                nome_fantasia = (
                    str(row.get("nome_fantasia") or "").strip()
                    or None
                )
                email = (
                    str(row.get("correio_eletronico") or "").strip().lower()
                    or None
                )

                # Validate email basic format
                if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
                    email = None

                rfb[cnpj_14] = {
                    "cnae_principal": cnae_principal,
                    "bairro": bairro,
                    "cep": cep,
                    "endereco_normalizado": endereco,
                    "nome_fantasia": nome_fantasia,
                    "email": email,
                }
            except Exception as exc:
                logger.debug("rfb-enrich: erro ao processar linha: %s", exc)
                continue

    return rfb


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------


def enrich_from_rfb_dump(
    db: Session,
    *,
    dump_dir: Path,
    uf_filter: str = "DF",
    batch_size: int = 5_000,
    dry_run: bool = False,
) -> dict[str, int]:
    """Enrich EmpresaCandidata and LocalCandidato from RFB Estabelecimentos dump.

    Reads pipe-delimited CSV files from Receita Federal and updates company and
    location records with CNAE, address, CEP, and contact info, but only for
    fields that are currently None.

    Args:
        db: SQLAlchemy session
        dump_dir: Directory containing Estabelecimentos*.csv files
        uf_filter: Filter by UF (default "DF" for Brasília)
        batch_size: Commit every N updates (default 5000)
        dry_run: If True, don't commit changes (default False)

    Returns:
        Stats dict:
        - rfb_rows_loaded: Number of RFB records loaded
        - empresas_matched: Number of EmpresaCandidata found in RFB
        - empresas_updated: Number of EmpresaCandidata records modified
        - locais_updated: Number of LocalCandidato records modified
        - batches: Number of commit batches

    Raises:
        ValueError: If dump_dir does not exist or no CSV files found
    """
    dump_dir = Path(dump_dir)

    # Load RFB data
    logger.info(
        "rfb-enrich: carregando arquivos de %s (UF=%s)",
        dump_dir, uf_filter
    )
    rfb = _load_rfb_files(dump_dir, uf_filter=uf_filter)
    logger.info("rfb-enrich: %d registros RFB carregados para UF=%s", len(rfb), uf_filter)

    if not rfb:
        logger.warning("rfb-enrich: nenhum registro RFB carregado")
        return {
            "rfb_rows_loaded": 0,
            "empresas_matched": 0,
            "empresas_updated": 0,
            "locais_updated": 0,
            "batches": 0,
        }

    # Query in batches to avoid huge IN() lists
    rfb_cnpjs = list(rfb.keys())
    batch_size_query = 10_000

    empresas_matched = 0
    empresas_updated = 0
    locais_updated = 0
    batches = 0

    total_batches_query = (len(rfb_cnpjs) + batch_size_query - 1) // batch_size_query

    for batch_i in range(0, len(rfb_cnpjs), batch_size_query):
        cnpj_batch = rfb_cnpjs[batch_i : batch_i + batch_size_query]
        batch_n = batch_i // batch_size_query + 1

        # Query companies for this batch
        empresas = db.query(EmpresaCandidata).filter(
            EmpresaCandidata.cnpj.in_(cnpj_batch)
        ).all()

        empresas_matched += len(empresas)

        updates_in_batch = 0

        for empresa in empresas:
            data = rfb.get(empresa.cnpj)
            if not data:
                continue

            updated = False

            # Update empresa fields (only if None)
            if empresa.cnae_principal is None and data["cnae_principal"]:
                empresa.cnae_principal = data["cnae_principal"]
                updated = True

            if empresa.bairro is None and data["bairro"]:
                empresa.bairro = data["bairro"]
                updated = True

            if empresa.cep is None and data["cep"]:
                empresa.cep = data["cep"]
                updated = True

            if empresa.endereco_normalizado is None and data["endereco_normalizado"]:
                empresa.endereco_normalizado = data["endereco_normalizado"]
                updated = True

            if empresa.nome_fantasia is None and data["nome_fantasia"]:
                empresa.nome_fantasia = data["nome_fantasia"]
                updated = True

            if empresa.email is None and data["email"]:
                empresa.email = data["email"]
                updated = True

            if updated:
                empresas_updated += 1
                updates_in_batch += 1

                # Update associated LocalCandidato records
                locais = db.query(LocalCandidato).filter(
                    LocalCandidato.empresa_id == empresa.id
                ).all()

                for local in locais:
                    if local.bairro is None and data["bairro"]:
                        local.bairro = data["bairro"]
                        locais_updated += 1

                    if local.cep is None and data["cep"]:
                        local.cep = data["cep"]
                        locais_updated += 1

                    if local.endereco is None and data["endereco_normalizado"]:
                        local.endereco = data["endereco_normalizado"]
                        locais_updated += 1

        # Commit batch
        if updates_in_batch > 0:
            if not dry_run:
                db.commit()
            batches += 1
            logger.info(
                "rfb-enrich: processado batch %d/%d — %d atualizacoes",
                batch_n, total_batches_query, updates_in_batch,
            )

    stats = {
        "rfb_rows_loaded": len(rfb),
        "empresas_matched": empresas_matched,
        "empresas_updated": empresas_updated,
        "locais_updated": locais_updated,
        "batches": batches,
    }

    logger.info("rfb-enrich: concluído — %s", stats)
    return stats
