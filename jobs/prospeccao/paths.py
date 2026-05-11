"""Diretórios de saída e manifesto de execução."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jobs.prospeccao import config


def ensure_raw_layout() -> dict[str, Path]:
    base = config.RAW_DIR
    sub = {
        "base": base,
        "ckan": base / "ckan_df",
        "receita": base / "receita_cnpj",
        "osm": base / "osm_geofabrik",
        "inep": base / "inep",
        "cnes": base / "cnes",
        "pncp": base / "pncp",
        "pncp_consulta": base / "pncp_consulta",
        "ibge": base / "ibge",
        "geoportal": base / "geoportal",
        "reports": base / "_reports",
        "meta": base / "_manifest",
    }
    for p in sub.values():
        p.mkdir(parents=True, exist_ok=True)
    return sub


def write_manifest(name: str, payload: dict[str, Any]) -> Path:
    dirs = ensure_raw_layout()
    meta = dirs["meta"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = meta / f"{name}_{stamp}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def write_report(name: str, payload: dict[str, Any]) -> Path:
    dirs = ensure_raw_layout()
    rep = dirs["reports"] / f"{name}.json"
    rep.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return rep
