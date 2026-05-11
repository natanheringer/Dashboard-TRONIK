"""Geofabrik — extract regional .osm.pbf."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path

logger = logging.getLogger(__name__)


def download_pbf(
    url: Optional[str] = None,
    *,
    max_mb: Optional[int] = None,
    filename: str = "extract.osm.pbf",
) -> Path:
    u = url or config.GEOFABRIK_DEFAULT_PBF
    dirs = pathutil.ensure_raw_layout()
    dest = dirs["osm"] / filename
    max_bytes = max_mb * 1024 * 1024 if max_mb else None
    logger.info("Geofabrik: %s -> %s (max_mb=%s)", u, dest, max_mb)
    download_url_to_path(u, dest, max_bytes=max_bytes, resume=True, skip_if_same_size=True)
    pathutil.write_manifest(
        "geofabrik_pbf",
        {"url": u, "path": str(dest), "truncated": max_bytes is not None},
    )
    return dest
