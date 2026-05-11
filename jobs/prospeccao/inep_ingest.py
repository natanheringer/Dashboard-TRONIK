"""INEP — microdados Censo Escolar (ZIP) ou CSV direto via env."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path, session

logger = logging.getLogger(__name__)


def download_censo_escolar_csv(
    *,
    max_mb: int = 200,
    dest_name: str = "censo_escolar_externo.csv",
) -> Path:
    """TRONIK_INEP_CENSO_ESCOLAR_CSV_URL — ficheiro único (ex.: export manual)."""
    url = (config.INEP_CENSO_ESCOLAR_CSV_URL or "").strip()
    if not url:
        raise RuntimeError("Defina TRONIK_INEP_CENSO_ESCOLAR_CSV_URL.")
    dirs = pathutil.ensure_raw_layout()
    dest = dirs["inep"] / dest_name
    max_bytes = max_mb * 1024 * 1024
    download_url_to_path(url, dest, max_bytes=max_bytes, resume=True)
    pathutil.write_manifest("inep_csv", {"url": url, "path": str(dest)})
    return dest


def _zip_url_for_year(year: str) -> str:
    return config.INEP_MICRODADOS_BASE.format(year=year)


def download_censo_escolar_microdados_zip(
    year: Optional[str] = None,
    *,
    max_mb: Optional[int] = None,
) -> Path:
    """
    ZIP oficial microdados (vários GB em anos recentes).
    max_mb=None descarrega completo (cuidado em disco).
    """
    y = year or config.INEP_CENSO_ESCOLAR_YEAR
    url = _zip_url_for_year(y)
    dirs = pathutil.ensure_raw_layout()
    dest = dirs["inep"] / f"microdados_censo_escolar_{y}.zip"
    max_bytes = max_mb * 1024 * 1024 if max_mb else None
    logger.info("INEP microdados: %s", url)
    download_url_to_path(url, dest, max_bytes=max_bytes, resume=True, skip_if_same_size=True)
    pathutil.write_manifest("inep_microdados", {"year": y, "url": url, "path": str(dest)})
    return dest


def probe_censo_escolar_years(years: Optional[List[str]] = None) -> Optional[str]:
    """Devolve o primeiro ano cujo ZIP responde HEAD OK."""
    for y in years or ["2024", "2023", "2022", "2021"]:
        url = _zip_url_for_year(y)
        try:
            r = session().head(url, allow_redirects=True, timeout=config.HTTP_TIMEOUT_S)
            if r.ok:
                logger.info("INEP: ano disponível %s (%s)", y, url)
                return y
        except Exception as e:
            logger.debug("INEP probe %s: %s", y, e)
    return None
