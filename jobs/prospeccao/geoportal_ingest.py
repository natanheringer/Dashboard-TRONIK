"""
Camadas ArcGIS REST (Geoportal / SISDIA / IBRAM) — export GeoJSON paginado.

O URL default aponta para Regiões Administrativas (polígonos). Ajuste
TRONIK_GEOPORTAL_RA_FEATURE_URL para outra camada FeatureServer.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import get_json, throttle

logger = logging.getLogger(__name__)

_ARCGIS_TIMEOUT = float(config.GEOPORTAL_TIMEOUT_S)


def query_layer_geojson_page(
    base_feature_url: str,
    *,
    offset: int,
    page_size: int = 2000,
    where: str = "1=1",
    out_fields: str = "*",
) -> dict[str, Any]:
    """
    ArcGIS Feature Layer query com f=geojson.
    base_feature_url exemplo: .../FeatureServer/0
    """
    base = base_feature_url.rstrip("/")
    params = {
        "where": where,
        "outFields": out_fields,
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": str(offset),
        "resultRecordCount": str(page_size),
    }
    url = f"{base}/query?{urlencode(params)}"
    throttle()
    return get_json(url, timeout=_ARCGIS_TIMEOUT)


def sync_ra_geojson(
    *,
    feature_url: Optional[str] = None,
    page_size: int = 2000,
    max_features: Optional[int] = None,
) -> Path:
    """Concatena features num único FeatureCollection (respeitando limite)."""
    url_base = feature_url or config.GEOPORTAL_RA_FEATURE_URL
    dirs = pathutil.ensure_raw_layout()
    out = dirs["geoportal"] / "regioes_administrativas.geojson"

    features: list[dict[str, Any]] = []
    offset = 0
    total = 0
    while True:
        chunk = query_layer_geojson_page(url_base, offset=offset, page_size=page_size)
        feats = (chunk.get("features") or []) if isinstance(chunk, dict) else []
        if not feats:
            break
        features.extend(feats)
        total += len(feats)
        offset += len(feats)
        if len(feats) < page_size:
            break
        if max_features is not None and total >= max_features:
            features = features[:max_features]
            break

    fc = {"type": "FeatureCollection", "features": features}
    out.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    logger.info("Geoportal: %s features -> %s", len(features), out)
    pathutil.write_manifest("geoportal_ra", {"path": str(out), "count": len(features), "url": url_base})
    return out
