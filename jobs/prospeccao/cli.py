"""CLI: python -m jobs.prospeccao (executar na raiz do repositorio)."""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(
        description="Ingestao robusta de dados publicos (DF / Brasil): APIs oficiais e downloads.",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUG nos loggers")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_ckan = sub.add_parser("ckan-metadata", help="package_search para JSONL resumido")
    s_ckan.add_argument("--max", type=int, default=500)
    s_ckan.add_argument("--org", type=str, default=None)

    sub.add_parser("ckan-orgs-list", help="Lista slugs organization_list")

    s_show = sub.add_parser("ckan-package-show", help="Metadados completos package_show (mais pedidos à API)")
    s_show.add_argument("--max", type=int, default=60)
    s_show.add_argument("--org", type=str, default=None)

    s_ckan_dl = sub.add_parser("ckan-org", help="Baixa recursos de uma organização (paginado)")
    s_ckan_dl.add_argument("org", type=str)
    s_ckan_dl.add_argument("--max-packages", type=int, default=30)
    s_ckan_dl.add_argument("--max-mb", type=int, default=50)

    sub.add_parser("ckan-default-orgs", help="Várias orgs (TRONIK_CKAN_DEFAULT_ORGS) com limites conservadores")

    s_all = sub.add_parser("catalog-only", help="Metadados CKAN (leve), alias histórico")
    s_all.add_argument("--max", type=int, default=400)

    sub.add_parser("ibge-df", help="Municípios UF 53 + estados (JSON)")

    s_geo = sub.add_parser("geoportal-ra", help="RA em GeoJSON (ArcGIS REST)")
    s_geo.add_argument("--max-features", type=int, default=5000)
    s_geo.add_argument("--url", type=str, default=None)

    s_pncp = sub.add_parser("pncp-contratacoes", help="API consulta: contratações publicadas (DF)")
    s_pncp.add_argument("--dias", type=int, default=7)
    s_pncp.add_argument("--max-pages", type=int, default=40)

    sub.add_parser("receita", help="ZIPs via TRONIK_RECEITA_CNPJ_ZIP_URLS")

    s_ra = sub.add_parser("receita-auto", help="Deteta base Receita e descarrega N ZIPs")
    s_ra.add_argument("--tipo", choices=("estabelecimentos", "empresas"), default="estabelecimentos")
    s_ra.add_argument("--max", type=int, default=2)
    s_ra.add_argument("--probe-only", action="store_true")

    s_gf = sub.add_parser("geofabrik", help="PBF regional Geofabrik")
    s_gf.add_argument("--max-mb", type=int, default=None)
    s_gf.add_argument("--url", type=str, default=None)

    sub.add_parser("inep", help="CSV via TRONIK_INEP_CENSO_ESCOLAR_CSV_URL")

    s_inep_z = sub.add_parser("inep-microdados", help="ZIP microdados INEP")
    s_inep_z.add_argument("--year", type=str, default=None)
    s_inep_z.add_argument("--max-mb", type=int, default=None)

    sub.add_parser("inep-probe", help="HEAD para descobrir ano ZIP disponível")

    sub.add_parser("cnes", help="ZIP CNES via TRONIK_CNES_BASE_ZIP_URL")

    s_h = sub.add_parser("harvest", help="Corre vários passos e grava _reports/last_harvest.json")
    s_h.add_argument(
        "--steps",
        type=str,
        default="ibge,geoportal,ckan_meta,pncp,ckan_orgs",
        help="Separados por vírgula: ibge,geoportal,ckan_meta,ckan_show,pncp,ckan_orgs,receita_probe,inep_probe",
    )
    s_h.add_argument("--dry-run", action="store_true")
    s_h.add_argument("--ckan-max", type=int, default=250)
    s_h.add_argument("--pncp-dias", type=int, default=14)
    s_h.add_argument("--pncp-max-pages", type=int, default=80)

    args = p.parse_args(argv)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.cmd == "ckan-metadata":
        from jobs.prospeccao.ckan_ingest import sync_catalog_metadata

        sync_catalog_metadata(max_packages=args.max, fq_org=args.org)
        return 0

    if args.cmd == "ckan-orgs-list":
        from jobs.prospeccao.ckan_ingest import organization_slugs

        slugs = organization_slugs()
        print(json.dumps(slugs, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "ckan-package-show":
        from jobs.prospeccao.ckan_ingest import sync_package_show_details

        sync_package_show_details(max_packages=args.max, fq_org=args.org)
        return 0

    if args.cmd == "ckan-org":
        from jobs.prospeccao.ckan_ingest import download_resources_for_org

        download_resources_for_org(
            args.org,
            max_packages=args.max_packages,
            max_resource_mb=args.max_mb,
            paginate=True,
        )
        return 0

    if args.cmd == "ckan-default-orgs":
        from jobs.prospeccao.ckan_ingest import sync_default_ckan_orgs

        sync_default_ckan_orgs()
        return 0

    if args.cmd == "catalog-only":
        from jobs.prospeccao.ckan_ingest import sync_catalog_metadata

        sync_catalog_metadata(max_packages=args.max, fq_org=None)
        return 0

    if args.cmd == "ibge-df":
        from jobs.prospeccao.ibge_ingest import sync_df_municipios, sync_estados

        sync_df_municipios()
        sync_estados()
        return 0

    if args.cmd == "geoportal-ra":
        from jobs.prospeccao.geoportal_ingest import sync_ra_geojson

        sync_ra_geojson(feature_url=args.url, max_features=args.max_features)
        return 0

    if args.cmd == "pncp-contratacoes":
        from jobs.prospeccao.pncp_ingest import sync_contratacoes_df_periodo

        sync_contratacoes_df_periodo(
            dias=args.dias,
            max_pages=args.max_pages,
        )
        return 0

    if args.cmd == "receita":
        from jobs.prospeccao.receita_ingest import download_receita_zips_from_env

        download_receita_zips_from_env()
        return 0

    if args.cmd == "receita-auto":
        from jobs.prospeccao.receita_ingest import download_receita_auto

        download_receita_auto(
            tipo=args.tipo,
            max_files=args.max,
            probe_only=args.probe_only,
        )
        return 0

    if args.cmd == "geofabrik":
        from jobs.prospeccao.geofabrik_ingest import download_pbf

        download_pbf(url=args.url, max_mb=args.max_mb)
        return 0

    if args.cmd == "inep":
        from jobs.prospeccao.inep_ingest import download_censo_escolar_csv

        download_censo_escolar_csv()
        return 0

    if args.cmd == "inep-microdados":
        from jobs.prospeccao.inep_ingest import download_censo_escolar_microdados_zip

        download_censo_escolar_microdados_zip(year=args.year, max_mb=args.max_mb)
        return 0

    if args.cmd == "inep-probe":
        from jobs.prospeccao.inep_ingest import probe_censo_escolar_years

        y = probe_censo_escolar_years()
        print(y or "nenhum")
        return 0

    if args.cmd == "cnes":
        from jobs.prospeccao.cnes_ingest import download_cnes_zip

        download_cnes_zip()
        return 0

    if args.cmd == "harvest":
        from jobs.prospeccao.harvest import run_harvest

        steps = [s.strip() for s in args.steps.split(",") if s.strip()]
        rep = run_harvest(
            steps,
            dry_run=args.dry_run,
            ckan_max=args.ckan_max,
            pncp_dias=args.pncp_dias,
            pncp_max_pages=args.pncp_max_pages,
        )
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        return 0 if not rep.get("errors") else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
