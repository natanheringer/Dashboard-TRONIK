"""IBAMA CTF/APP — Cadastro Técnico Federal de Atividades Potencialmente Poluidoras.

Baixa o CSV de pessoas jurídicas inscritas no CTF/APP por estado e cruza com
empresa_candidata pelo CNPJ. Empresas na categoria "Indústria de Material
Elétrico, Eletrônico e Comunicações" (FTE-5) são leads diretos de e-waste.

Fonte: https://dadosabertos.ibama.gov.br/dataset/pessoas-juridicas-inscritas-no-ctf-app
URL CSV: http://dadosabertos.ibama.gov.br/dados/CTF/APP/{UF}/pessoasJuridicas.csv
Atualização: mensal (último: 2026-04-29)
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path

logger = logging.getLogger(__name__)

_CTF_CSV_BASE = "http://dadosabertos.ibama.gov.br/dados/CTF/APP/{uf}/pessoasJuridicas.csv"
_BATCH_SIZE = 500

# Palavras-chave que identificam atividades REEE no CTF/APP
_ELETRO_KEYWORDS = (
    "eletro",
    "eletr",
    "inform",
    "telecomunica",
    "comunicacao",
    "comunicação",
    "bateria",
    "pilha",
    "semicondutor",
    "reciclagem de residu",
    "sucata",
    "reee",
)

# Palavras-chave para atividades de destinação/transporte de resíduos — relevantes como parceiros
_DESTINADOR_KEYWORDS = (
    "destinacao",
    "destinação",
    "transporte de residuo",
    "armazenamento de residuo",
    "tratamento de residuo",
    "reciclagem",
    "coleta de residuo",
)

# Campos esperados no CSV do IBAMA (nomes variam por versão)
_CNPJ_FIELDS = ("cnpj", "CNPJ", "nr_cnpj", "CnpjPessoa")
_ATIVIDADE_FIELDS = ("atividade", "Atividade", "ds_atividade", "DescricaoAtividade", "nm_atividade")


def _clean_cnpj(raw: str | None) -> str:
    if not raw:
        return ""
    return "".join(c for c in str(raw) if c.isdigit())


def _find_field(header: list[str], candidates: tuple[str, ...]) -> int | None:
    for name in candidates:
        for i, col in enumerate(header):
            if col.strip().lower() == name.lower():
                return i
    return None


def _is_eletro(atividade: str) -> bool:
    a = atividade.lower()
    return any(kw in a for kw in _ELETRO_KEYWORDS)


def _is_destinador(atividade: str) -> bool:
    a = atividade.lower()
    return any(kw in a for kw in _DESTINADOR_KEYWORDS)


def _parse_csv_bytes(raw: bytes) -> list[dict[str, str]]:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue
        for delim in (";", ",", "\t"):
            reader = csv.DictReader(io.StringIO(text), delimiter=delim)
            rows = list(reader)
            if rows and len(rows[0]) > 2:
                return rows
    return []


def _load_records_from_file(path: Path) -> list[dict[str, str]]:
    return _parse_csv_bytes(path.read_bytes())


def download_ibama_ctf_csv(uf: str, *, dest_dir: Path | None = None) -> Path | None:
    """Baixa o CSV de pessoas jurídicas CTF/APP para uma UF específica."""
    url = _CTF_CSV_BASE.format(uf=uf.upper())
    dirs = pathutil.ensure_raw_layout()
    out_dir = dest_dir or (dirs["base"] / "ibama_ctf")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"pessoasJuridicas_{uf.upper()}.csv"

    logger.info("IBAMA CTF/APP: baixando UF=%s (%s)", uf.upper(), url)
    try:
        download_url_to_path(url, dest, resume=True, skip_if_same_size=True)
        logger.info(
            "IBAMA CTF/APP: %s -> %s (%d KB)",
            uf.upper(),
            dest.name,
            dest.stat().st_size // 1024,
        )
        return dest
    except Exception as exc:
        logger.error("IBAMA CTF/APP download UF=%s falhou: %s", uf, exc)
        return None


def _resolve_ctf_path(uf: str, ctf_dir: Path, *, download: bool) -> Path | None:
    dest = ctf_dir / f"pessoasJuridicas_{uf.upper()}.csv"
    if download:
        path = download_ibama_ctf_csv(uf, dest_dir=ctf_dir)
        if path:
            return path
    if dest.is_file() and dest.stat().st_size > 0:
        logger.info("IBAMA CTF/APP UF=%s: usando CSV local %s", uf.upper(), dest.name)
        return dest
    return None


def _append_ibama_label(empresa: EmpresaCandidata, tag: str) -> bool:
    label = f"[IBAMA:{tag}]"
    existing = empresa.natureza_juridica or ""
    if label in existing:
        return False
    empresa.natureza_juridica = f"{existing} {label}".strip()
    return True


def sync_ibama_ctf(
    db: Session,
    *,
    ufs: set[str] | None = None,
    include_destinadores: bool = True,
    download: bool = True,
) -> dict[str, Any]:
    """Baixa CTF/APP para as UFs indicadas e cruza com empresa_candidata.

    Empresas marcadas:
      [IBAMA:eletronico]  — atividade ligada a equipamentos eletroeletrônicos
      [IBAMA:destinador]  — destinação/reciclagem/transporte de resíduos (parceiro)

    Args:
        ufs: Estados a processar (default: {"DF", "GO"}).
        include_destinadores: Se True, também marca destinadores de resíduos.
        download: Se False, usa apenas CSVs já presentes em data/raw/.../ibama_ctf.

    Returns:
        Stats dict.
    """
    ufs = ufs or {"DF", "GO"}
    stats: dict[str, Any] = {
        "ufs_processadas": [],
        "registros_ctf": 0,
        "cnpjs_eletronico": 0,
        "cnpjs_destinador": 0,
        "empresas_encontradas": 0,
        "empresas_marcadas": 0,
        "marcadas_eletronico": 0,
        "marcadas_destinador": 0,
        "erros": [],
    }

    dirs = pathutil.ensure_raw_layout()
    ctf_dir = dirs["base"] / "ibama_ctf"
    ctf_dir.mkdir(parents=True, exist_ok=True)

    # CNPJ → tag (eletronico tem prioridade sobre destinador)
    cnpj_tag: dict[str, str] = {}

    for uf in sorted(ufs):
        path = _resolve_ctf_path(uf, ctf_dir, download=download)
        if not path:
            stats["erros"].append(f"arquivo_ausente:{uf}")
            continue

        records = _load_records_from_file(path)
        if not records:
            logger.warning("IBAMA CTF/APP UF=%s: CSV vazio ou não parseável", uf)
            stats["erros"].append(f"csv_vazio:{uf}")
            continue

        header = list(records[0].keys())
        col_cnpj = _find_field(header, _CNPJ_FIELDS)
        col_ativ = _find_field(header, _ATIVIDADE_FIELDS)

        if col_cnpj is None:
            logger.error(
                "IBAMA CTF/APP UF=%s: coluna CNPJ não encontrada. Colunas: %s",
                uf,
                header[:20],
            )
            stats["erros"].append(f"coluna_cnpj_ausente:{uf}")
            continue

        logger.info(
            "IBAMA CTF/APP UF=%s: %d registros, CNPJ:%s atividade:%s",
            uf,
            len(records),
            header[col_cnpj],
            header[col_ativ] if col_ativ is not None else "?",
        )

        stats["registros_ctf"] += len(records)
        stats["ufs_processadas"].append(uf)

        for row in records:
            vals = list(row.values())
            cnpj = _clean_cnpj(vals[col_cnpj])
            if len(cnpj) != 14:
                continue
            atividade = vals[col_ativ].strip() if col_ativ is not None else ""

            if _is_eletro(atividade):
                prev = cnpj_tag.get(cnpj)
                if prev != "eletronico":
                    if prev == "destinador":
                        stats["cnpjs_destinador"] -= 1
                    else:
                        stats["cnpjs_eletronico"] += 1
                    cnpj_tag[cnpj] = "eletronico"
            elif include_destinadores and _is_destinador(atividade) and cnpj not in cnpj_tag:
                cnpj_tag[cnpj] = "destinador"
                stats["cnpjs_destinador"] += 1

    pathutil.write_manifest(
        "ibama_ctf",
        {
            "ufs": sorted(ufs),
            "download": download,
            "registros": stats["registros_ctf"],
            "cnpjs_eletronico": stats["cnpjs_eletronico"],
            "cnpjs_destinador": stats["cnpjs_destinador"],
        },
    )

    if not cnpj_tag:
        logger.warning("IBAMA CTF/APP: nenhum CNPJ relevante extraído")
        return stats

    logger.info(
        "IBAMA CTF/APP: %d CNPJs únicos (%d eletrônico, %d destinador) em %s",
        len(cnpj_tag),
        stats["cnpjs_eletronico"],
        stats["cnpjs_destinador"],
        sorted(ufs),
    )

    cnpjs_list = list(cnpj_tag.keys())
    for i in range(0, len(cnpjs_list), _BATCH_SIZE):
        batch = cnpjs_list[i : i + _BATCH_SIZE]
        empresas = (
            db.query(EmpresaCandidata)
            .filter(EmpresaCandidata.cnpj.in_(batch))
            .all()
        )
        stats["empresas_encontradas"] += len(empresas)
        for empresa in empresas:
            cnpj = _clean_cnpj(empresa.cnpj)
            tag = cnpj_tag.get(cnpj, "")
            if not tag or not _append_ibama_label(empresa, tag):
                continue
            stats["empresas_marcadas"] += 1
            if tag == "eletronico":
                stats["marcadas_eletronico"] += 1
            else:
                stats["marcadas_destinador"] += 1

    db.flush()
    logger.info("IBAMA CTF/APP sync concluído: %s", stats)
    return stats
