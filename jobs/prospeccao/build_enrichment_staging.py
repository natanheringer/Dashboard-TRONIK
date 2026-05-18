"""Materialize OSM / INEP / CNES staging parquets for ranker enrichment (Sócrates).

Reads raw sources under data/prospeccao/* or data/raw/prospeccao/* and writes
aggregated parquet files consumed by ``enrichment_proxies.lookup_proxies``.

When a source is missing, the corresponding builder logs and returns ``skipped``.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from jobs.prospeccao import config

logger = logging.getLogger(__name__)

REPO_ROOT = config.REPO_ROOT

_ENV_OSM_OUT = "TRONIK_OSM_POI_PARQUET"
_ENV_INEP_OUT = "TRONIK_INEP_CENSO_PARQUET"
_ENV_CNES_OUT = "TRONIK_CNES_PARQUET"

DEFAULT_STAGING_DIR = REPO_ROOT / "data" / "ml" / "staging"
DEFAULT_OSM_OUT = DEFAULT_STAGING_DIR / "osm_poi_ree.parquet"
DEFAULT_INEP_OUT = DEFAULT_STAGING_DIR / "inep_censo_ra.parquet"
DEFAULT_CNES_OUT = DEFAULT_STAGING_DIR / "cnes_mun.parquet"

_OSM_REE_SHOPS = frozenset({
    "electronics",
    "computer",
    "mobile_phone",
    "telecommunication",
    "electrical",
    "appliance",
    "hifi",
    "radiotechnics",
})
_OSM_REE_AMENITIES = frozenset({"school", "university", "college", "hospital", "clinic"})
_OSM_REE_OFFICES = frozenset({"it", "telecommunication", "company"})

_LAT_ALIASES = frozenset({"latitude", "lat", "y", "nu_latitude", "vl_latitude"})
_LON_ALIASES = frozenset({"longitude", "lon", "lng", "long", "x", "nu_longitude", "vl_longitude"})
_CAT_ALIASES = frozenset({"category", "categoria", "tipo", "tag", "amenity", "shop"})
_RA_ALIASES = frozenset({
    "ra",
    "regiao_administrativa",
    "regiao",
    "no_regiao",
    "no_subdistrito",
    "ds_regiao_administrativa",
    "subdistrito",
})
_MUN_ALIASES = frozenset({
    "municipio",
    "municipio_nome",
    "nome_municipio",
    "no_municipio",
    "city",
    "co_municipio",
})
_INEP_RA_ALIASES = _RA_ALIASES | frozenset({"no_distrito", "distrito"})
_INEP_UF_ALIASES = frozenset({"co_uf", "uf", "sg_uf", "estado"})


def _output_path(env_name: str, default: Path) -> Path:
    raw = (os.getenv(env_name) or "").strip()
    return Path(raw) if raw else default


def _osm_source_dirs() -> list[Path]:
    override = (os.getenv("TRONIK_OSM_SOURCE_DIR") or "").strip()
    if override:
        return [Path(override)]
    candidates = [
        REPO_ROOT / "data" / "prospeccao" / "osm",
        config.RAW_DIR / "osm_geofabrik",
    ]
    return [p for p in candidates if p.is_dir()]


def _inep_source_dirs() -> list[Path]:
    override = (os.getenv("TRONIK_INEP_SOURCE_DIR") or "").strip()
    if override:
        return [Path(override)]
    candidates = [
        REPO_ROOT / "data" / "prospeccao" / "inep",
        config.RAW_DIR / "inep",
    ]
    return [p for p in candidates if p.is_dir()]


def _cnes_source_dirs() -> list[Path]:
    override = (os.getenv("TRONIK_CNES_SOURCE_DIR") or "").strip()
    if override:
        return [Path(override)]
    candidates = [
        REPO_ROOT / "data" / "prospeccao" / "cnes",
        config.RAW_DIR / "cnes",
    ]
    return [p for p in candidates if p.is_dir()]


def _norm_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _find_col(fieldnames: list[str], aliases: frozenset[str]) -> str | None:
    for raw in fieldnames:
        key = _norm_header(raw)
        if key in aliases:
            return raw
    return None


def _float_or_none(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with path.open(encoding=encoding, newline="") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames:
                    return [], []
                rows = list(reader)
                return list(reader.fieldnames), rows
        except UnicodeDecodeError:
            continue
    logger.warning("Não foi possível decodificar CSV: %s", path)
    return [], []


def _write_parquet(records: list[dict[str, Any]], path: Path) -> bool:
    if not records:
        return False
    try:
        import pandas as pd
    except ImportError:
        logger.warning("pandas ausente — não foi possível gravar %s", path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(path, index=False)
    return True


def _osm_category_from_tags(tags: dict[str, str]) -> str | None:
    shop = tags.get("shop", "").strip().lower()
    if shop in _OSM_REE_SHOPS:
        return f"shop={shop}"
    amenity = tags.get("amenity", "").strip().lower()
    if amenity in _OSM_REE_AMENITIES:
        return f"amenity={amenity}"
    office = tags.get("office", "").strip().lower()
    if office in _OSM_REE_OFFICES:
        return f"office={office}"
    if tags.get("waste") in ("electronics", "electrical"):
        return "waste=electronics"
    return None


def _rows_from_osm_csv(path: Path) -> list[dict[str, Any]]:
    fieldnames, rows = _read_csv_rows(path)
    if not rows:
        return []
    lat_col = _find_col(fieldnames, _LAT_ALIASES)
    lon_col = _find_col(fieldnames, _LON_ALIASES)
    if not lat_col or not lon_col:
        return []
    cat_col = _find_col(fieldnames, _CAT_ALIASES)
    ra_col = _find_col(fieldnames, _RA_ALIASES)
    out: list[dict[str, Any]] = []
    for row in rows:
        lat = _float_or_none(row.get(lat_col))
        lon = _float_or_none(row.get(lon_col))
        if lat is None or lon is None:
            continue
        category = (row.get(cat_col) or "poi").strip() if cat_col else "poi"
        entry: dict[str, Any] = {"lat": lat, "lon": lon, "category": category}
        if ra_col and row.get(ra_col):
            entry["ra"] = str(row[ra_col]).strip()
        out.append(entry)
    return out


def _rows_from_osm_pbf(path: Path) -> list[dict[str, Any]]:
    try:
        import osmium
    except ImportError:
        logger.info("pyosmium ausente — ignorando PBF %s", path.name)
        return []

    class _Handler(osmium.SimpleHandler):
        def __init__(self) -> None:
            super().__init__()
            self.rows: list[dict[str, Any]] = []

        def node(self, n: osmium.osm.Node) -> None:
            if not n.location.valid():
                return
            tags = {t.k: t.v for t in n.tags}
            category = _osm_category_from_tags(tags)
            if not category:
                return
            self.rows.append({
                "lat": n.location.lat,
                "lon": n.location.lon,
                "category": category,
            })

    handler = _Handler()
    handler.apply_file(str(path), locations=True)
    return handler.rows


def _collect_osm_sources(dirs: list[Path]) -> tuple[list[Path], list[Path]]:
    csvs: list[Path] = []
    pbfs: list[Path] = []
    for base in dirs:
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix == ".csv":
                csvs.append(path)
            elif suffix == ".pbf":
                pbfs.append(path)
    return csvs, pbfs


def build_osm_poi_parquet(*, output_path: Path | None = None) -> dict[str, Any]:
    """Build OSM POI parquet (lat, lon, category, optional ra) from CSV or Geofabrik PBF."""
    out_path = output_path or _output_path(_ENV_OSM_OUT, DEFAULT_OSM_OUT)
    dirs = _osm_source_dirs()
    if not dirs:
        msg = "Nenhum diretório OSM encontrado (data/prospeccao/osm ou raw/osm_geofabrik)"
        logger.info("build_osm_poi_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    csvs, pbfs = _collect_osm_sources(dirs)
    if not csvs and not pbfs:
        msg = f"Sem CSV/PBF em {[str(d) for d in dirs]}"
        logger.info("build_osm_poi_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    records: list[dict[str, Any]] = []
    for csv_path in csvs:
        records.extend(_rows_from_osm_csv(csv_path))
    for pbf_path in pbfs:
        records.extend(_rows_from_osm_pbf(pbf_path))

    if not records:
        msg = "Nenhum POI REE válido extraído das fontes OSM"
        logger.info("build_osm_poi_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    ok = _write_parquet(records, out_path)
    result: dict[str, Any] = {
        "skipped": False,
        "ok": ok,
        "path": str(out_path),
        "rows": len(records),
        "sources": {"csv": len(csvs), "pbf": len(pbfs)},
    }
    if ok:
        logger.info("build_osm_poi_parquet: %s linhas -> %s", len(records), out_path)
    return result


def _find_inep_csv(dirs: list[Path]) -> Path | None:
    preferred = "censo_escolar_externo.csv"
    for base in dirs:
        candidate = base / preferred
        if candidate.is_file():
            return candidate
    for base in dirs:
        csvs = sorted(base.glob("*.csv"))
        if csvs:
            return csvs[0]
    return None


def build_inep_ra_parquet(*, output_path: Path | None = None) -> dict[str, Any]:
    """Aggregate school counts by RA from local INEP censo CSV."""
    out_path = output_path or _output_path(_ENV_INEP_OUT, DEFAULT_INEP_OUT)
    if not (os.getenv("TRONIK_INEP_CENSO_ESCOLAR_CSV_URL") or "").strip():
        msg = "TRONIK_INEP_CENSO_ESCOLAR_CSV_URL não definida"
        logger.info("build_inep_ra_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    dirs = _inep_source_dirs()
    if not dirs:
        msg = "Nenhum diretório INEP local (data/prospeccao/inep ou raw/inep)"
        logger.info("build_inep_ra_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    csv_path = _find_inep_csv(dirs)
    if csv_path is None:
        msg = f"CSV INEP ausente em {[str(d) for d in dirs]}"
        logger.info("build_inep_ra_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    fieldnames, rows = _read_csv_rows(csv_path)
    if not rows:
        msg = f"CSV INEP vazio ou ilegível: {csv_path}"
        logger.info("build_inep_ra_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    ra_col = _find_col(fieldnames, _INEP_RA_ALIASES)
    if not ra_col:
        msg = f"Coluna de RA não encontrada em {csv_path.name}"
        logger.info("build_inep_ra_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    uf_col = _find_col(fieldnames, _INEP_UF_ALIASES)
    counts: Counter[str] = Counter()
    for row in rows:
        if uf_col:
            uf = str(row.get(uf_col) or "").strip()
            if uf and uf not in ("53", "DF"):
                continue
        ra_val = str(row.get(ra_col) or "").strip()
        if ra_val:
            counts[ra_val] += 1

    if not counts:
        msg = "Nenhuma escola agregada por RA (verifique UF=DF ou colunas)"
        logger.info("build_inep_ra_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    records = [{"ra": ra, "count": n} for ra, n in sorted(counts.items())]
    ok = _write_parquet(records, out_path)
    result: dict[str, Any] = {
        "skipped": False,
        "ok": ok,
        "path": str(out_path),
        "rows": len(records),
        "source": str(csv_path),
        "schools_total": sum(counts.values()),
    }
    if ok:
        logger.info(
            "build_inep_ra_parquet: %s RAs (%s escolas) -> %s",
            len(records),
            result["schools_total"],
            out_path,
        )
    return result


def _find_cnes_zip(dirs: list[Path]) -> Path | None:
    for base in dirs:
        zips = sorted(base.glob("*.zip"))
        if zips:
            return zips[-1]
    return None


def _iter_cnes_csv_rows(zf: zipfile.ZipFile) -> tuple[list[str], list[dict[str, str]]]:
    """Pick the largest CSV inside the CNES zip (typically establishment table)."""
    csv_members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not csv_members:
        return [], []
    csv_members.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
    for member in csv_members:
        raw = zf.read(member)
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                text = raw.decode(encoding)
                reader = csv.DictReader(io.StringIO(text), delimiter=";")
                if not reader.fieldnames:
                    continue
                rows = list(reader)
                if rows:
                    return list(reader.fieldnames), rows
            except UnicodeDecodeError:
                continue
    return [], []


def build_cnes_mun_parquet(*, output_path: Path | None = None) -> dict[str, Any]:
    """Aggregate health units by municipio from local CNES zip."""
    out_path = output_path or _output_path(_ENV_CNES_OUT, DEFAULT_CNES_OUT)
    dirs = _cnes_source_dirs()
    if not dirs:
        msg = "Nenhum diretório CNES local (data/prospeccao/cnes ou raw/cnes)"
        logger.info("build_cnes_mun_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    zip_path = _find_cnes_zip(dirs)
    if zip_path is None:
        msg = f"ZIP CNES ausente em {[str(d) for d in dirs]}"
        logger.info("build_cnes_mun_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    try:
        with zipfile.ZipFile(zip_path) as zf:
            fieldnames, rows = _iter_cnes_csv_rows(zf)
    except zipfile.BadZipFile:
        msg = f"ZIP CNES inválido: {zip_path}"
        logger.info("build_cnes_mun_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    if not rows:
        msg = f"Nenhum CSV utilizável em {zip_path.name}"
        logger.info("build_cnes_mun_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    mun_col = _find_col(fieldnames, _MUN_ALIASES)
    if not mun_col:
        msg = f"Coluna de município não encontrada em {zip_path.name}"
        logger.info("build_cnes_mun_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    counts: Counter[str] = Counter()
    for row in rows:
        mun = str(row.get(mun_col) or "").strip()
        if mun:
            counts[mun] += 1

    if not counts:
        msg = "Nenhuma unidade agregada por município"
        logger.info("build_cnes_mun_parquet: skip — %s", msg)
        return {"skipped": True, "reason": msg, "path": str(out_path)}

    records = [{"municipio": mun, "unidades": n} for mun, n in sorted(counts.items())]
    ok = _write_parquet(records, out_path)
    result: dict[str, Any] = {
        "skipped": False,
        "ok": ok,
        "path": str(out_path),
        "rows": len(records),
        "source": str(zip_path),
        "units_total": sum(counts.values()),
    }
    if ok:
        logger.info(
            "build_cnes_mun_parquet: %s municípios (%s unidades) -> %s",
            len(records),
            result["units_total"],
            out_path,
        )
    return result


def build_all_enrichment() -> dict[str, Any]:
    """Run all three staging builders (graceful skip per source)."""
    return {
        "osm": build_osm_poi_parquet(),
        "inep": build_inep_ra_parquet(),
        "cnes": build_cnes_mun_parquet(),
    }
