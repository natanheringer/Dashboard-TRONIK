# Ingestão pública — `jobs/prospeccao` (v0.2)

**Arquitetura do sistema (diagramas):** [docs/ARQUITETURA.md](../docs/ARQUITETURA.md)

Cliente **robusto** para fontes oficiais do plano de prospecção (DF / Brasil): **retries** (urllib3), **pausa entre pedidos CKAN**, **downloads com retomada** (`Range` + `Accept-Ranges`), **manifestos** em `data/raw/prospeccao/_manifest/` e **relatório** `data/raw/prospeccao/_reports/last_harvest.json`.

> Não é “scraper” genérico de HTML: prioriza **API CKAN**, **ArcGIS REST**, **API IBGE**, **API PNCP consultas**, **HTTP direto** (Receita, Geofabrik, INEP, CNES). Respeite termos de uso, carga dos servidores e LGPD.

## Execução

Na **raiz** do repositório:

```bash
python -m jobs.prospeccao --help
python -m jobs.prospeccao harvest --dry-run
python -m jobs.prospeccao harvest --steps ibge,geoportal,ckan_meta,pncp
```

### Comandos principais

| Comando | Descrição |
|---------|-----------|
| `catalog-only` / `ckan-metadata` | `package_search` → JSONL (metadados CKAN DF) |
| `ckan-orgs-list` | `organization_list` (slugs) |
| `ckan-package-show` | `package_show` em lote (metadados completos + recursos) |
| `ckan-org <slug>` | Download paginado de recursos (CSV/ZIP/JSON…) até `--max-mb` |
| `ckan-default-orgs` | Várias orgs (`TRONIK_CKAN_DEFAULT_ORGS`) com limites conservadores |
| `ibge-df` | Municípios UF 53 + `estados.json` |
| `geoportal-ra` | RA em GeoJSON (`TRONIK_GEOPORTAL_RA_FEATURE_URL`, default IBRAM 2025) |
| `pncp-contratacoes` | API **consulta** `GET …/contratacoes/publicacao` (exige `tamanhoPagina`; período curto pode devolver 400 — usar ≥ ~14 dias) |
| `receita` | ZIPs via `TRONIK_RECEITA_CNPJ_ZIP_URLS` |
| `receita-auto` | Procura base em `TRONIK_RECEITA_CNPJ_BASE_URLS` e descarrega `Empresas*.zip` ou `Estabelecimentos*.zip` |
| `geofabrik` | PBF regional (use `--max-mb` para teste) |
| `inep` / `inep-microdados` / `inep-probe` | CSV env ou ZIP microdados (`TRONIK_INEP_MICRODADOS_BASE`) |
| `cnes` | ZIP via `TRONIK_CNES_BASE_ZIP_URL` |
| `harvest` | Orquestra passos e grava relatório JSON |

## Variáveis de ambiente (resumo)

| Variável | Default / notas |
|----------|-----------------|
| `TRONIK_PROSPECCAO_RAW_DIR` | `data/raw/prospeccao` |
| `TRONIK_CKAN_DF_URL` | `https://dados.df.gov.br` |
| `TRONIK_CKAN_ROWS` | `100` (máx. por `package_search`) |
| `TRONIK_CKAN_PAGE_SLEEP_S` | `0.35` — pausa entre chamadas CKAN |
| `TRONIK_HTTP_MAX_RETRIES` | `5` |
| `TRONIK_HTTP_BACKOFF_FACTOR` | `0.6` |
| `TRONIK_HTTP_TIMEOUT` | `180` s |
| `TRONIK_HTTP_USER_AGENT` | Identifique o projeto (boa prática) |
| `TRONIK_RECEITA_CNPJ_BASE_URLS` | Bases candidatas separadas por vírgula |
| `TRONIK_RECEITA_CNPJ_ZIP_URLS` | URLs completas separadas por vírgula |
| `TRONIK_GEOFABRIK_PBF_URL` | Default centro-oeste Geofabrik |
| `TRONIK_INEP_MICRODADOS_BASE` | `…microdados_censo_escolar_{year}.zip` |
| `TRONIK_CNES_BASE_ZIP_URL` | Link mensal DATASUS (portal CNES) |
| `TRONIK_PNCP_CONSULTA_BASE` | `https://pncp.gov.br/api/consulta/v1` |
| `TRONIK_GEOPORTAL_RA_FEATURE_URL` | Default IBRAM RA 2025 FeatureServer |
| `TRONIK_GEOPORTAL_TIMEOUT_S` | `90` |
| `TRONIK_CKAN_DEFAULT_ORGS` | Lista de slugs para `ckan-default-orgs` / `harvest` |

## Fontes cobertas por código

1. **CKAN DF** — metadados, `package_show`, downloads por organização.  
2. **IBGE API v1** — municípios / estados.  
3. **ArcGIS REST** — polígonos RA (URL configurável).  
4. **PNCP consultas** — contratações publicadas (JSONL).  
5. **Receita** — URLs explícitas ou deteção de base + ZIPs típicos.  
6. **Geofabrik** — PBF OSM regional.  
7. **INEP** — ZIP microdados (ano configurável) ou CSV por URL.  
8. **CNES** — ZIP por URL (competência definida no portal DATASUS).

## Ainda por URL manual / próximo passo

- **CNEFE**, **IPEDF/PDAD**, **camadas IDE-DF adicionais**, **DETRAN/DER** — adicionar módulos semelhantes ao `geoportal_ingest` quando tiveres `FeatureServer` ou CSV estável.  
- **Normalização** (`normalize_entities.py`) e **staging** — consumir estes ficheiros.

## Notas técnicas

- **PNCP:** a resposta inclui `totalPaginas`; o sync pára ao atingir a última página ou `max_pages`. Períodos muito curtos podem devolver **HTTP 400**; aumentar `--dias` (ex.: 14–30).  
- **Receita:** ficheiros são **grandes**; use `receita-auto --max 1` para validar base antes de baixar tudo.  
- **INEP microdados:** ZIP completo pode ter **vários GB**; use `--max-mb` só para teste de conectividade.  
- **Git:** `data/raw/prospeccao/**/*` está no `.gitignore` (exceto `.gitkeep`).
