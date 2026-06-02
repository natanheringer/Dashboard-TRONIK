"""CNES — ZIP via URL explícita (competência mensal DATASUS)."""

from __future__ import annotations

import logging
from pathlib import Path

from jobs.prospeccao import config, paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path

logger = logging.getLogger(__name__)


def download_cnes_zip(*, max_mb: int | None = None) -> Path:
    url = (config.CNES_BASE_ZIP_URL or "").strip()
    if not url:
        raise RuntimeError(
            "Defina TRONIK_CNES_BASE_ZIP_URL (ZIP oficial CNES, ex.: competência mensal). "
            "Portal: https://cnes.datasus.gov.br/pages/downloads/arquivosBaseDados.jsp"
        )
    dirs = pathutil.ensure_raw_layout()
    name = url.rstrip("/").split("/")[-1] or "cnes_base.zip"
    dest = dirs["cnes"] / name
    max_bytes = max_mb * 1024 * 1024 if max_mb else None
    logger.info("CNES: %s -> %s", url[:120], dest)
    download_url_to_path(url, dest, max_bytes=max_bytes, resume=True, skip_if_same_size=True)
    pathutil.write_manifest("cnes", {"url": url, "path": str(dest)})
    return dest
