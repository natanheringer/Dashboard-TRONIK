# TRONIK Recicla — Plano de Machine Learning

**Atualização:** maio/2026  
**Alinhamento:** edital Porto Digital / Residência em Software & IA + arquitetura operacional de prospecção (sem heatmap como produto central, sem etapa manual de validação como motor do modelo).

---

## Visão geral

A stack continua em Python, com jobs batch fora do ciclo de request do Flask. Este documento coloca no centro a **prospecção massiva no DF**: ingestão → normalização → geocodificação/enriquecimento → features tabulares → **XGBoost Learning to Rank** → **ranking na dashboard e na Nik** como fila operacional.

Os demais módulos (predição de enchimento, score de coletores, narrativa ESG) permanecem como frentes complementares ao produto e ao edital; a prioridade de produto descrita abaixo é **fila priorizada de candidatos**, não mapa de calor nem validação humana como fonte de *label*.

**Domínio operacional:** a Tronik atua em **resíduos de equipamentos eletroeletrônicos (REE / e-waste)** — coleta, pontos de descarte e logística associada. O ranking de prospecção deve medir **fit para esse fluxo** (CNAE, perfil de estabelecimento, proximidade a polos com descarte de REE, histórico interno de coleta de eletrônicos). Não é escopo posicionar a operação como gestora de papel, plástico de embalagem, metal de lata, óleo de cozinha ou orgânico; fontes públicas amplas (saúde, educação, SLU) entram como **proxies territoriais** ou contexto regulatório quando ajudam a estimar geração de REE ou obrigações correlatas, não como expansão de linha de resíduo.

**Código (subtração maio/2026):** removidos do repositório o modelo ORM `locais_prospeccao`, o serviço `banco_dados/services/ml_prospeccao.py`, a rota preview `/prospeccao`, a camada de prospects/heatmap no mapa e os endpoints `/api/ml/prospeccao*`, para não colidir com a implementação futura descrita neste plano. Instalações antigas podem ainda ter a tabela física `locais_prospeccao` no banco; pode-se eliminá-la com migração manual se desejado.

**Diagramas do sistema:** ver [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

---

## Parte A — Prospecção com XGBRanker (eixo principal)

### A.1 Princípios de arquitetura

| Decisão | Conteúdo |
|--------|----------|
| Interface | Tabela operacional de ranking (dashboard), consulta auditável (Nik). **Sem** heatmap como centro do produto. **Sem** lógica de “validação manual” como gerador de alvo do modelo. |
| Pipeline | Ingestão massiva → normalização → geocodificação/enriquecimento → features tabulares → treino/score XGBoost → publicação de scores → consumo unificado (API + Nik). |
| Alvo | Labels **objetivos e observáveis** (dados internos Tronik + sinais públicos estruturados). Julgamento subjetivo de operação **não** alimenta o *y* do treino. |
| Modelo | **XGBRanker** com `qid` por contexto (RA, bairro normalizado, grade H3, zona operacional, etc.) e objetivo do tipo `rank:ndcg`, adequado quando o entregável é **ordenar** candidatos por relevância dentro do grupo. |
| CNPJ | Tratar **CNPJ como texto** no schema: a Receita Federal passou a prever CNPJ alfanumérico para novas inscrições a partir de julho/2026. |
| Geocodificação em massa | **Não** usar a API pública do Nominatim como motor principal (política de uso limitada). Preferir instância própria, provedor contratado ou fila assíncrona com **cache agressivo**. |
| Execução | Jobs **batch** (pasta `jobs/prospeccao/`), não no request do Flask. Dados crus em Parquet ou `raw_*`; limpos em `staging_*`; camada de aplicação em tabelas finais consumidas pela dashboard e pela Nik. |

### A.2 Modelagem: relevância por grupo

- Cada `qid` agrupa candidatos comparáveis (ex.: mesma RA, mesmo bairro, mesma célula H3 ou mesma zona logística).
- O modelo aprende **quem deve aparecer acima** dentro daquele contexto.
- **Labels** em camadas automáticas, sem envolver operação como fonte de verdade do alvo:
  - **Camada forte (interna):** parceiro ativo, coletor instalado, coleta realizada, volume coletado, recorrência, contrato.
  - **Camada complementar (pública):** bases que indiquem **geração ou obrigações ligadas a REE** (ex.: grandes geradores com PGRS quando o conjunto de dados permitir cruzar com perfil eletrônico, logística reversa de eletroeletrônicos onde houver dado estruturado), equipamentos públicos, saúde/educação como **proxies de fluxo e de TI/labs**, comércio estruturado com forte componente de eletrônicos, polos de circulação.
- **Label ordinal** sugerido (ex.: 0–3), onde 3 = evidência objetiva mais forte de *fit*. Evolui o pipeline: com mais histórico real, reduz-se peso relativo dos sinais públicos e aumenta-se o dos resultados internos.

### A.3 Camadas de dados

1. **Base CNPJ (Receita Federal — dados abertos):** universo inicial de empresas/estabelecimentos no DF (CNAE, situação cadastral, endereço, matriz/filial, porte, natureza jurídica, Simples, sócios conforme layout oficial ZIP por blocos).
2. **Camada geográfica pública (GDF):** Portal de Dados Abertos do DF (CKAN), Geoportal/IDE-DF (camadas territoriais, RA, infraestrutura). *Spatial join* para RA, zona, distâncias e contexto territorial.
3. **OpenStreetMap (ex.: Geofabrik):** POIs e categorias (shopping, mercado, escola, hospital, terminal, etc.) para features de entorno e polos de fluxo onde dados oficiais são esparsos.

### A.4 Esquema lógico de dados (tabelas)

| Tabela | Papel |
|--------|--------|
| `empresa_candidata` | CNPJ (texto), razão social, nome fantasia, CNAE(s), porte, natureza jurídica, situação cadastral, endereço normalizado, origem. |
| `local_candidato` | Lat/lon, RA, bairro, CEP, qualidade da geocodificação, categoria operacional, vínculo com empresa quando houver. |
| `fonte_publica_registro` | Cada registro bruto com hash e data de ingestão (rastreabilidade). |
| `feature_snapshot_prospeccao` | Features calculadas por versão de pipeline/modelo. |
| `score_prospeccao` | Predição, ranking, versão do modelo, top features explicativas (SHAP ou contribuição), data. |
| `modelo_prospeccao` | Artefato, métricas, hiperparâmetros, *feature schema*. |

### A.5 Separação de bancos lógicos (mesmo Postgres no MVP)

| Esquema / prefixo | Uso |
|-------------------|-----|
| **raw** | Ingestão bruta, volumes grandes. |
| **ml** | Features, artefatos, snapshots, scores intermediários. |
| **app** | O que a dashboard e a API leem de forma estável. |

A Nik deve ler **app** e, se necessário, **views** controladas de `ml` — não o raw completo (latência e qualidade de resposta).

### A.6 Jobs sugeridos (`jobs/prospeccao/`)

| Script | Função |
|--------|--------|
| `ingest_cnpj.py` | Download/normalização dos ZIPs Receita, filtro UF=DF, staging. |
| `ingest_osm.py` | Extração regional OSM / Geofabrik, preparação para consultas espaciais. |
| `ingest_gdf.py` | Portal DF, Geoportal, camadas por API/CSV/shape onde aplicável. |
| `normalize_entities.py` | Unificação empresa/local, deduplicação, regras de elegibilidade. |
| `geocode_candidates.py` | Fila + cache; saída com score de qualidade do endereço. |
| `build_features.py` | Montagem do `feature_snapshot` + `qid` + label ordinal. |
| `train_xgboost.py` | XGBRanker, validação, persistência em `modelo_prospeccao`. |
| `score_candidates.py` | Batch scoring, gravação em `score_prospeccao`. |
| `publish_scores.py` | Promoção para camada `app`, versionamento visível à API. |

Harvester inicial (CKAN DF, downloads opcionais Receita/Geofabrik/INEP/CNES/PNCP): pasta `jobs/prospeccao/` e `jobs/prospeccao/README.md`.

### A.7 Features iniciais (objetivas)

**De CNPJ:** CNAE principal e secundários, idade da empresa, porte, natureza jurídica, matriz/filial, situação cadastral, bairro, CEP, presença de e-mail/telefone, contagem de estabelecimentos do mesmo CNPJ básico, filiais no DF, densidade de empresas semelhantes no entorno.

**De localização:** distância à sede/base Tronik, distância a coletores existentes, quantidade de parceiros próximos, candidatos próximos, distância a vias principais, terminais, escolas, hospitais, órgãos, centros comerciais, proxies de alta circulação.

**De categoria / negócio REE:** compatibilidade de CNAE e de perfil de estabelecimento com **descarte de e-waste** (varejo de TI, assistência, grandes varejistas com linha branca, shoppings com pilha de eletrônicos, instituições com laboratório, etc.), intensidade de circulação como proxy de volume potencial de REE.

**Internas (quando existirem):** histórico de coleta **de eletrônicos** por região, volume médio de REE, frequência, sucesso/inadimplência contratual.

### A.8 Métricas de treino (foco no topo da fila)

- **NDCG@20**, **NDCG@50**, precisão nos primeiros 50, sobreposição com clientes/locais historicamente bem-sucedidos.
- Pergunta-guia: *entre milhares de candidatos no DF, quais 50 a operação deveria ver primeiro hoje?* Erros no meio da lista são menos críticos que erro na ordenação do topo.

### A.9 Dashboard — tela Prospecção

- Formato **tabela**, não mapa central.
- Colunas sugeridas: score, prioridade, nome fantasia, razão social, CNAE, categoria resumida, RA/bairro, endereço, telefone/e-mail quando houver, evidências, distância logística, origem dos dados, data de atualização, ação (criar lead/tarefa/contato).
- Filtros: RA, categoria, CNAE, score mínimo, com contato disponível, sem lead criado, perto de rota existente, porte, atualização recente.

### A.10 Nik — tools internas (não texto solto)

| Tool (conceito) | Comportamento |
|-----------------|---------------|
| `buscar_candidatos_prospeccao(filtros)` | Ranking paginado, mesma versão de modelo que a dashboard. |
| `explicar_candidato(id)` | Evidências + contribuições de features (pré-calculadas com o score quando possível). |
| `comparar_candidatos(ids)` | Lado a lado de features-chave e scores. |
| `gerar_roteiro_contato(id)` | Texto operacional a partir de dados estruturados + políticas de tom de voz. |
| `criar_tarefa_comercial(id)` | Integração CRM/tarefas. |

Respostas **auditáveis** (ex.: “topo porque CNAE compatível, alta densidade comercial, contato público, perto de rota atual, similar a parceiros com coleta recorrente”).

### A.11 Implementação no repositório

- **Serviço:** `banco_dados/services/prospeccao_xgb_service.py` — carrega artefato XGBoost, valida *schema* de features, batch scoring, escrita em `score_prospeccao`.
- **Orquestrador:** job em `jobs/prospeccao/` (ex.: `run_pipeline.py`) ou módulo novo com outro nome — **não** reintroduzir o antigo `banco_dados/services/ml_prospeccao.py` (removido).
- **API:** `GET /api/ml/prospeccao` (ou prefixo acordado) — ranking paginado, filtros, explicações; mesma fonte que a Nik.

### A.12 MVP técnico (recorte)

1. Ingestão: **CNPJ DF** + **OSM** + **GDF/Geoportal** (+ INEP/CNES conforme capacidade da equipe na mesma sprint).
2. Normalização + geocodificação com elegibilidade pré-ranking: ativos, endereço no DF, CNAEs plausíveis, CNPJ válido, sem duplicidade óbvia, geocodificação mínima aceitável.
3. Tabela única de candidatos enriquecida; `feature_snapshot`; **XGBRanker** com labels objetivos; **scoring diário** (ou frequência acordada).
4. Tela de ranking na dashboard + tools da Nik apontando para a mesma tabela/versionamento.

---

## Parte B — Fontes de dados (lista operacional)

Legenda de extração: **ZIP/CSV** = download direto; **API** = endpoint estável; **WFS/REST** = serviços geográficos; **Investigar** = depende de termos, formato ou crawl incremental.

### B.1 Fontes prioritárias (primeira onda de ingestão)

| Prioridade | Fonte | O que extrair | Como entra no modelo | Extração |
|:-----------:|--------|----------------|----------------------|----------|
| 1 | **Receita Federal — Dados Abertos CNPJ** | Empresas, estabelecimentos, CNAEs, natureza jurídica, porte, situação cadastral, endereço, matriz/filial, abertura, Simples, sócios (layouts Empresas*, Estabelecimentos*, Socios*, Simples, tabelas de domínio) | Base-mãe de candidatos; filtro UF=DF, ativos, CNAE/endereço | **ZIP** por blocos no site da Receita |
| 2 | **IBGE — CNEFE 2022** | Endereços georreferenciados, espécie de unidade, atributos de endereçamento | Validação/refino de geocode, densidade por área | **Download** IBGE (microdados/agregados conforme produto) |
| 3 | **OpenStreetMap / Geofabrik** | POIs, vias, edificações, comércio, educação, saúde, transporte | Features de entorno, distâncias a polos de fluxo | **PBF** regional + pipeline (osmium/pyosmium, etc.) |
| 4 | **INEP — Censo Escolar / Catálogo de Escolas** | Escolas públicas/privadas, funcionamento, modalidade, localização | Proxy de fluxo e de unidades com laboratório/TI (REE), proximidade | **CSV/API** INEP |
| 5 | **DATASUS / CNES** | Estabelecimentos de saúde, tipo, gestão, endereço, competência | Candidatos/features de proximidade a polos de saúde | **Download** por competência (DATASUS) |
| 6 | **Geoportal / IDE-DF** | RAs, limites administrativos, lotes, setores, infraestrutura, equipamentos urbanos | *Spatial join*, RA, zona, distância logística | **WFS/ArcGIS REST** (por camada) |
| 7 | **IPEDF / PDAD / Atlas do DF** | Renda, população, domicílios, trabalho, indicadores por **RA** (PDAD Ampliada 2024 — 35 RAs) | Contexto socioeconômico por região | **XLSX/CSV/PDF** conforme publicação |
| 8 | **Portal de Dados Abertos do DF (CKAN)** | Catálogo multi-tema (saúde, mobilidade, meio ambiente, transparência, SLU, DETRAN, DER, SEMOB, JUCIS-DF, etc.) | Hub de ingestão incremental; novos conjuntos | **API CKAN** + download por recurso |

### B.2 Sinais comerciais e institucionais

| Fonte | O que extrair | Uso | Extração |
|--------|---------------|-----|----------|
| **JUCIS-DF** | Estatísticas de empresas ativas/constituídas/extintas por natureza | Dinamismo por NJ (não substitui Receita) | **CSV** no portal DF |
| **Transparência DF** | Licitações, contratos, convênios, despesas | CNPJ/entidades fornecedoras do GDF | **CSV/HTML** (portal) |
| **Compras.gov.br / PNCP** | Contratações públicas, objeto, valores, UF, CNPJ | Fornecedores ativos, grandes contratos no DF | **API/JSON/CSV** |
| **Cadastur (Min. Turismo)** | PJ/PF cadastrados no setor turístico | Hotéis, agências, eventos, fluxo | **Consulta/Base** (verificar formato atual) |

### B.3 Mobilidade, fluxo e território

| Fonte | O que extrair | Uso | Extração |
|--------|---------------|-----|----------|
| **DETRAN-DF** (dados abertos) | Pedestres, fiscalização, acidentes, indicadores | Proxies de circulação | **CSV** portal DF |
| **DER-DF** | Malha rodoviária, obras de arte, condições | Distância a vias principais, logística | **Geodados/portal** |
| **SEMOB / DF no Ponto** | Linhas, pontos, terminais | Fluxo (prioridade após OSM/Geoportal) | **Investigar** (API vs export) |
| **Metrô-DF** | Estações, linhas | Distância a polos de transporte | **Dados abertos / site** |

### B.4 REE, PGRS e aderência ao negócio (e-waste)

| Fonte | O que extrair | Uso | Extração |
|--------|---------------|-----|----------|
| **SLU-DF — Grandes geradores** | Normas, PGRS, prestadores, contexto regulatório | *Fit* quando o dado público permitir relacionar a **fluxo de resíduos que inclua REE** ou obrigações de destinação | **Web + PDF**; confirmar lista tabular pública |
| **SLU — PGRS Digital** | Gestão de resíduos por estabelecimento | Integração futura / labels se houver acesso e granularidade útil para REE | **Sistema** (não assumir open data completo) |
| **SLU via CKAN DF** | Conjuntos publicados pela organização SLU | Datasets reutilizáveis alinhados a REE ou a cadastro de geradores | **CKAN** organização=SLU |

### B.5 Atalho para padronização

| Fonte | Uso |
|--------|-----|
| **Base dos Dados** | Acelera consumo de CNES, Censo Escolar, compras, etc., em SQL/BigQuery; manter **fonte oficial** como referência de atualização e auditoria. |

### B.6 Ordem prática sugerida

1. **Receita (CNPJ) + CNEFE + OSM + Geoportal/RA + INEP + CNES** — base grande com empresa, categoria, endereço, coordenada, entorno e fluxo institucional.  
2. Depois: **CKAN DF**, **JUCIS**, **Transparência DF**, **PNCP**, **DETRAN/DER**, **SLU** — enriquecimento, atividade pública, logística e sinais de contexto **REE** onde aplicável.

### B.7 Linha de chegada analítica

Uma **visão única** para dashboard e Nik (camada `app`):

`cnpj`, `nome`, `categoria`, `cnae`, `endereco`, `lat`, `lon`, `ra`, `origens`, `features` (ou referência a snapshot), `score_xgb`, `ranking`, `motivos_modelo`, `data_atualizacao`, `versao_modelo`.

---

## Parte C — Frentes ML complementares (produto e edital)

Resumo do que já estava no plano original; útil para cronograma e demonstração multidimensional de IA.

### C.1 Módulo 1 — Predição de enchimento (séries temporais)

- **Dados:** `nivel_preenchimento`, sazonalidade, histórico de `coletas`.  
- **Modelo:** Prophet ou ARIMA por coletor.  
- **Saída:** `predicted_full_datetime` + intervalo.  
- **Onde:** card do coletor, alertas.  
- **Service sugerido:** `banco_dados/services/ml_predicao.py`.

### C.2 Módulo 2 — TRONIK Score (priorização de **coletores** operacionais)

- Distinto do ranking de **prospecção**: aqui o alvo continua ligado a eficiência de rota/coleta (lucro/km, distância, nível, vizinhança).  
- **Modelo:** XGBoost ou LightGBM em tabular.  
- **Service sugerido:** `banco_dados/services/ml_score.py`.

### C.3 Módulo 3 — Narrativa de impacto (NLP / Ollama)

- Agregação por parceiro → prompt estruturado → modelo open-source via Ollama → cache no banco.  
- **Service sugerido:** `banco_dados/services/ml_narrativa.py`.

### C.4 Dados externos para narrativa e relatórios

- CEMPRE / fatores CO₂; IBGE/SNIS onde couber; clima (INMET/Open-Meteo) como feature opcional para enchimento.

---

## Parte D — Mapeamento edital (resumo)

| Tema edital | Onde está no plano |
|-------------|-------------------|
| Problema e personas | Operadora (fila de prospecção + coletores); parceiro (narrativa); analista (cruzamentos). |
| Automação / predição | Parte A (ranking prospectivo); Parte C.1 e C.2. |
| Geração de conteúdo | Parte C.3. |
| Banco e API | Tabelas Parte A; endpoints `/api/ml/prospeccao`, predição, ranking coletores, narrativa. |
| LGPD | Finalidade definida; minimização; explicabilidade; evitar uso indiscriminado de dado pessoal em scoring sem base legal documentada. |

---

## Parte E — Cronograma sugerido (ajustar às datas do semestre)

| Fase | Entrega |
|------|---------|
| 1 | Esquema `raw` / `ml` / `app` + migrações das tabelas da Parte A.4 |
| 2 | `ingest_cnpj` + `normalize` + elegibilidade DF |
| 3 | Geocodificação com fila + cache + `local_candidato` |
| 4 | `ingest_osm` + `ingest_gdf` + primeiras features de entorno |
| 5 | `build_features` + labels ordinais + `train_xgboost` (XGBRanker) |
| 6 | `score_candidates` + `publish_scores` + `prospeccao_xgb_service` |
| 7 | Rota API + tela tabela dashboard + tools Nik |
| 8 | Métricas NDCG@k em validação + monitoramento de *drift* por versão |

---

## Dependências Python (prospecção)

- `xgboost` (com suporte a treino *ranking* na versão utilizada)  
- `scikit-learn` (métricas, *preprocessing* onde necessário)  
- `pandas`, `pyarrow` (Parquet), `geopandas` / `shapely` (joins espaciais)  
- Biblioteca de geocodificação escolhida (self-hosted ou provedor) — **não** depender só do Nominatim público em lote.

---

*Documento único de referência para ML Tronik: prospecção XGBRanker como núcleo operacional; demais módulos como complemento ao produto e ao edital.*
