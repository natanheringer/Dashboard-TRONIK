"""
Orquestra várias fontes numa única execução (relatório JSON em _reports).

steps (lista): ckan_meta, ckan_links, ckan_show, ibge, geoportal, pncp, ckan_orgs, receita_probe, inep_probe
"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import UTC, datetime
from typing import Any

from jobs.prospeccao import paths as pathutil

logger = logging.getLogger(__name__)


def run_harvest(
    steps: list[str] | None = None,
    *,
    dry_run: bool = False,
    ckan_max: int = 200,
    ckan_show_max: int = 30,
    ckan_link_max: int | None = 300,
    pncp_dias: int = 14,
    pncp_max_pages: int = 80,
    ckan_org_max_pkg: int = 8,
    ckan_org_max_mb: int = 25,
) -> dict[str, Any]:
    """
    Executa passos na ordem; erros num passo não cancelam os seguintes (acumulam em errors).
    """
    steps = steps or [
        "ibge",
        "geoportal",
        "ckan_meta",
        "ckan_links",
        "pncp",
        "ckan_orgs",
    ]
    pathutil.ensure_raw_layout()
    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "steps": steps,
        "ok": {},
        "errors": {},
        "durations_s": {},
    }

    def run(name: str, fn: Any) -> None:
        started = time.perf_counter()
        logger.info("Harvest step start: %s", name)
        if dry_run:
            report["ok"][name] = "skipped_dry_run"
            report["durations_s"][name] = 0.0
            logger.info("Harvest step skipped (dry-run): %s", name)
            return
        try:
            out = fn()
            if isinstance(out, dict) and out:
                sample = next(iter(out.values()))
                if isinstance(sample, list) and sample and hasattr(sample[0], "as_posix"):
                    report["ok"][name] = {k: [str(p) for p in v] for k, v in out.items()}
                else:
                    report["ok"][name] = out
            else:
                report["ok"][name] = out
            elapsed = time.perf_counter() - started
            report["durations_s"][name] = round(elapsed, 3)
            logger.info("Harvest step ok: %s duration=%.3fs", name, elapsed)
        except Exception as e:
            elapsed = time.perf_counter() - started
            report["durations_s"][name] = round(elapsed, 3)
            report["errors"][name] = {"error": str(e), "trace": traceback.format_exc()}
            logger.exception("Harvest step failed: %s duration=%.3fs", name, elapsed)

    if "ibge" in steps:
        from jobs.prospeccao.ibge_ingest import sync_df_municipios, sync_estados, sync_ride_entorno

        run("ibge_municipios", lambda: sync_df_municipios())
        run("ibge_ride_entorno", lambda: sync_ride_entorno())
        run("ibge_estados", lambda: sync_estados())

    if "geoportal" in steps:
        from jobs.prospeccao.geoportal_ingest import sync_ra_geojson

        run("geoportal_ra", lambda: sync_ra_geojson(max_features=5000))

    if "ckan_meta" in steps:
        from jobs.prospeccao.ckan_ingest import sync_catalog_metadata

        run("ckan_meta", lambda: sync_catalog_metadata(max_packages=ckan_max))

    if "ckan_links" in steps:
        from jobs.prospeccao.ckan_ingest import validate_ckan_resource_links

        run(
            "ckan_links",
            lambda: validate_ckan_resource_links(
                max_packages=ckan_max,
                max_links=ckan_link_max,
            ),
        )

    if "ckan_show" in steps:
        from jobs.prospeccao.ckan_ingest import sync_package_show_details

        run("ckan_show", lambda: sync_package_show_details(max_packages=ckan_show_max))

    if "pncp" in steps:
        from jobs.prospeccao.pncp_ingest import sync_contratacoes_df_periodo

        run(
            "pncp_contratacoes",
            lambda: sync_contratacoes_df_periodo(dias=pncp_dias, max_pages=pncp_max_pages),
        )

    if "ckan_orgs" in steps:
        from jobs.prospeccao.ckan_ingest import sync_default_ckan_orgs

        run(
            "ckan_orgs",
            lambda: sync_default_ckan_orgs(
                max_packages_per_org=ckan_org_max_pkg,
                max_mb=ckan_org_max_mb,
            ),
        )

    if "receita_probe" in steps:
        from jobs.prospeccao.receita_ingest import discover_working_base

        run("receita_probe", lambda: discover_working_base() or "none")

    if "inep_probe" in steps:
        from jobs.prospeccao.inep_ingest import probe_censo_escolar_years

        run("inep_probe", lambda: probe_censo_escolar_years() or "none")

    if "cnefe" in steps:
        from jobs.prospeccao.cnefe_ingest import sync_cnefe

        run("cnefe", lambda: sync_cnefe(download=True))

    if "receita_parse" in steps:
        from jobs.prospeccao import paths as _pathutil
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.receita_parse import parse_estabelecimentos_to_db
        _dirs = _pathutil.ensure_raw_layout()

        def _receita_parse():
            with session_scope() as db:
                result = parse_estabelecimentos_to_db(db, _dirs["receita"])
                db.commit()
            return result

        run("receita_parse", _receita_parse)

    if "normalize" in steps:
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.normalize_candidates import normalize_all

        def _normalize():
            with session_scope() as db:
                return normalize_all(db)

        run("normalize", _normalize)

    if "aneel" in steps:
        from jobs.prospeccao.aneel_ingest import sync_aneel_consumidores
        from jobs.prospeccao.db import session_scope

        def _aneel():
            with session_scope() as db:
                result = sync_aneel_consumidores(db)
                db.commit()
            return result

        run("aneel_consumidores", _aneel)

    if "ibram" in steps:
        from jobs.prospeccao import config as _config
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.ibram_ingest import sync_ibram_geradores

        def _ibram():
            url = getattr(_config, "IBRAM_GERADORES_URL", "").strip() or None
            with session_scope() as db:
                result = sync_ibram_geradores(db, url=url)
                db.commit()
            return result

        run("ibram_geradores", _ibram)

    if "ibama_ctf" in steps:
        from jobs.prospeccao import config as _config
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.ibama_ctf_ingest import sync_ibama_ctf

        def _ibama_ctf():
            ufs = {
                u.strip().upper()
                for u in _config.IBAMA_CTF_DEFAULT_UFS.split(",")
                if u.strip()
            }
            with session_scope() as db:
                result = sync_ibama_ctf(db, ufs=ufs or {"DF", "GO"})
                db.commit()
            step_errs = result.get("erros") or []
            if step_errs and not result.get("ufs_processadas"):
                raise RuntimeError("IBAMA CTF/APP: " + "; ".join(step_errs))
            return result

        run("ibama_ctf", _ibama_ctf)
        _ibama_out = report.get("ok", {}).get("ibama_ctf")
        if isinstance(_ibama_out, dict) and _ibama_out.get("erros"):
            report["errors"]["ibama_ctf"] = {
                "error": "; ".join(_ibama_out["erros"]),
                "partial": True,
                "stats": {k: v for k, v in _ibama_out.items() if k != "erros"},
            }

    if "brasilapi_enrich" in steps:
        from jobs.prospeccao import config as _config
        from jobs.prospeccao.brasilapi_enrich import enrich_via_brasilapi
        from jobs.prospeccao.db import session_scope

        def _brasilapi():
            with session_scope() as db:
                result = enrich_via_brasilapi(
                    db,
                    batch_size=_config.BRASILAPI_BATCH_SIZE,
                    sleep_s=_config.BRASILAPI_SLEEP_S,
                )
                db.commit()
            return result

        run("brasilapi_enrich", _brasilapi)

    report["finished_at"] = datetime.now(UTC).isoformat()
    logger.info(
        "Harvest complete: ok=%s errors=%s report=%s",
        len(report["ok"]),
        len(report["errors"]),
        "last_harvest.json",
    )
    pathutil.write_report("last_harvest", report)
    return report
