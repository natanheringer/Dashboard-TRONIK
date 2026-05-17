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

    s_links = sub.add_parser("ckan-link-quality", help="Valida URLs de recursos CKAN com HEAD/GET")
    s_links.add_argument("--max-packages", type=int, default=100)
    s_links.add_argument("--max-links", type=int, default=300)
    s_links.add_argument("--org", type=str, default=None)

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
    s_ra.add_argument("--tipo", choices=("estabelecimentos", "empresas", "lookups"), default="estabelecimentos")
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
        default="ibge,geoportal,ckan_meta,ckan_links,pncp,ckan_orgs",
        help="Separados por vírgula: ibge,geoportal,ckan_meta,ckan_links,ckan_show,pncp,ckan_orgs,receita_probe,inep_probe,aneel,ibram,ibama_ctf",
    )
    s_h.add_argument("--dry-run", action="store_true")
    s_h.add_argument("--ckan-max", type=int, default=250)
    s_h.add_argument("--ckan-link-max", type=int, default=300)
    s_h.add_argument("--pncp-dias", type=int, default=14)
    s_h.add_argument("--pncp-max-pages", type=int, default=80)

    s_build = sub.add_parser("build-features", help="Monta feature_snapshot_prospeccao")
    s_build.add_argument("--version", type=str, default="prospeccao-ree-v3.3")
    s_build.add_argument("--seed-demo", action="store_true", help="Insere candidatos demo para smoke test")
    s_build.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Processa só as N primeiras empresas (ordem por id). Útil para teste; qid_stats fica só sobre esse recorte.",
    )
    s_build.add_argument(
        "--use-internal-labels",
        action="store_true",
        help="Labels a partir do DB operacional (parceiro/coleta/contrato); fallback heurístico sem match",
    )

    s_train = sub.add_parser("train-ranker", help="Treina XGBRanker ou baseline heuristico")
    s_train.add_argument("--pipeline-version", type=str, default="prospeccao-ree-v3.3")
    s_train.add_argument("--model-version", type=str, default=None)
    s_train.add_argument("--no-baseline", action="store_true")

    s_score = sub.add_parser("score-candidates", help="Pontua snapshots com modelo ativo")
    s_score.add_argument("--model-version", type=str, default=None)
    s_score.add_argument("--pipeline-version", type=str, default=None)

    s_pub = sub.add_parser("published-scores", help="Lista ranking publicado para dashboard/Nik")
    s_pub.add_argument("--limit", type=int, default=20)
    s_pub.add_argument("--qid", type=str, default=None)
    s_pub.add_argument("--prioridade", type=str, default=None)
    s_pub.add_argument("--model-version", type=str, default=None)

    sub.add_parser("monitor", help="Relatório JSON de saúde do ranker (cron/ops)")

    sub.add_parser(
        "enrichment-probe",
        help="Verifica TRONIK_OSM_POI_PARQUET / INEP / CNES staging para proxies do ranker",
    )

    s_pipe = sub.add_parser("ranker-pipeline", help="build-features + train-ranker + score-candidates")
    s_pipe.add_argument("--version", type=str, default="prospeccao-ree-v3.3")
    s_pipe.add_argument("--seed-demo", action="store_true")
    s_pipe.add_argument(
        "--build-limit",
        type=int,
        default=None,
        metavar="N",
        help="Repasse para build-features --limit (smoke / recorte).",
    )
    s_pipe.add_argument(
        "--use-internal-labels",
        action="store_true",
        help="Repasse para build-features --use-internal-labels",
    )

    s_rp = sub.add_parser("receita-parse", help="Parseia ZIPs Receita baixados -> empresa_candidata + local_candidato")
    s_rp.add_argument("--no-two-pass", action="store_true", help="Carrega TODOS Empresas*.zip na memória (rápido, ~12 GB RAM)")

    s_cnefe = sub.add_parser("cnefe", help="Baixa + parseia CNEFE 2022 coordenadas (DF + GO)")
    s_cnefe.add_argument("--no-download", action="store_true", help="Pula download, só parseia ZIPs existentes")

    s_norm = sub.add_parser("normalize", help="Dedup + geocode CNEFE + RA + qid")
    s_norm.add_argument("--skip-geocode", action="store_true", help="Pula geocodificação CNEFE")
    s_norm.add_argument("--skip-ra", action="store_true", help="Pula atribuição de RA")

    s_aneel = sub.add_parser("aneel", help="Baixa e cruza dados ANEEL de consumidores livres (proxy porte operacional)")
    s_aneel.add_argument("--url", type=str, default=None, help="URL direta do CSV/ZIP ANEEL")
    s_aneel.add_argument("--ufs", type=str, default="DF,GO", help="UFs a filtrar separadas por vírgula (default DF,GO)")

    s_ibram = sub.add_parser("ibram", help="Importa cadastro IBRAM de geradores de resíduos perigosos (e-waste)")
    s_ibram.add_argument("--file", type=str, default=None, help="Caminho para CSV exportado do portal IBRAM")
    s_ibram.add_argument("--url", type=str, default=None, help="URL direta de recurso CSV/XLS do IBRAM")

    s_ibama_ctf = sub.add_parser("ibama-ctf", help="CTF/APP IBAMA: pessoas jurídicas por estado — leads eletroeletrônicos")
    s_ibama_ctf.add_argument("--ufs", type=str, default=None, help="Estados separados por vírgula (default TRONIK_IBAMA_CTF_UFS ou DF,GO)")
    s_ibama_ctf.add_argument("--no-destinadores", action="store_true", help="Não marca destinadores/recicladores")
    s_ibama_ctf.add_argument("--no-download", action="store_true", help="Pula download, usa CSVs em data/raw/.../ibama_ctf")

    sub.add_parser(
        "link-crm",
        help="Associa empresa_candidata.pipeline_id a deals CRM ganhos (nome = coletor.localizacao)",
    )

    s_ba = sub.add_parser("brasilapi-enrich", help="Enriquece email/telefone/CNAE via Brasil API (free, sem auth)")
    s_ba.add_argument("--batch", type=int, default=500, help="Max CNPJs por execução (default 500)")
    s_ba.add_argument("--sleep", type=float, default=None, help="Pausa entre requests em segundos (default 0.4)")
    s_ba.add_argument("--all", dest="all_records", action="store_true", help="Consulta todos, não só os sem contato")

    s_cdd = sub.add_parser("fetch-targeted", help="Busca DF+Entorno via Casa dos Dados API (sem download pesado)")
    s_cdd.add_argument(
        "--tiers", type=str, default="all",
        help="Tiers de proximidade: all, df, t1, t1,t2, t1,t2,t3, t1,t2,t3,t4",
    )
    s_cdd.add_argument("--max-pages", type=int, default=None, help="Max pages per query (default 200)")

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

    if args.cmd == "ckan-link-quality":
        from jobs.prospeccao.ckan_ingest import validate_ckan_resource_links

        result = validate_ckan_resource_links(
            max_packages=args.max_packages,
            max_links=args.max_links,
            fq_org=args.org,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result.get("failed", 0) == 0 else 1

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
        from jobs.prospeccao.ibge_ingest import sync_df_municipios, sync_estados, sync_ride_entorno

        sync_df_municipios()
        sync_ride_entorno()
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
            ckan_link_max=args.ckan_link_max,
            pncp_dias=args.pncp_dias,
            pncp_max_pages=args.pncp_max_pages,
        )
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        return 0 if not rep.get("errors") else 1

    if args.cmd == "aneel":
        from jobs.prospeccao.aneel_ingest import sync_aneel_consumidores
        from jobs.prospeccao.db import session_scope

        ufs = {u.strip().upper() for u in args.ufs.split(",") if u.strip()}
        with session_scope() as db:
            result = sync_aneel_consumidores(db, url=args.url, ufs=ufs)
            db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "ibram":
        from pathlib import Path as _Path

        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.ibram_ingest import sync_ibram_geradores

        csv_path = _Path(args.file) if args.file else None
        with session_scope() as db:
            result = sync_ibram_geradores(db, csv_path=csv_path, url=args.url)
            db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "ibama-ctf":
        from jobs.prospeccao import config as _config
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.ibama_ctf_ingest import sync_ibama_ctf

        ufs_raw = (args.ufs or _config.IBAMA_CTF_DEFAULT_UFS).strip()
        ufs = {u.strip().upper() for u in ufs_raw.split(",") if u.strip()}
        with session_scope() as db:
            result = sync_ibama_ctf(
                db,
                ufs=ufs,
                include_destinadores=not args.no_destinadores,
                download=not args.no_download,
            )
            db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "link-crm":
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.link_crm_pipeline import sync_pipeline_links

        with session_scope() as db:
            result = sync_pipeline_links(db)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "brasilapi-enrich":
        from jobs.prospeccao.brasilapi_enrich import enrich_via_brasilapi
        from jobs.prospeccao.db import session_scope

        with session_scope() as db:
            result = enrich_via_brasilapi(
                db,
                batch_size=args.batch,
                sleep_s=args.sleep,
                only_missing_contact=not args.all_records,
            )
            db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "fetch-targeted":
        from jobs.prospeccao.casadosdados_fetch import fetch_targeted
        from jobs.prospeccao.db import session_scope

        with session_scope() as db:
            result = fetch_targeted(db, tiers=args.tiers, max_pages_per_query=args.max_pages)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "receita-parse":
        from jobs.prospeccao import paths as pathutil
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.receita_parse import parse_estabelecimentos_to_db
        dirs = pathutil.ensure_raw_layout()
        with session_scope() as db:
            result = parse_estabelecimentos_to_db(db, dirs["receita"], two_pass=not args.no_two_pass)
            db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "cnefe":
        from jobs.prospeccao.cnefe_ingest import sync_cnefe

        result = sync_cnefe(download=not args.no_download)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "normalize":
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.normalize_candidates import normalize_all

        with session_scope() as db:
            result = normalize_all(db, skip_geocode=args.skip_geocode, skip_ra=args.skip_ra)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "build-features":
        from jobs.prospeccao.build_features import build_feature_snapshots
        from jobs.prospeccao.db import session_scope

        with session_scope() as db:
            result = build_feature_snapshots(
                db,
                pipeline_version=args.version,
                seed_demo=args.seed_demo,
                limit=args.limit,
                use_internal_labels=args.use_internal_labels,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "train-ranker":
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.train_xgboost import train_ranker

        with session_scope() as db:
            result = train_ranker(
                db,
                pipeline_version=args.pipeline_version,
                model_version=args.model_version,
                allow_baseline=not args.no_baseline,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "score-candidates":
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.score_candidates import score_candidates

        with session_scope() as db:
            result = score_candidates(
                db,
                model_version=args.model_version,
                pipeline_version=args.pipeline_version,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "published-scores":
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.publish_scores import list_published_scores

        with session_scope() as db:
            result = list_published_scores(
                db,
                limite=args.limit,
                qid=args.qid,
                prioridade=args.prioridade,
                model_version=args.model_version,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "monitor":
        from jobs.prospeccao.monitor_ranker import run_monitor

        return run_monitor()

    if args.cmd == "enrichment-probe":
        from jobs.prospeccao.enrichment_proxies import probe_enrichment_files

        print(json.dumps(probe_enrichment_files(), ensure_ascii=False, indent=2, default=str))
        return 0

    if args.cmd == "ranker-pipeline":
        from jobs.prospeccao.build_features import build_feature_snapshots
        from jobs.prospeccao.db import session_scope
        from jobs.prospeccao.score_candidates import score_candidates
        from jobs.prospeccao.train_xgboost import train_ranker

        with session_scope() as db:
            built = build_feature_snapshots(
                db,
                pipeline_version=args.version,
                seed_demo=args.seed_demo,
                limit=args.build_limit,
                use_internal_labels=args.use_internal_labels,
            )
            trained = train_ranker(db, pipeline_version=args.version)
            scored = score_candidates(db, model_version=trained["versao"], pipeline_version=args.version)
        print(json.dumps({"built": built, "trained": trained, "scored": scored}, ensure_ascii=False, indent=2, default=str))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
