"""ANEEL — Consumidores Livres e Especiais como proxy de porte operacional.

Baixa o dataset público de consumidores de energia elétrica da ANEEL via
dados abertos (CKAN dadosabertos.aneel.gov.br) e cruza com empresa_candidata
pelo CNPJ. Empresas grandes consumidoras de energia elétrica são fortes
candidatas a geradoras de e-waste (datacenters, varejo de eletrônicos,
indústria de TI, hospitais, etc.).

Fonte: https://dadosabertos.aneel.gov.br/
Dataset: Relação de Consumidores Livres e Especiais (atualizado mensalmente)
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata
from jobs.prospeccao import config, paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path, get_json

logger = logging.getLogger(__name__)

# ANEEL CKAN API — dadosabertos.aneel.gov.br
_ANEEL_CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"
_ANEEL_DATASET_SLUG = "relacao-de-consumidores-livres-e-especiais"

# Campos ANEEL esperados no CSV (podem variar por versão do dataset)
_CNPJ_FIELDS = ("CnpjConsumidor", "CNPJ", "cnpj", "NumeroCNPJ")
_CLASSE_FIELDS = ("ClasseConsumidor", "Classe", "TipoConsumidor", "SubGrupo")
_CONSUMO_FIELDS = ("ConsumoMWh", "ConsumoAnualMWh", "Consumo_MWh", "ConsumoTotal")
_UF_FIELDS = ("SiglaUF", "UF", "uf", "Estado")

# Classificação de porte operacional por consumo (MWh/ano)
_CONSUMO_TIERS = [
    (100_000, "industrial_grande"),   # >100 GWh/ano — grande indústria
    (10_000,  "industrial_medio"),    # >10 GWh/ano — médio porte
    (1_000,   "comercial_grande"),    # >1 GWh/ano — grande comércio
    (0,       "consumidor_livre"),    # qualquer consumidor livre registrado
]


def _clean_cnpj(raw: str | None) -> str:
    if not raw:
        return ""
    return "".join(c for c in str(raw) if c.isdigit())


def _discover_dataset_url() -> str | None:
    """Encontra URL do CSV mais recente no CKAN da ANEEL."""
    try:
        data = get_json(
            f"{_ANEEL_CKAN_BASE}/package_show",
            params={"id": _ANEEL_DATASET_SLUG},
            timeout=30,
        )
        resources = data.get("result", {}).get("resources", [])
        # Prefer CSV, fallback to ZIP
        for fmt in ("CSV", "csv", "ZIP", "zip"):
            for r in resources:
                if r.get("format", "").upper() == fmt.upper() and r.get("url"):
                    logger.info(
                        "ANEEL dataset encontrado: %s (%s)",
                        r.get("name", "?"), r.get("url", "")[:80],
                    )
                    return r["url"]
    except Exception as exc:
        logger.warning("ANEEL CKAN discovery falhou: %s", exc)
    return None


def _find_field(header: list[str], candidates: tuple[str, ...]) -> int | None:
    for name in candidates:
        for i, col in enumerate(header):
            if col.strip().lower() == name.lower():
                return i
    return None


def _parse_consumo(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def _consumo_tier(mwh: float | None) -> str:
    if mwh is None:
        return "consumidor_livre"
    for threshold, label in _CONSUMO_TIERS:
        if mwh >= threshold:
            return label
    return "consumidor_livre"


def _parse_csv_bytes(raw: bytes, encoding: str = "latin-1") -> list[dict[str, str]]:
    text = raw.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def _load_records_from_file(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                logger.warning("ANEEL ZIP sem CSV: %s", path.name)
                return []
            with zf.open(csv_names[0]) as f:
                return _parse_csv_bytes(f.read())
    else:
        return _parse_csv_bytes(path.read_bytes())


def download_aneel_consumidores(*, url: str | None = None) -> Path | None:
    """Baixa o dataset ANEEL de consumidores livres para data/raw."""
    target_url = url or getattr(config, "ANEEL_CONSUMIDORES_URL", "").strip()
    if not target_url:
        target_url = _discover_dataset_url()
    if not target_url:
        logger.warning(
            "ANEEL: URL não encontrada. Defina TRONIK_ANEEL_CONSUMIDORES_URL ou "
            "verifique se o dataset '%s' está no CKAN da ANEEL.",
            _ANEEL_DATASET_SLUG,
        )
        return None

    dirs = pathutil.ensure_raw_layout()
    aneel_dir = dirs["base"] / "aneel"
    aneel_dir.mkdir(parents=True, exist_ok=True)
    fname = target_url.rstrip("/").split("/")[-1] or "aneel_consumidores.csv"
    dest = aneel_dir / fname

    logger.info("ANEEL download: %s → %s", target_url[:100], dest.name)
    try:
        download_url_to_path(target_url, dest, resume=True, skip_if_same_size=True)
        pathutil.write_manifest("aneel_consumidores", {"url": target_url, "path": str(dest)})
        return dest
    except Exception as exc:
        logger.error("ANEEL download falhou: %s", exc)
        return None


def sync_aneel_consumidores(
    db: Session,
    *,
    url: str | None = None,
    ufs: set[str] | None = None,
) -> dict[str, Any]:
    """Baixa e cruza dados ANEEL com empresa_candidata pelo CNPJ.

    Adiciona campo `consumo_classe` (proxy de porte real) às empresas que
    constam na base de consumidores livres/especiais da ANEEL.

    Args:
        url: URL direta do CSV/ZIP. Se None, tenta descobrir via CKAN.
        ufs: Filtrar por UF (ex: {"DF", "GO"}). None = todos.

    Returns:
        Stats dict.
    """
    ufs = ufs or {"DF", "GO"}
    stats: dict[str, Any] = {
        "registros_aneel": 0,
        "cnpjs_aneel_df_go": 0,
        "empresas_encontradas": 0,
        "empresas_marcadas": 0,
        "arquivo": None,
    }

    path = download_aneel_consumidores(url=url)
    if not path:
        stats["erro"] = "Download falhou ou URL não configurada"
        return stats

    stats["arquivo"] = path.name

    records = _load_records_from_file(path)
    stats["registros_aneel"] = len(records)
    if not records:
        logger.warning("ANEEL: nenhum registro lido de %s", path.name)
        return stats

    # Detectar colunas dinamicamente
    header = list(records[0].keys())
    col_cnpj = _find_field(header, _CNPJ_FIELDS)
    col_classe = _find_field(header, _CLASSE_FIELDS)
    col_consumo = _find_field(header, _CONSUMO_FIELDS)
    col_uf = _find_field(header, _UF_FIELDS)

    if col_cnpj is None:
        logger.error(
            "ANEEL: coluna CNPJ não encontrada. Colunas disponíveis: %s",
            header[:20],
        )
        stats["erro"] = "Coluna CNPJ não encontrada no CSV"
        return stats

    logger.info(
        "ANEEL colunas detectadas — CNPJ:%s classe:%s consumo:%s uf:%s",
        header[col_cnpj] if col_cnpj is not None else "?",
        header[col_classe] if col_classe is not None else "?",
        header[col_consumo] if col_consumo is not None else "?",
        header[col_uf] if col_uf is not None else "?",
    )

    # Construir índice CNPJ → (tier, classe_raw)
    cnpj_index: dict[str, tuple[str, str]] = {}
    for row in records:
        vals = list(row.values())
        uf_raw = vals[col_uf].strip().upper() if col_uf is not None else ""
        if ufs and uf_raw not in ufs:
            continue
        cnpj = _clean_cnpj(vals[col_cnpj])
        if len(cnpj) != 14:
            continue
        consumo = _parse_consumo(vals[col_consumo] if col_consumo is not None else None)
        classe_raw = vals[col_classe].strip() if col_classe is not None else ""
        tier = _consumo_tier(consumo)
        cnpj_index[cnpj] = (tier, classe_raw)

    stats["cnpjs_aneel_df_go"] = len(cnpj_index)
    logger.info("ANEEL: %d CNPJs únicos em %s", len(cnpj_index), ufs)

    if not cnpj_index:
        return stats

    # Cruzar com banco
    cnpjs_list = list(cnpj_index.keys())
    chunk = 500
    for i in range(0, len(cnpjs_list), chunk):
        batch = cnpjs_list[i : i + chunk]
        empresas = (
            db.query(EmpresaCandidata)
            .filter(EmpresaCandidata.cnpj.in_(batch))
            .all()
        )
        stats["empresas_encontradas"] += len(empresas)
        for empresa in empresas:
            cnpj = _clean_cnpj(empresa.cnpj)
            tier, classe_raw = cnpj_index.get(cnpj, ("", ""))
            if tier:
                # Usar campo natureza_juridica como carrier temporário se não houver campo dedicado
                # Ou qualquer campo spare disponível no modelo
                if not empresa.natureza_juridica or "consumidor" not in empresa.natureza_juridica.lower():
                    empresa.natureza_juridica = (
                        f"{empresa.natureza_juridica or ''} [ANEEL:{tier}]".strip()
                    )
                stats["empresas_marcadas"] += 1

    db.flush()
    logger.info("ANEEL sync concluído: %s", stats)
    return stats
