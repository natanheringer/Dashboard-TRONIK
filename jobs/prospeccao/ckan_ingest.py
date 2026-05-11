"""
Catálogo CKAN do Distrito Federal (dados.df.gov.br).

- package_search com paginação e pausa entre pedidos
- organization_list
- package_show opcional (metadados completos + recursos)
- download de recursos com limite MB e deduplicação por URL
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional, Set

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path, session, throttle

logger = logging.getLogger(__name__)


def _action_url() -> str:
    return f"{config.CKAN_BASE_URL}/api/3/action/"


def ckan_call(action: str, payload: Optional[dict[str, Any]] = None) -> Any:
    url = _action_url() + action
    throttle()
    r = session().post(url, json=payload or {}, timeout=config.HTTP_TIMEOUT_S)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"CKAN error ({action}): {body}")
    return body["result"]


def organization_slugs() -> list[str]:
    """Lista slugs de organizações (para iterar downloads)."""
    return list(ckan_call("organization_list", {"all_fields": False}))


def fetch_package_search(
    *,
    rows: int = 100,
    start: int = 0,
    fq: Optional[str] = None,
    q: str = "",
) -> dict[str, Any]:
    rows = min(rows, config.CKAN_ROWS_PER_PAGE)
    return ckan_call(
        "package_search",
        {
            "q": q,
            "rows": rows,
            "start": start,
            **({"fq": fq} if fq else {}),
        },
    )


def fetch_package_show(name: str) -> dict[str, Any]:
    return ckan_call("package_show", {"id": name})


def sync_catalog_metadata(
    *,
    max_packages: int = 500,
    fq_org: Optional[str] = None,
    out_name: str = "package_search_summary.jsonl",
) -> Path:
    """Pagina package_search e grava JSONL resumido."""
    dirs = pathutil.ensure_raw_layout()
    out = dirs["ckan"] / out_name
    fq = f"organization:{fq_org}" if fq_org else None
    start = 0
    count = 0
    rows = min(config.CKAN_ROWS_PER_PAGE, max_packages)
    with out.open("w", encoding="utf-8") as fp:
        while count < max_packages:
            batch_rows = min(rows, max_packages - count)
            res = fetch_package_search(rows=batch_rows, start=start, fq=fq)
            results = res.get("results") or []
            if not results:
                break
            for pkg in results:
                line = {
                    "name": pkg.get("name"),
                    "title": pkg.get("title"),
                    "organization": (pkg.get("organization") or {}).get("name"),
                    "num_resources": len(pkg.get("resources") or []),
                    "metadata_modified": pkg.get("metadata_modified"),
                    "tags": [t.get("name") for t in (pkg.get("tags") or [])],
                }
                fp.write(json.dumps(line, ensure_ascii=False) + "\n")
                count += 1
            start += len(results)
            if len(results) < batch_rows:
                break
    logger.info("CKAN metadata: %s registros -> %s", count, out)
    pathutil.write_manifest(
        "ckan_catalog",
        {"file": str(out), "count": count, "fq_org": fq_org, "base": config.CKAN_BASE_URL},
    )
    return out


def sync_package_show_details(
    *,
    max_packages: int = 80,
    fq_org: Optional[str] = None,
) -> Path:
    """Grava um JSONL com package_show completo (mais pesado na API)."""
    dirs = pathutil.ensure_raw_layout()
    out = dirs["ckan"] / "package_show_details.jsonl"
    start = 0
    count = 0
    fq = f"organization:{fq_org}" if fq_org else None
    rows = min(config.CKAN_ROWS_PER_PAGE, max_packages)
    with out.open("w", encoding="utf-8") as fp:
        while count < max_packages:
            batch = min(rows, max_packages - count)
            res = fetch_package_search(rows=batch, start=start, fq=fq)
            results = res.get("results") or []
            if not results:
                break
            for pkg in results:
                name = pkg.get("name")
                if not name:
                    continue
                try:
                    full = fetch_package_show(name)
                    fp.write(json.dumps(full, ensure_ascii=False) + "\n")
                    count += 1
                except Exception as e:
                    logger.warning("package_show falhou %s: %s", name, e)
            start += len(results)
            if len(results) < batch:
                break
    logger.info("CKAN package_show: %s pacotes -> %s", count, out)
    pathutil.write_manifest(
        "ckan_package_show",
        {"file": str(out), "count": count, "fq_org": fq_org},
    )
    return out


def download_resources_for_org(
    org_name: str,
    *,
    max_packages: int = 40,
    max_resource_mb: int = 80,
    extensions: Optional[set[str]] = None,
    paginate: bool = True,
) -> list[Path]:
    """Baixa recursos; com paginate=True percorre várias páginas de package_search."""
    exts = extensions or {".csv", ".json", ".zip", ".xlsx", ".xls", ".geojson", ".kml", ".kmz"}
    max_bytes = max_resource_mb * 1024 * 1024
    dirs = pathutil.ensure_raw_layout()
    org_slug = org_name.strip().replace("/", "_")
    org_dir = dirs["ckan"] / "orgs" / org_slug
    org_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    seen_urls: Set[str] = set()
    start = 0
    packages_seen = 0
    rows = config.CKAN_ROWS_PER_PAGE

    while packages_seen < max_packages:
        res = fetch_package_search(
            rows=min(rows, max_packages - packages_seen),
            start=start,
            fq=f"organization:{org_slug}",
        )
        packages = res.get("results") or []
        if not packages:
            break
        for pkg in packages:
            if packages_seen >= max_packages:
                break
            packages_seen += 1
            slug = (pkg.get("name") or "sem_nome").replace("/", "_")
            pkg_dir = org_dir / slug
            pkg_dir.mkdir(parents=True, exist_ok=True)
            for res_item in pkg.get("resources") or []:
                url = (res_item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                fmt = (res_item.get("format") or "").lower()
                name = (res_item.get("name") or "resource").replace("/", "_")
                path_hint = Path(name)
                suf = path_hint.suffix.lower()
                if suf not in exts and fmt not in {
                    "csv",
                    "json",
                    "zip",
                    "xlsx",
                    "xls",
                    "geojson",
                    "text",
                    "api",
                    "shp",
                }:
                    continue
                if not suf:
                    suf = f".{fmt}" if fmt and fmt != "api" else ".bin"
                rid = res_item.get("id") or "id"
                dest = pkg_dir / f"{rid}_{path_hint.name}"
                if not dest.suffix:
                    dest = dest.with_suffix(suf)
                try:
                    logger.info("Baixando %s", url[:160])
                    dr = download_url_to_path(
                        url,
                        dest,
                        max_bytes=max_bytes,
                        resume=True,
                        skip_if_same_size=True,
                        compute_hash=False,
                    )
                    if dr.truncated:
                        logger.warning("Truncado a %s MB: %s", max_resource_mb, dest.name)
                    if not dr.skipped:
                        seen_urls.add(url)
                    saved.append(dest)
                except Exception as e:
                    logger.error("Falha recurso: %s", e)
        if not paginate:
            break
        start += len(packages)
        if len(packages) < rows:
            break

    pathutil.write_manifest(
        "ckan_download",
        {"org": org_slug, "files": [str(p) for p in saved], "count": len(saved)},
    )
    return saved


def sync_default_ckan_orgs(
    *,
    orgs: Optional[list[str]] = None,
    max_packages_per_org: int = 15,
    max_mb: int = 40,
) -> dict[str, list[Path]]:
    """Percorre lista de organizações (default TRONIK_CKAN_DEFAULT_ORGS)."""
    slugs = orgs or [o.strip() for o in config.DEFAULT_CKAN_ORGS if o.strip()]
    out: dict[str, list[Path]] = {}
    for org in slugs:
        try:
            out[org] = download_resources_for_org(
                org,
                max_packages=max_packages_per_org,
                max_resource_mb=max_mb,
                paginate=True,
            )
        except Exception as e:
            logger.error("Org CKAN %s: %s", org, e)
            out[org] = []
    pathutil.write_manifest("ckan_multi_org", {k: [str(p) for p in v] for k, v in out.items()})
    return out
