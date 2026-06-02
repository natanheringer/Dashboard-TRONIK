# dashboard-tronik

E-waste prospection system for the Federal District of Brazil. Identifies and ranks commercial leads (waste electronics generators) through Learning to Rank on 534k candidates enriched from eight public data sources.

## Problem Statement

Tronik Recicla operates e-waste collection in the Federal District (DF). Efficient growth requires scalable lead generation: identifying companies likely to generate electronics waste, prioritizing outreach by commercial value. Manual CRM processes do not scale. This system automates discovery and ranking via machine learning on open government datasets.

## Architecture

1. **Harvest** — Ingest public data (CNPJ dump from Receita Federal, IBAMA CTF, IBGE CNEFE, ANEEL SAMP, INEP Censo Escolar, PNCP, OpenStreetMap)
2. **Receita Parse** — Parse 50M+ establishments from Receita Federal CNPJ registry; extract CNPJ, legal name, primary CNAE
3. **RFB Enrich** — Supplement with secondary CNAEs, complete address, postal code, and registration status from RFB Estabelecimentos
4. **Normalize** — Deduplication, geocoding via IBGE CNEFE (106M address index), assignment of RA (Administrative Region), generation of Qualification IDs (QID) for listwise grouping
5. **Build Features** — Engineer 20-dimensional feature vectors for 534k candidates (CNAE fit, geocode quality, company size, spatial proximity via BallTree, contact richness, institutional proxies)
6. **Train Ranker** — Fit XGBRanker with listwise (rank:ndcg) objective on geographic QID groups, apply monotonic constraints, temporal train/val split, pre-training quality gates
7. **Score Candidates** — Apply trained ranker; compute percentile rank within each geographic group; publish scores to CRM API

## Why Learning to Rank

Lead ranking differs from classification: the absolute quality threshold is unknown, and commercial value is relative within local geographic markets. Listwise ranking (Learning to Rank) addresses both:

- **Relative ranking within markets:** XGBRanker trained with NDCG@20 objective ensures companies are ranked relative to peers in the same RA, not globally. A strong candidate in Brasília's tech sector may rank differently than a similar company in a remote area.
- **Cross-group generalization:** Temporal train/val split (holdout recent QID groups) prevents data leakage and measures model robustness to unseen geographic/temporal distributions.
- **Monotonic constraints:** Guardrails on feature contributions (e.g., active status, geocoding confirmation, data completeness always improve rank) inject domain knowledge without rigid thresholds.
- **Scalability:** Tree-based LTR handles non-linear interactions; early stopping and hyperparameter search avoid overfitting on 534k candidates across 100 QID groups.

## Data Sources

| Source | Data Extracted | Use in Pipeline |
|--------|-----------------|-----------------|
| Receita Federal (CNPJ dump) | ~50M establishments: CNPJ, razão social, CNAE | Primary candidate pool; company registration status |
| RFB Estabelecimentos | Secondary CNAEs, complete address, CEP, foundation date | Enrichment: CNAE fit scoring, age, data completeness |
| IBGE CNEFE | 106M geocoded addresses; region/sector/subsector hierarchy | Geocoding (latitude/longitude, RA assignment) |
| IBAMA CTF | Electronic waste collection permits, licensed companies | Proxy: public_proxy_fit signal (institutional alignment) |
| ANEEL SAMP | Electricity meter data; equipment consumption profiles | Logistics proximity: BallTree neighbor density |
| INEP Censo Escolar | Schools; institution density by municipality | Territorial proxy: inep_institution_proxy feature |
| CNES (Sistema de Saúde) | Health establishments; facility density | Territorial proxy: cnes_health_proxy feature |
| OpenStreetMap (Geofabrik) | POI density; amenities tagged electronics/repair | Spatial: osm_poi_ree_density feature |

## Key Technical Decisions

- **Listwise LTR with geo-first QID grouping:** Companies ranked within their Administrative Region (RA), not globally. Respects geographic heterogeneity of DF (Brasília's tech sector vs. Entorno suburbs behave differently). Prevents out-of-distribution overfitting.

- **Monotonic constraints on XGBoost:** FEATURE_NAMES[i] maps to MONOTONIC_CONSTRAINTS[i] (1 = monotonically increasing). Active status, has_geocode, and data_tier always contribute positively. Context-dependent features (age, neighborhood density) left unconstrained; tree decides.

- **Temporal train/val split:** Holdout most recent 20% of QID groups by snapshot ID (proxy for creation timestamp). Prevents data leakage; measures generalization to new candidates and time periods.

- **Quality gate pre-training:** Abort if (a) <8 QIDs with size >= 2 (insufficient listwise diversity), or (b) largest QID >50% of training set (risk of label collapse). Post-training: block activation if val NDCG < 0.30 or < active model NDCG.

- **BallTree with haversine metric:** O(log N) nearest-neighbor lookup for OSM POI density and ANEEL proximity features instead of O(N²) pairwise distance. 534k candidates, 100ms latency target.

- **Engine singleton + pool_pre_ping:** Reuse database connection pools across batch jobs. SQLite WAL mode (concurrent reads with writes), 60s timeout, PostgreSQL pool_pre_ping (skip stale connections after network blips). Railway.app production target.

- **Atomic parquet writes (.tmp + rename):** Feature snapshots written to .tmp, renamed on success. Prevents partial reads if process crashes mid-write; consistent views for training jobs.

- **Fallback geocoding chain:** If CNEFE match fails, fallback to RA centroid (lat/lng of region center). Ensures all 534k candidates have usable coordinates; has_geocode binary flag signals confidence level to ranker.

## Stack

- **Core:** Python 3.11+, SQLAlchemy 2.0+, SQLite (dev) / PostgreSQL (prod)
- **ML:** XGBoost (XGBRanker, rank:ndcg objective), scikit-learn (ndcg_score metric, BallTree), pandas, joblib (model serialization)
- **Data:** Parquet (feature snapshots), pandas DataFrames, numpy arrays
- **Scheduling:** APScheduler (cron job orchestration), PowerShell (Windows pipeline runner)
- **Ingest:** CKAN API, IBGE Geoportal, HTTP batch downloads (Geofabrik, Receita Federal)
- **Geocoding:** IBGE CNEFE library (internal), fallback to RA centroid
- **Database Models:** SQLAlchemy ORM (EmpresaCandidata, FeatureSnapshotProspeccao, ModeloProspeccao, LocalCandidato)

## Running the Pipeline

### Full Pipeline (end-to-end)

```powershell
# Activate Python environment
.\.venv\Scripts\Activate.ps1

# Run harvest -> normalize -> build-features -> train-ranker -> score-candidates
python -m jobs.prospeccao cli run-pipeline \
  --pipeline-version "prospeccao-ree-v3.4" \
  --model-version "v3.4-$(Get-Date -Format yyyyMMddHHmmss)" \
  --log-level DEBUG

# Check results
python -m jobs.prospeccao cli monitor-ranker --show-top 20
```

### Individual Steps

```powershell
# Ingest CNPJ dump, parse, enrich
python -m jobs.prospeccao harvest

# Normalize and geocode
python -m jobs.prospeccao normalize-candidates

# Build feature snapshots
python -m jobs.prospeccao build-features --version "prospeccao-ree-v3.4"

# Train XGBRanker (with hyperparameter search)
python -m jobs.prospeccao train-xgboost --allow-baseline

# Score all candidates and publish to CRM
python -m jobs.prospeccao score-candidates --publish-crm
```

### Configuration

Environment variables (`.env` or Railway):

```
DATABASE_URL=postgresql://user:pass@host/dbname  # PostgreSQL in prod
TRONIK_SEDE_LAT=-15.7942
TRONIK_SEDE_LNG=-47.8822
LOG_LEVEL=INFO
```

## Project Structure

```
dashboard-tronik/
├── jobs/prospeccao/                    # ML/prospection pipeline
│   ├── cli.py                          # Command-line interface
│   ├── config.py                       # Paths, constants
│   ├── db.py                           # Database session factory (singleton pool)
│   ├── ranker_contract.py              # Feature schema, CNAE weights, monotonic constraints
│   ├── build_features.py               # Feature engineering (20 dimensions)
│   ├── train_xgboost.py                # XGBRanker training, hyperparameter search
│   ├── score_candidates.py             # Inference, percentile ranking by QID
│   ├── enrichment_proxies.py           # Territorial proxies (INEP, CNES, OSM)
│   ├── normalize_candidates.py         # Dedup, geocoding, QID assignment
│   ├── *_ingest.py                     # Data source ingestion (Receita, IBAMA, IBGE, ANEEL, INEP, CNES, Geofabrik)
│   ├── paths.py                        # Filesystem paths (data/, models/)
│   └── __main__.py                     # Entry point
├── banco_dados/                        # Core database & API models
│   ├── modelos.py                      # SQLAlchemy ORM (57k lines)
│   ├── services/                       # Business logic layer
│   │   ├── account_service.py
│   │   ├── coleta_service.py
│   │   ├── comercial_service.py        # Commercial dashboard services
│   │   ├── crm_service.py
│   │   ├── contrato_service.py
│   │   └── ...
│   ├── utils/
│   │   ├── db_session.py               # SQLAlchemy session management
│   │   ├── constantes.py
│   │   └── ...
│   ├── geocodificacao.py
│   ├── notificacoes.py
│   └── serializers.py
├── rotas/api/                          # REST endpoints
│   ├── coletores.py
│   ├── coletas.py
│   ├── comercial.py
│   ├── crm.py
│   └── ...
├── tests/                              # Pytest (120+)
├── data/
│   ├── ml/prospeccao/                  # Feature snapshots (.parquet), trained models (.joblib)
│   └── ...
├── app.py                              # Flask application
├── requirements.txt
├── run_pipeline.ps1                    # PowerShell orchestration script
└── README.md
```

## Development

### Setup

```bash
git clone <repo>
cd dashboard-tronik
python -m venv .venv
source .venv/bin/activate  # Linux/Mac; Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py  # Flask dev server
```

### Code Style

- Python: PEP 8, type hints
- SQL: Standard SQLAlchemy ORM
- Commits: Conventional Commits (feat, fix, refactor, etc.)

### Testing

```bash
pytest tests/ -v --cov=jobs --cov=banco_dados
```

## Monitoring & Operations

### Ranker Health

```powershell
python -m jobs.prospeccao cli monitor-ranker --show-top 50
```

Outputs active model version, NDCG metrics, feature importance (gain, weight, cover), validation holdout performance.

### Feature Snapshot Inspection

All feature snapshots are versioned and immutable. Query `FeatureSnapshotProspeccao` by `pipeline_version` and `qid`.

### Pipeline Logs

Batch jobs emit structured logs (JSON) to stdout and `logs/prospeccao.log`. Each ingest, normalize, build-features, and train-ranker step is logged separately.

## References

- **Feature Schema:** `jobs/prospeccao/ranker_contract.py` (FEATURE_NAMES, MONOTONIC_CONSTRAINTS)
- **CNAE Scoring:** REE_CNAE_PREFIX_WEIGHTS in ranker_contract.py (primary + secondary CNAE fit)
- **Listwise Grouping:** QID fallback chain in `build_features.py` (RA → bairro → CEP5 → CNAE4 → zone)
- **Hyperparameter Search:** _ranker_param_candidates() in train_xgboost.py (8 XGBRanker configurations)

## License

GPL-2.0. See LICENSE file.

---

**Maintained by:** Natan Heringer  
**Last Updated:** May 2026  
**Repository:** https://github.com/TronikRecicla/dashboard-tronik
