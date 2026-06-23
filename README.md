# Dashboard-TRONIK

Dashboard para controle e monitoramento da reciclagem inteligente de resíduos eletrônicos, desenvolvido para a **TRONIK RECICLA**. O sistema integra monitoramento operacional de coletores, CRM comercial, APIs REST e um pipeline de prospecção de leads (REE) no Distrito Federal com *Learning to Rank* sobre ~534 mil candidatos enriquecidos a partir de oito fontes públicas.

Documentação detalhada do dashboard: [`docs/DOCUMENTAÇÃO_COMPLETA.md`](docs/DOCUMENTAÇÃO_COMPLETA.md) · Pipeline de prospecção: [`jobs/prospeccao/README.md`](jobs/prospeccao/README.md)

## Visão geral

| Módulo | Descrição |
|--------|-----------|
| **Dashboard web** | Monitoramento de coletores, coletas, rotas, relatórios e notificações |
| **API REST** | Endpoints Flask para coletores, CRM, comercial, prospecção e integrações |
| **Nik (assistente)** | Agente conversacional integrado ao dashboard |
| **Prospecção REE** | Ingestão de dados abertos, engenharia de features e ranking com XGBRanker |

## Contexto do problema

A Tronik Recicla opera coleta de resíduos eletrônicos no Distrito Federal (DF). O crescimento comercial exige prospecção escalável: identificar empresas com maior probabilidade de gerar REE e priorizar abordagens por valor relativo. Processos manuais de CRM não escalam. O pipeline de prospecção automatiza descoberta e ranking via aprendizado de máquina sobre bases governamentais abertas.

## Arquitetura da prospecção

1. **Harvest** — Ingestão de dados públicos (dump CNPJ da Receita Federal, IBAMA CTF, IBGE CNEFE, ANEEL SAMP, INEP Censo Escolar, PNCP, OpenStreetMap)
2. **Receita Parse** — Parse de 50M+ estabelecimentos do cadastro CNPJ; extração de CNPJ, razão social e CNAE principal
3. **RFB Enrich** — Complemento com CNAEs secundários, endereço completo, CEP e situação cadastral (Estabelecimentos RFB)
4. **Normalize** — Deduplicação, geocodificação via IBGE CNEFE (índice de 106M endereços), atribuição de RA (Região Administrativa) e geração de QIDs para agrupamento listwise
5. **Build Features** — Vetores de 20 dimensões para ~534k candidatos (fit de CNAE, qualidade de geocode, porte, proximidade espacial via BallTree, riqueza de contato, proxies institucionais)
6. **Train Ranker** — XGBRanker com objetivo listwise (`rank:ndcg`), restrições monotônicas, split temporal treino/val e *quality gates* pré-treino
7. **Score Candidates** — Inferência, percentil por grupo geográfico (QID) e publicação de scores na API/CRM

## Por que Learning to Rank

O ranking de leads difere de classificação: o limiar absoluto de qualidade é desconhecido e o valor comercial é relativo dentro de mercados geográficos locais. O ranking listwise (*Learning to Rank*) trata ambos os aspectos:

- **Ranking relativo por mercado:** o XGBRanker com NDCG@20 ranqueia empresas em relação aos pares na mesma RA, não globalmente.
- **Generalização entre grupos:** split temporal (holdout dos QIDs mais recentes) evita vazamento e mede robustez a distribuições geográficas/temporais novas.
- **Restrições monotônicas:** *guardrails* em features (situação ativa, geocode confirmado, completude de dados) injetam conhecimento de domínio sem limiares rígidos.
- **Escala:** LTR baseado em árvores lida com interações não lineares; early stopping e busca de hiperparâmetros reduzem overfitting em ~534k candidatos em ~100 grupos QID.

## Fontes de dados

| Fonte | Dados extraídos | Uso no pipeline |
|-------|-----------------|-----------------|
| Receita Federal (dump CNPJ) | ~50M estabelecimentos: CNPJ, razão social, CNAE | Pool principal de candidatos; situação cadastral |
| RFB Estabelecimentos | CNAEs secundários, endereço, CEP, data de abertura | Enriquecimento: fit de CNAE, idade, completude |
| IBGE CNEFE | 106M endereços geocodificados; hierarquia região/setor | Geocodificação (lat/lng, atribuição de RA) |
| IBAMA CTF | Licenças de coleta de REE | Proxy: sinal `public_proxy_fit` |
| ANEEL SAMP | Medidores e perfis de consumo | Proximidade logística: densidade de vizinhos (BallTree) |
| INEP Censo Escolar | Escolas por município | Proxy territorial: `inep_institution_proxy` |
| CNES | Estabelecimentos de saúde | Proxy territorial: `cnes_health_proxy` |
| OpenStreetMap (Geofabrik) | Densidade de POIs (eletrônicos/reparo) | Espacial: `osm_poi_ree_density` |

## Decisões técnicas

- **LTR listwise com QID geo-first:** empresas ranqueadas dentro da RA, respeitando heterogeneidade do DF (setor tech de Brasília vs. Entorno).
- **Restrições monotônicas no XGBoost:** `FEATURE_NAMES[i]` mapeia para `MONOTONIC_CONSTRAINTS[i]` (1 = monotonicamente crescente).
- **Split temporal treino/val:** holdout dos 20% QIDs mais recentes por snapshot; mede generalização temporal.
- **Quality gate pré-treino:** aborta se (a) &lt;8 QIDs com tamanho ≥ 2, ou (b) maior QID &gt;50% do treino. Pós-treino: bloqueia ativação se NDCG val &lt; 0,30 ou abaixo do modelo ativo.
- **BallTree com métrica haversine:** vizinho mais próximo em O(log N) para features OSM/ANEEL (~100 ms em 534k candidatos).
- **Engine singleton + pool_pre_ping:** pools reutilizados entre jobs; SQLite WAL (dev), PostgreSQL com `pool_pre_ping` (prod, ex.: Railway).
- **Escrita atômica de parquet (.tmp + rename):** evita leituras parciais em crash.
- **Cadeia de fallback de geocodificação:** CNEFE → centróide da RA; flag `has_geocode` sinaliza confiança ao ranker.

## Stack

- **Core:** Python 3.11+, SQLAlchemy 2.0+, SQLite (dev) / PostgreSQL (prod)
- **ML:** XGBoost (XGBRanker, `rank:ndcg`), scikit-learn (NDCG, BallTree), pandas, joblib
- **Web:** Flask, Flask-Login, APScheduler, Leaflet (frontend)
- **Dados:** Parquet, pandas, numpy
- **Ingestão:** CKAN, Geoportal IBGE, downloads HTTP (Geofabrik, Receita Federal)
- **Modelos ORM:** `EmpresaCandidata`, `FeatureSnapshotProspeccao`, `ModeloProspeccao`, `LocalCandidato` (ver `banco_dados/modelos.py`)

## Executando o pipeline de prospecção

### Pipeline completo (ponta a ponta)

```powershell
# Ativar ambiente Python
.\.venv\Scripts\Activate.ps1

# harvest → normalize → build-features → train-ranker → score-candidates
python -m jobs.prospeccao cli run-pipeline `
  --pipeline-version "prospeccao-ree-v3.4" `
  --model-version "v3.4-$(Get-Date -Format yyyyMMddHHmmss)" `
  --log-level DEBUG

# Conferir resultados
python -m jobs.prospeccao cli monitor-ranker --show-top 20
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m jobs.prospeccao cli run-pipeline \
  --pipeline-version "prospeccao-ree-v3.4" \
  --model-version "v3.4-$(date +%Y%m%d%H%M%S)" \
  --log-level DEBUG
```

### Etapas individuais

```bash
python -m jobs.prospeccao harvest
python -m jobs.prospeccao normalize-candidates
python -m jobs.prospeccao build-features --version "prospeccao-ree-v3.4"
python -m jobs.prospeccao train-xgboost --allow-baseline
python -m jobs.prospeccao score-candidates --publish-crm
```

### Configuração

Variáveis de ambiente (`.env` ou Railway):

```
DATABASE_URL=postgresql://user:pass@host/dbname
TRONIK_SEDE_LAT=-15.7942
TRONIK_SEDE_LNG=-47.8822
LOG_LEVEL=INFO
```

## Estrutura do projeto

```
Dashboard-TRONIK/
├── app.py                              # Aplicação Flask
├── jobs/prospeccao/                    # Pipeline ML / prospecção
│   ├── cli.py
│   ├── ranker_contract.py              # Schema de features e restrições monotônicas
│   ├── build_features.py
│   ├── train_xgboost.py
│   ├── score_candidates.py
│   └── *_ingest.py                     # Ingestão por fonte
├── banco_dados/                        # ORM e serviços de negócio
│   ├── modelos.py
│   └── services/
├── rotas/api/                          # Endpoints REST
├── nik_bot/                            # Assistente Nik
├── templates/ / estatico/              # Frontend
├── tests/                              # Pytest (120+ testes)
├── docs/                               # Documentação estendida
├── data/ml/prospeccao/                 # Snapshots (.parquet) e modelos (.joblib)
└── requirements.txt
```

## Desenvolvimento

### Setup

```bash
git clone https://github.com/natanheringer/Dashboard-TRONIK.git
cd Dashboard-TRONIK
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py               # Servidor Flask em desenvolvimento
```

### Estilo e testes

- Python: PEP 8, type hints onde aplicável
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat`, `fix`, `refactor`, …)

```bash
pytest tests/ -v --cov=jobs --cov=banco_dados
```

## Monitoramento e operações

```powershell
python -m jobs.prospeccao cli monitor-ranker --show-top 50
```

Exibe versão do modelo ativo, métricas NDCG, importância de features e desempenho no holdout de validação.

Snapshots de features são versionados e imutáveis (`FeatureSnapshotProspeccao` por `pipeline_version` e `qid`). Jobs em lote registram logs estruturados em stdout e `logs/prospeccao.log`.

## Referências

- **Schema de features:** `jobs/prospeccao/ranker_contract.py` (`FEATURE_NAMES`, `MONOTONIC_CONSTRAINTS`)
- **Pesos CNAE:** `REE_CNAE_PREFIX_WEIGHTS` em `ranker_contract.py`
- **Agrupamento QID:** cadeia RA → bairro → CEP5 → CNAE4 → zone em `build_features.py`
- **Busca de hiperparâmetros:** `_ranker_param_candidates()` em `train_xgboost.py`

## Licença

[GPL-2.0](LICENSE)

---

**Autor e mantenedor:** [Natan Heringer](https://github.com/natanheringer) (@natanheringer)

**Mantenedores:** [Yves Jorge](https://github.com/yveshjorge) · [Rafael Caputo](https://github.com/rafaelcaputo2324) · [Thales Leão](https://github.com/tleaoribeironeves-max) · [Gabriel Oliveira de Araújo](https://github.com/gabrieloliveiraetb) · [Mateus de Jesus Carvalho do Nascimento](https://github.com/mateusjcn) · [Pedro Gabryel Oliveira](https://github.com/ySpecks) · [Ruan Costa](https://github.com/Ruan25-coder)

Lista completa: [`docs/CONTRIBUTORS.md`](docs/CONTRIBUTORS.md)

**Última atualização:** junho de 2026  
**Repositório:** https://github.com/natanheringer/Dashboard-TRONIK
