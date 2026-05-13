"""CNEFE 2022 — download and parse IBGE census address coordinates.

Builds an in-memory and DB-persisted lookup table:
  (cep, logradouro_normalized, numero) -> (lat, lon, quality)

Used by normalize_candidates.py to geocode Receita Federal addresses without
depending on external geocoding APIs.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path

logger = logging.getLogger(__name__)

# CNEFE 2022 Arquivos_CNEFE/CSV column name candidates (case-insensitive).
_LAT_CANDIDATES = {"latitude"}
_LON_CANDIDATES = {"longitude"}
_CEP_CANDIDATES = {"cep"}
_LOGRADOURO_CANDIDATES = {"nom_seglogr", "nom_logradouro", "logradouro"}
_NUMERO_CANDIDATES = {"num_endereco", "numero"}
_MUNICIPIO_CANDIDATES = {"cod_municipio", "cod_mun", "municipio"}

_RIDE_CODES: set[str] = {str(code) for code in config.RIDE_ENTORNO_MUNICIPIOS}
_BRASILIA_CODE = config.IBGE_MUNICIPIO_DF_IBGE  # "5300108"


def _normalize_logradouro(raw: str) -> str:
    """Normalize a street name for fuzzy matching: lowercase, ASCII, collapse spaces."""
    s = raw.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s


def _find_col(headers_lower: list[str], candidates: set[str]) -> int | None:
    for i, h in enumerate(headers_lower):
        if h in candidates:
            return i
    return None


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_cnefe_zips() -> list[Path]:
    """Download CNEFE coordinate ZIPs for DF and GO into data/raw/prospeccao/cnefe/."""
    dirs = pathutil.ensure_raw_layout()
    out_dir = dirs["cnefe"]
    base = config.CNEFE_BASE.rstrip("/") + "/"
    downloaded: list[Path] = []
    for uf, filename in config.CNEFE_FILES.items():
        url = f"{base}{filename}"
        dest = out_dir / filename
        logger.info("CNEFE download: %s -> %s", url, dest)
        try:
            download_url_to_path(url, dest, resume=True, skip_if_same_size=True)
            downloaded.append(dest)
        except Exception:
            logger.exception("Failed to download CNEFE %s", uf)
    return downloaded


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

GeocodeLookup = dict[tuple[str, str, str], tuple[float, float, float]]


def _iter_csv_in_zip(zip_path: Path):
    """Yield (headers, row_iterator) from the first CSV inside a ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and not n.startswith("__MACOSX")
        ]
        if not csv_names:
            logger.warning("No CSV found in %s", zip_path)
            return
        for csv_name in csv_names:
            with zf.open(csv_name) as raw:
                reader = csv.reader(
                    io.TextIOWrapper(raw, encoding="utf-8", errors="replace"),
                    delimiter=";",
                )
                headers = next(reader, None)
                if headers is None:
                    continue
                yield headers, reader


def parse_cnefe_zip(
    zip_path: Path,
    *,
    filter_ride: bool = True,
) -> GeocodeLookup:
    """Parse a CNEFE coordinate ZIP and return a geocode lookup dict.

    Keys: (cep, logradouro_normalized, numero)
    Values: (latitude, longitude, quality)
    Quality is 1.0 for CNEFE (high confidence census data).
    """
    lookup: GeocodeLookup = {}
    for headers, rows in _iter_csv_in_zip(zip_path):
        headers_lower = [h.strip().lower() for h in headers]
        lat_i = _find_col(headers_lower, _LAT_CANDIDATES)
        lon_i = _find_col(headers_lower, _LON_CANDIDATES)
        cep_i = _find_col(headers_lower, _CEP_CANDIDATES)
        logr_i = _find_col(headers_lower, _LOGRADOURO_CANDIDATES)
        num_i = _find_col(headers_lower, _NUMERO_CANDIDATES)
        muni_i = _find_col(headers_lower, _MUNICIPIO_CANDIDATES)

        if lat_i is None or lon_i is None:
            logger.warning("Could not find lat/lon columns in %s: %s", zip_path, headers_lower)
            continue
        if cep_i is None and logr_i is None:
            logger.warning("No CEP or logradouro column in %s", zip_path)
            continue

        total = 0
        kept = 0
        for row in rows:
            total += 1
            try:
                lat_raw = row[lat_i].strip().replace(",", ".")
                lon_raw = row[lon_i].strip().replace(",", ".")
                if not lat_raw or not lon_raw:
                    continue
                lat = float(lat_raw)
                lon = float(lon_raw)
            except (ValueError, IndexError):
                continue

            if filter_ride and muni_i is not None:
                muni_val = row[muni_i].strip() if len(row) > muni_i else ""
                if muni_val and muni_val != _BRASILIA_CODE and muni_val not in _RIDE_CODES:
                    continue

            cep = row[cep_i].strip() if cep_i is not None and len(row) > cep_i else ""
            logr = _normalize_logradouro(row[logr_i]) if logr_i is not None and len(row) > logr_i else ""
            num = row[num_i].strip() if num_i is not None and len(row) > num_i else ""

            if not cep and not logr:
                continue

            key = (cep, logr, num)
            lookup[key] = (lat, lon, 1.0)
            kept += 1

        logger.info("CNEFE %s: %d rows scanned, %d kept", zip_path.name, total, kept)

    return lookup


def build_cnefe_lookup(cnefe_dir: Path | None = None) -> GeocodeLookup:
    """Build the full geocode lookup from all downloaded CNEFE ZIPs."""
    if cnefe_dir is None:
        dirs = pathutil.ensure_raw_layout()
        cnefe_dir = dirs["cnefe"]

    combined: GeocodeLookup = {}
    for uf, filename in config.CNEFE_FILES.items():
        path = cnefe_dir / filename
        if not path.exists():
            logger.warning("CNEFE %s not found at %s", filename, cnefe_dir)
            continue
        partial = parse_cnefe_zip(path, filter_ride=(uf == "GO"))
        combined.update(partial)

    logger.info("CNEFE combined lookup: %d address entries", len(combined))
    return combined


def geocode_address(
    lookup: GeocodeLookup,
    cep: str | None,
    logradouro: str | None,
    numero: str | None,
) -> tuple[float, float, float] | None:
    """Try to geocode an address using the CNEFE lookup.

    Attempts progressively looser matching:
      1. (cep, logradouro_norm, numero)
      2. (cep, logradouro_norm, "")     — any number on same street
      3. (cep, "", "")                   — centroid of CEP block
    """
    cep = (cep or "").strip()
    logr = _normalize_logradouro(logradouro) if logradouro else ""
    num = (numero or "").strip()

    if cep and logr and num:
        hit = lookup.get((cep, logr, num))
        if hit:
            return hit

    if cep and logr:
        hit = lookup.get((cep, logr, ""))
        if hit:
            return (hit[0], hit[1], 0.8)

    if cep:
        hit = lookup.get((cep, "", ""))
        if hit:
            return (hit[0], hit[1], 0.5)

    return None


def sync_cnefe(download: bool = True) -> dict[str, Any]:
    """Download + parse CNEFE files and return stats."""
    stats: dict[str, Any] = {"downloaded": [], "lookup_size": 0}
    if download:
        downloaded = download_cnefe_zips()
        stats["downloaded"] = [str(p) for p in downloaded]
    lookup = build_cnefe_lookup()
    stats["lookup_size"] = len(lookup)
    return stats
