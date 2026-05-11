"""API de localidades IBGE (municípios do DF, estados, etc.) — JSON estável."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import get_json, throttle

logger = logging.getLogger(__name__)


def _url(path: str) -> str:
    return f"{config.IBGE_API_BASE}{path}"


def fetch_municipios_uf(uf: str = config.IBGE_UF_DF) -> list[dict[str, Any]]:
    throttle()
    return get_json(_url(f"/localidades/estados/{uf}/municipios"))


def fetch_estados() -> list[dict[str, Any]]:
    throttle()
    return get_json(_url("/localidades/estados"))


def sync_df_municipios() -> Path:
    dirs = pathutil.ensure_raw_layout()
    out = dirs["ibge"] / "municipios_uf_53.json"
    data = fetch_municipios_uf()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("IBGE: %s municípios UF %s -> %s", len(data), config.IBGE_UF_DF, out)
    pathutil.write_manifest("ibge_municipios_df", {"path": str(out), "count": len(data)})
    return out


def sync_estados() -> Path:
    dirs = pathutil.ensure_raw_layout()
    out = dirs["ibge"] / "estados.json"
    data = fetch_estados()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    pathutil.write_manifest("ibge_estados", {"path": str(out), "count": len(data)})
    return out
