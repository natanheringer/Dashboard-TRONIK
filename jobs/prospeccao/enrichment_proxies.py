"""Optional OSM / INEP / CNES staging lookups for ranker enrichment (Sócrates).

Reads precomputed parquet or CSV paths from environment:
  TRONIK_OSM_POI_PARQUET
  TRONIK_INEP_CENSO_PARQUET
  TRONIK_CNES_PARQUET

When files are missing or unreadable, ``lookup_proxies`` returns 0.0 for all signals.
"""

from __future__ import annotations

import csv
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.neighbors import BallTree

from jobs.prospeccao.ranker_contract import FEATURE_NAMES, haversine_km

logger = logging.getLogger(__name__)

PROXY_KEYS = ("osm_poi_ree_density", "inep_institution_proxy", "cnes_health_proxy")
if set(PROXY_KEYS) - set(FEATURE_NAMES):
    raise RuntimeError(
        "PROXY_KEYS must name features present in ranker_contract.FEATURE_NAMES "
        f"(unknown={sorted(set(PROXY_KEYS) - set(FEATURE_NAMES))})"
    )

_ENV_OSM = "TRONIK_OSM_POI_PARQUET"
_ENV_INEP = "TRONIK_INEP_CENSO_PARQUET"
_ENV_CNES = "TRONIK_CNES_PARQUET"

_RADIUS_KM = float(os.getenv("TRONIK_ENRICHMENT_RADIUS_KM", "3.0"))
_OSM_CAP = 50
_INEP_CAP = 25
_CNES_CAP = 20

_LAT_COLS = frozenset({"latitude", "lat", "y"})
_LON_COLS = frozenset({"longitude", "lon", "lng", "long", "x"})
_RA_COLS = frozenset({"ra", "regiao_administrativa", "regiao"})
_MUN_COLS = frozenset({"municipio", "municipio_nome", "nome_municipio", "city"})
_COUNT_COLS = frozenset({
    "count",
    "density",
    "institution_count",
    "escolas",
    "unidades",
    "establishment_count",
    "poi_count",
    "n",
})


class _OsmIndex:
    __slots__ = ("points",)

    def __init__(self, points: list[tuple[float, float]]) -> None:
        self.points = points


class _AggregateIndex:
    __slots__ = ("by_ra", "by_municipio", "points")

    def __init__(
        self,
        *,
        by_ra: dict[str, float],
        by_municipio: dict[str, float],
        points: list[tuple[float, float]],
    ) -> None:
        self.by_ra = by_ra
        self.by_municipio = by_municipio
        self.points = points


_cache: dict[str, Any] = {
    "osm": None,
    "inep": None,
    "cnes": None,
    "loaded": False,
    "ball_trees": {},  # Cache for BallTree per points hash
}

_LOAD_LOCK = threading.Lock()


def clear_proxy_caches() -> None:
    """Reset module caches (tests)."""
    _cache["osm"] = None
    _cache["inep"] = None
    _cache["cnes"] = None
    _cache["loaded"] = False
    _cache["ball_trees"] = {}


def _norm_key(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def _norm_density(count: float, cap: float) -> float:
    if count <= 0:
        return 0.0
    return min(1.0, math.log1p(count) / math.log1p(cap))


def _clamp_proxy(value: float, cap: float) -> float:
    """Accept pre-normalized [0,1] staging values or raw counts."""
    if value <= 1.0:
        return max(0.0, min(1.0, value))
    return _norm_density(value, cap)


def _pick_col(row: dict[str, Any], candidates: frozenset[str]) -> str | None:
    lower_map = {str(k).strip().lower(): k for k in row}
    for cand in candidates:
        if cand in lower_map:
            return str(lower_map[cand])
    return None


def _float_val(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    if suffix in (".parquet", ".pq"):
        try:
            import pandas as pd
        except ImportError:
            logger.warning("pandas ausente — não foi possível ler %s", path)
            return []
        frame = pd.read_parquet(path)
        return frame.to_dict(orient="records")
    logger.warning("Formato não suportado para enrichment: %s", path)
    return []


def _path_from_env(name: str) -> Path | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _build_osm_index(rows: list[dict[str, Any]]) -> _OsmIndex | None:
    if not rows:
        return None

    points: list[tuple[float, float]] = []

    # Detect column names once from first row to avoid O(N) recomputation per row
    lat_col = _pick_col(rows[0], _LAT_COLS)
    lon_col = _pick_col(rows[0], _LON_COLS)

    if not lat_col or not lon_col:
        return None

    for row in rows:
        lat = _float_val(row.get(lat_col))
        lon = _float_val(row.get(lon_col))
        if lat is None or lon is None:
            continue
        points.append((lat, lon))
    return _OsmIndex(points) if points else None


def _build_aggregate_index(rows: list[dict[str, Any]]) -> _AggregateIndex | None:
    if not rows:
        return None

    by_ra: dict[str, float] = {}
    by_municipio: dict[str, float] = {}
    points: list[tuple[float, float]] = []

    # Detect column names once from first row to avoid O(N) recomputation per row
    ra_col = _pick_col(rows[0], _RA_COLS)
    mun_col = _pick_col(rows[0], _MUN_COLS)
    count_col = _pick_col(rows[0], _COUNT_COLS)
    lat_col = _pick_col(rows[0], _LAT_COLS)
    lon_col = _pick_col(rows[0], _LON_COLS)

    for row in rows:
        if lat_col and lon_col:
            lat = _float_val(row.get(lat_col))
            lon = _float_val(row.get(lon_col))
            if lat is not None and lon is not None:
                points.append((lat, lon))

        value = 1.0
        if count_col:
            parsed = _float_val(row.get(count_col))
            if parsed is not None:
                value = parsed

        if ra_col:
            key = _norm_key(row.get(ra_col))
            if key:
                by_ra[key] = max(by_ra.get(key, 0.0), value)
        if mun_col:
            key = _norm_key(row.get(mun_col))
            if key:
                by_municipio[key] = max(by_municipio.get(key, 0.0), value)

    if not by_ra and not by_municipio and not points:
        return None
    return _AggregateIndex(by_ra=by_ra, by_municipio=by_municipio, points=points)


def _ensure_loaded() -> None:
    # Double-checked locking for thread-safe initialization
    if _cache["loaded"]:
        return

    with _LOAD_LOCK:
        # Re-check after acquiring lock
        if _cache["loaded"]:
            return
        _cache["loaded"] = True

        osm_path = _path_from_env(_ENV_OSM)
        if osm_path:
            rows = _load_rows(osm_path)
            _cache["osm"] = _build_osm_index(rows)
            if _cache["osm"] is None:
                logger.info("OSM enrichment: nenhum ponto válido em %s", osm_path)

        inep_path = _path_from_env(_ENV_INEP)
        if inep_path:
            rows = _load_rows(inep_path)
            _cache["inep"] = _build_aggregate_index(rows)
            if _cache["inep"] is None:
                logger.info("INEP enrichment: nenhuma linha utilizável em %s", inep_path)

        cnes_path = _path_from_env(_ENV_CNES)
        if cnes_path:
            rows = _load_rows(cnes_path)
            _cache["cnes"] = _build_aggregate_index(rows)
            if _cache["cnes"] is None:
                logger.info("CNES enrichment: nenhuma linha utilizável em %s", cnes_path)


def _count_within_radius(
    lat: float,
    lon: float,
    points: list[tuple[float, float]],
    radius_km: float,
) -> int:
    """Count POIs within radius_km using BallTree spatial index."""
    if not points:
        return 0

    # Compute hash for caching BallTree
    points_hash = hash(tuple(points))

    # Lazy-build BallTree on first use with double-checked locking
    ball_trees = _cache.get("ball_trees", {})
    if points_hash not in ball_trees:
        with _LOAD_LOCK:
            # Re-read from cache after acquiring lock (double-checked locking correct)
            ball_trees = _cache.get("ball_trees", {})
            if points_hash not in ball_trees:
                # Convert lat/lon to radians for Haversine metric
                pts_rad = np.radians(np.asarray(points, dtype=float))
                ball_trees = dict(ball_trees)  # Do not mutate cache dict directly
                ball_trees[points_hash] = BallTree(pts_rad, metric="haversine")
                _cache["ball_trees"] = ball_trees

    tree = _cache.get("ball_trees", {})[points_hash]
    # Query radius in radians: radius_km / Earth radius (6371 km)
    radius_rad = radius_km / 6371.0
    query_pt = np.radians(np.array([[lat, lon]], dtype=float))

    # count_only=True returns array of counts
    counts = tree.query_radius(query_pt, r=radius_rad, count_only=True)
    return int(counts[0])


def _aggregate_lookup(
    index: _AggregateIndex | None,
    *,
    lat: float | None,
    lon: float | None,
    ra: str | None,
    municipio: str | None,
    cap: float,
) -> float:
    if index is None:
        return 0.0
    ra_key = _norm_key(ra)
    if ra_key and ra_key in index.by_ra:
        return _clamp_proxy(float(index.by_ra[ra_key]), cap)
    mun_key = _norm_key(municipio)
    if mun_key and mun_key in index.by_municipio:
        return _clamp_proxy(float(index.by_municipio[mun_key]), cap)
    if lat is not None and lon is not None and index.points:
        count = _count_within_radius(lat, lon, index.points, _RADIUS_KM)
        return _norm_density(float(count), cap)
    return 0.0


def lookup_proxies(
    lat: float | None,
    lon: float | None,
    ra: str | None,
    municipio: str | None,
) -> dict[str, float]:
    """Return OSM/INEP/CNES proxy floats in [0, 1]; defaults to 0.0 when staging is absent."""
    _ensure_loaded()
    out = dict.fromkeys(PROXY_KEYS, 0.0)

    if lat is not None and lon is not None:
        osm_index: _OsmIndex | None = _cache.get("osm")
        if osm_index and osm_index.points:
            count = _count_within_radius(lat, lon, osm_index.points, _RADIUS_KM)
            out["osm_poi_ree_density"] = _norm_density(float(count), _OSM_CAP)

    inep_index: _AggregateIndex | None = _cache.get("inep")
    out["inep_institution_proxy"] = _aggregate_lookup(
        inep_index,
        lat=lat,
        lon=lon,
        ra=ra,
        municipio=municipio,
        cap=_INEP_CAP,
    )

    cnes_index: _AggregateIndex | None = _cache.get("cnes")
    out["cnes_health_proxy"] = _aggregate_lookup(
        cnes_index,
        lat=lat,
        lon=lon,
        ra=ra,
        municipio=municipio,
        cap=_CNES_CAP,
    )

    return out


def probe_enrichment_files() -> dict[str, Any]:
    """Report whether proxy staging files exist and are loadable."""
    clear_proxy_caches()
    _ensure_loaded()
    paths = {
        "osm": os.getenv(_ENV_OSM, ""),
        "inep": os.getenv(_ENV_INEP, ""),
        "cnes": os.getenv(_ENV_CNES, ""),
    }
    status: dict[str, Any] = {"radius_km": _RADIUS_KM, "sources": {}}
    for key, env_name in (("osm", _ENV_OSM), ("inep", _ENV_INEP), ("cnes", _ENV_CNES)):
        raw = paths[key]
        path = Path(raw) if raw else None
        entry: dict[str, Any] = {
            "env": env_name,
            "path": raw or None,
            "exists": bool(path and path.is_file()),
            "loaded": False,
            "rows_hint": None,
        }
        if entry["exists"] and path is not None:
            rows = _load_rows(path)
            entry["rows_hint"] = len(rows)
            if key == "osm":
                entry["loaded"] = _cache.get("osm") is not None
            else:
                entry["loaded"] = _cache.get(key) is not None
        status["sources"][key] = entry
    return status
