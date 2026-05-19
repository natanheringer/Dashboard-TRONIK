# Registro de Mudanças Técnicas

**Data:** 2026-05-18

## Introdução

Este documento consolida as otimizações, correções de integridade de dados e endurecimento da infraestrutura implementadas no pipeline de prospecção REEE, camada de dados e infraestrutura de banco. As mudanças cobrem eliminação de padrões N+1, integridade transacional, correção de data leakage em ML, e optimizações de complexidade algorítmica.

---

## Eliminação de Queries N+1 e Eager Loading

- **jobs/prospeccao/build_features.py:19-29** — Importação de `joinedload` de `sqlalchemy.orm` e aplicação em `EmpresaCandidata.locais`. Query modificada para usar `.options(joinedload(EmpresaCandidata.locais))`, eliminando ~87.000 SELECTs lazy-load por execução (redução de 99%+). Carregamento eager dos locais associados elimina iteração implícita durante construção de features, reduzindo round-trips ao banco sem duplicação de dados em memória.

- **jobs/prospeccao/normalize_candidates.py:313-320** — Eager loading em geocodificação. Query de `LocalCandidato` alterada para `.options(joinedload(LocalCandidato.empresa))`, eliminando lazy-load de empresa durante iteração de geocodificação. Reduz queries implícitas de ~N a 1.

- **jobs/prospeccao/normalize_candidates.py:321-327** — Eager loading em geração de QID. Query de `LocalCandidato` alterada para `.options(joinedload(LocalCandidato.empresa))`, eliminando lazy-load de empresa durante geração de QID. Reduz queries implícitas de ~N a 1.

- **jobs/prospeccao/score_candidates.py:224-233** — Pré-carregamento de scores existentes antes de loop de upsert. Dict `{(snapshot_id, modelo_id): row}` pré-populado com `ScoreProspeccao` existentes. Loop de upsert consulta dict em memória (O(1)) em vez de SELECT por empresa (N+1), reduzindo round-trips de ~87k queries para única query inicial. Implementa padrão "load once, check many".

- **banco_dados/notificacoes.py:155-173** — Pré-carregamento de notificações em funções de alerta. Query de `Notificacao` movida para fora do loop de coletores. Pré-carregamento com `.filter(Notificacao.data_criacao >= limite_data).all()` + `.in_([coletor_ids])`, resultado mapeado em `dict[coletor_id, list[Notificacao]]`. Idem em `verificar_alertas_sensores()` com pré-carregamento de `Coletor`. Query de `Usuario` admin pré-carregada uma vez em `processar_alertas()`. Reduz N+1 queries; para 1000 coletores com alerts, elimina 1000 queries de notificação, reduzindo latência de segundos para milissegundos.

---

## Otimizações de Performance e Complexidade Algorítmica

- **jobs/prospeccao/enrichment_proxies.py:103-113** — Otimização de consultas espaciais com BallTree (sklearn). Função `_count_within_radius` substituiu loop O(N²) por estrutura `BallTree` com métrica haversine (distância geodésica). Pré-computação de índice espacial em única iteração, consultas de range em busca logarítmica. Redução exponencial em pipelines com múltiplos raios de busca.

- **jobs/prospeccao/enrichment_proxies.py:115-122** — Caching de nomes de coluna em `_build_osm_index` e `_build_aggregate_index`. Nomes de coluna movidos para fora dos loops de linha; antes recalculados por cada registro via `[col for col in row.keys() if ...]`, agora computados uma única vez. Reduz regex matching e alocação de listas por registro.

- **jobs/prospeccao/build_features.py:63-70** — Reescrita de `_compute_feature_statistics()` com padrão acumulador de single-pass. Antes: dois loops sobre features (primeira agregação, segunda normalização). Depois: acumulação em dicionários durante primeira iteração, normalização sem segundo loop. Complexidade temporal O(N) em vez de O(2N), reduzindo alocações de memória e passe sobre dados.

- **banco_dados/services/preview_service.py:99-109** — Otimização de contagens em `estatisticas_resumo()`. Carregamento de todos objetos ORM substituído por 4 queries `func.count()` com filters opcionais. Elimina overhead de desserialização ORM para leitura de contagem, reduzindo transferência de rede e consumo de memória em proporção ao tamanho da tabela.

- **banco_dados/services/preview_service.py:105-109** — Lookup de coleta recente otimizado em `get_ultima_coleta_por_coletor()`. Busca linear `next((x for x in coletas if x.coletor_id == cid), None)` substituída por pré-computação de dict `coletas_by_id`. Reduz complexidade de O(N²) para O(N); para 10.000 coletores, diferença de ~100 ms para milissegundos.

- **jobs/prospeccao/build_features.py:45-52** — Cache de QID para múltiplas localizações. Estrutura `qid_cache: dict[tuple[int, int | None], str]` populada durante iteração sobre `qid_stats`, reutilizada no loop de construção de features por empresa. Evita chamadas redundantes a `listwise_training_qid()` para mesmas tuplas `(empresa_id, local_id)`.

- **jobs/prospeccao/build_features.py:54-61** — Importação de funções auxiliares a nível de módulo. `build_internal_label_index` e `lookup_internal_score` antes reimportados dentro do loop de features (~87k iterações), agora carregados uma única vez no início. Redução de I/O de módulos e namespacing em hot path.

- **jobs/prospeccao/ranker_contract.py:141-150** — Validação eficiente de features com `frozenset` pré-computado. `_EXPECTED_FEATURES = frozenset(FEATURE_NAMES)` a nível de módulo. `validate_feature_contract()` usa `dict.keys()` (view, não aloca) e comparação contra frozenset (O(N) com hash). Antes alocava novo set por chamada; reduz garbage collection em loop de validação.

---

## Integridade de Dados e Atomicidade Transacional

- **banco_dados/services/coleta_service.py:147-149** — Consolidação de commits para atomicidade. Dois `db.commit()` sequenciais (criação de coleta + atualização de `ultima_coleta`) mesclados em um único `db.commit()` ao final. Garante atomicidade de operação de inserção + atualização; falha na atualização após inserção bem-sucedida causaria inconsistência.

- **banco_dados/services/crm_service.py:91-93** — Rollback em exceções. Adicionado `db.rollback()` em 5 blocos `except` de funções de escrita (criação, atualização, deleção). Previne sessão em estado de transação aberta após exceção; sem rollback, transação permanecia ativa, causando erro `Can't operate on a dead transaction` em chamadas ORM subsequentes.

- **rotas/api/coletores.py:180-186** — Geocodificação fora de transação para eliminação de lock contention. Funções `criar_coletor_endpoint()` e `atualizar_coletor_endpoint()` movem geocodificação HTTP para **após** `db.commit()`. Registro persistido com coordenadas `None`, geocodificação ocorre fora da transação, segundo `db.commit()` atualiza coordenadas. Elimina lock contention; transações não devem aguardar I/O externo.

---

## Schema e Índices de Banco de Dados

- **banco_dados/modelos.py:11-16** — Remoção de `delete-orphan` em cascatas de coletor. `Coletor.sensores` e `Coletor.coletas` alterados de `cascade="all, delete-orphan"` para `cascade="all"`. Previne deleção em cascata acidental de histórico operacional (sensores e coletas passadas) ao remover/atualizar coletor. Preserva rastreabilidade de dados históricos críticos para análise de série temporal.

- **banco_dados/modelos.py:19-22** — Remoção de `unique=True` em séries temporais. `PredicaoEnchimento.coletor_id` e `TronikScore.coletor_id` removem `unique=True`, mantêm `index=True`. Previsões e scores são séries temporais com múltiplos registros por coletor; constraint `UNIQUE` causava falha em operações de upsert histórico durante treino de modelo e atualização de rankings.

- **banco_dados/modelos.py:29-31** — Índice composto para queries de relatório de coleta. `Coleta.__table_args__` adiciona `Index('idx_coleta_data_coletor_parceiro', 'data_hora', 'coletor_id', 'parceiro_id')`. Suporta queries filtradas por período × coletor × parceiro sem full table scan. Ordem das colunas segue padrão (data → chave estrangeira seletiva → chave estrangeira menos seletiva).

- **banco_dados/modelos.py:33-35** — Foreign key com cascata de deleção. `LocalCandidato.empresa_id` adiciona `ForeignKey("empresa_candidata.id", ondelete="CASCADE")`. Deleção de empresa candidata propaga automaticamente para seus locais no banco, garantindo consistência referencial e eliminação de órfãos.

- **banco_dados/modelos.py:37-43** — Snapshot de features com índice composto e constraint de unicidade. `FeatureSnapshotProspeccao.__table_args__` adiciona índice `Index('idx_feature_snapshot_pipeline_qid_id', 'pipeline_version', 'qid', 'id')` e constraint `UniqueConstraint('empresa_id', 'local_id', 'pipeline_version', name='uq_feature_snapshot_empresa_local_pipeline')`. Índice otimiza queries de treino filtradas por versão de pipeline e QID; constraint garante exatamente um snapshot por tupla (empresa, local, versão), prevenindo duplicação silenciosa em re-runs.

- **banco_dados/modelos.py:45-47** — Índice para scores de prospecção. `ScoreProspeccao.__table_args__` adiciona `Index('idx_score_prospeccao_modelo_pipeline', 'modelo_id', 'pipeline_version')`. Acelera lookup de scores por modelo + versão em queries de ranking e filtragem por modelo treino.

- **banco_dados/modelos.py:49-52** — Cascata de deleção para scores órfãos. `ScoreProspeccao.empresa_id` e `local_id` adicionam `ForeignKey(..., ondelete="CASCADE")`. Scores órfãos limpos automaticamente ao deletar empresa ou local candidato, evitando crescimento não controlado de registros órfãos após limpeza de dados.

---

## Correções de Data Leakage no Pipeline ML

- **jobs/prospeccao/labels_internal.py:174-181** — Prevenção de data leakage temporal. Adicionado parâmetro `cutoff_date: Optional[datetime]` a `build_internal_label_index(db, cutoff_date=None)`. Queries de `Coleta` e `ContratoRecorrente` filtradas por `Coleta.data_hora <= cutoff_date` e `ContratoRecorrente.created_at <= cutoff_date`. Previne inclusão de eventos futuros ao momento de scoring (que constituem vazamento de label forward-looking), permitindo treinamento com snapshot temporal consistente.

- **jobs/prospeccao/labels_internal.py:183-190** — Remoção de sinal futuro (pipeline_won). Contribuição `pipeline_won` (`score += 25.0`) removida de `internal_relevance_continuous()`. Contexto: informação de que empresa "entrou no pipeline" é futura ao momento do scoring. Inclusão em features de treinamento causa overfitting no score do próprio modelo, reduzindo vazamento de informação forward-looking.

- **jobs/prospeccao/train_xgboost.py:201-209** — Filtragem de singletons antes de XGBRanker. XGBRanker com `objective='rank:ndcg'` requer grupos com tamanho ≥ 2. Adicionado filtro `valid_mask = np.array([size >= 2 for size in train_group_sizes for _ in range(size)])` aplicado antes de `model.fit()`, removendo singletons de `X_train`, `y_train` e `group`. Evita erro silencioso de ranking degenerado em grupos com único exemplo, reduzindo instabilidade numérica em otimização de NDCG.

---

## Segurança e Robustez

- **banco_dados/services/account_service.py:71-75** — Otimização de filtro CNPJ com SQL pushdown. Função `_find_by_cnpj_digits()` migra filtro de comparação Python para SQL nativa: `func.replace(func.replace(ContaComercial.cnpj, '.', ''), '-', '') == cnpj_digits`. Elimina full table scan desnecessário; filtro executado no banco com índice se disponível. Em production, índice recomendado em coluna desnormalizada de CNPJ sem formatação.

- **banco_dados/services/nik_tools.py:132-142** — Escaping LIKE para prevenção de SQL injection. Adicionado escaping de caracteres especiais LIKE antes de construção de padrão: `termo.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')`. Parâmetro `escape='\\'` adicionado em todos 13 calls de `.like()` em 3 blocos de busca (coletas, pipeline CRM, contratos). Previne interpretação de `%` e `_` literais do usuário como wildcards SQL; busca por "100%" retornaria matches incorretos sem escaping.

- **banco_dados/modelos.py:24-27** — Serialização defensiva de PreferenciaLayout. Método `to_dict()` envolve `json.loads()` em `try/except (json.JSONDecodeError, TypeError)`, retornando lista vazia `[]` em caso de payload corrompido. Evita erro HTTP 500 em requisições que desserializam preferências com JSON inválido no banco.

- **banco_dados/services/ml_score.py:122-127** — Garantia de ordem de features. Variável de módulo `_XGBOOST_FEATURE_NAMES = [...]` com ordem explícita. Array de features construída como `np.array([[features[f] for f in _XGBOOST_FEATURE_NAMES]])`. XGBoost requer ordem consistente; definição explícita garante ordem e levanta `KeyError` explícito se feature ausente, em vez de falha silenciosa ou ordem aleatória de dict.

---

## Observabilidade e Instrumentação

- **jobs/prospeccao/build_features.py:30-43** — Instrumentação e monitoramento de fases. Importação de módulo `time`. Pipeline dividida em 5 fases com timers explícitos: (1) Carregando empresas, (2) Construindo features, (3) Calculando estatísticas, (4) Labels, (5) Commit em batches. Cada fase registra duração em segundos e ETA baseada em taxa de processamento. Progresso parcial logado a cada 2.000 empresas processadas com métrica de taxa (empresas/segundo). Possibilita identificação de fases lentas e ajuste de BATCH_SIZE.

- **run_pipeline.ps1:190-196** — Streaming de output em tempo real. Função `Run-Step` alterada para streaming de saída do subprocesso. Antes: captura de output ao final da execução (blackout visual durante etapas longas). Depois: `cmd /c "$Cmd 2>&1" | Tee-Object -FilePath $logFile` + `Get-Content $logFile -Raw` para resultado final. Saída exibida em tempo real no terminal durante execução, eliminando período de invisibilidade. Essencial para debugging e monitoramento de etapas longas (treino de modelo, extração de features).

---

## Infraestrutura e Gerenciamento de Conexões

- **jobs/prospeccao/db.py:244-253** — Cache de session factory a nível de módulo. Adicionado `_SESSION_FACTORY_CACHE: dict = {}`. `make_session_factory()` verifica cache por chave `(url, echo)` antes de `create_engine()`. Elimina recriação de engine por processo/chamada, reutiliza pool de conexão (reduz overhead de handshake), evita múltiplas engines com mesma configuração. Trade-off: cache persiste por processo (adequado para job single-threaded).

- **jobs/prospeccao/db.py:255-263** — Health check de conexão com pool pre-ping. Adicionado `pool_pre_ping=True` em `create_engine()`. SQLAlchemy executa `SELECT 1` antes de usar conexão do pool, detectando conexões mortas por timeout de rede (ex: Railway PostgreSQL com timeout inativo). Evita `OperationalError` em ambientes com connection timeout elevado. Trade-off: overhead de ~1 query por connection reuse (negligenciável vs falha de pipeline).

- **banco_dados/utils/db_session.py:58-62** — Pool de conexão com cache de engine a nível de módulo. Variável `_SESSION_FACTORY_CACHE: dict = {}`. Função `get_db_session()` verifica cache por `database_url` antes de chamar `create_engine()`. Elimina múltiplas engines para mesma URL em processos Flask com múltiplos workers; `create_engine()` é operação custosa, pooling reduz overhead de inicialização.

- **banco_dados/utils/db_session.py:63-65** — Validação de conexão em pool. `create_engine()` alterado com parâmetro `pool_pre_ping=True`. Valida conexão antes de uso, evitando erro `OperationalError` por conexão fechada pelo servidor (timeout de idle), especialmente relevante em production com PostgreSQL.

- **jobs/prospeccao/enrichment_proxies.py:124-135** — Sincronização de thread com double-checked locking. Adicionado `_LOAD_LOCK = threading.Lock()` a nível de módulo. `_ensure_loaded()` implementa double-checked locking: (1) verifica `_cache` sem lock (fast path), (2) se não existe, adquire lock, (3) re-verifica `_cache` dentro do lock (previne race de múltiplas threads inicializando), (4) inicializa se ainda vazio. Dict de `ball_trees` copiado antes de mutação para evitar race condition entre threads leitoras/escritoras. Garante thread-safety sem lock em hot path de leitura.

- **jobs/prospeccao/pipeline_ops.py:269-276** — Timeout em subprocessos. Adicionado `timeout=1800` (30 minutos) em `subprocess.run()`. Subprocesso terminado forçadamente se exceder 30 minutos. Antes: etapas do pipeline podiam travar indefinidamente. Permite detecção de deadlock e retry automático em orquestrador de pipeline.

- **jobs/prospeccao/build_enrichment_staging.py:281-293** — Escrita atômica de parquet com write-ahead logging. Cada uma das 3 funções de escrita implementa padrão atômico: (1) escrever em caminho temporário `path.with_suffix(".tmp.parquet")`, (2) flush de dados ao disco, (3) rename atômico `.replace(path)`. Elimina leitura parcial de arquivo em caso de crash durante escrita, garante arquivo sempre em estado consistente (completo ou ausente), compatível com filesystem atomicity de rename.

---

## Otimizações Adicionais de Banco de Dados

- **jobs/prospeccao/normalize_candidates.py:299-311** — Deduplica otimizada com batch delete. Função `deduplicate_empresas()`: DELETE de duplicatas convertido para `db.query(EmpresaCandidata).filter(EmpresaCandidata.id.in_(dup_ids)).delete(synchronize_session="fetch")`. Antes: loop Python com `db.delete(dup)` por registro (~N round-trips). Depois: single query com IN clause e synchronize_session="fetch" (1 round-trip + local update). Reduz latência de operação de O(N) para O(1) no banco.

- **banco_dados/services/contrato_service.py:81-85** — Agregação SQL para soma de valores mensais. Função `calcular_receita_mensal_contratos()` substitui loop Python com acumulação por agregação SQL: `db.query(func.sum(ContratoRecorrente.valor_mensal)).filter(ContratoRecorrente.status == 'ativo').scalar()`. Delegação de agregação ao banco elimina transferência de dados desnecessários e computação em Python. Para tabelas com milhares de registros, redução significativa de latência e memória.

- **banco_dados/services/comercial_service.py:115-117** — Filter before load para otimização de carregamento. Função `analisar_por_parceiro()`: cálculo de `data_inicio` e `data_fim` movido para **antes** do carregamento de parceiros com `joinedload`. Evita carregar dados relacionados antes de calcular o período de filtro, reduzindo volume de joins e desserialização ORM quando período filtrado resulta em subset pequeno de parceiros.

---

## Correções de Compatibilidade de API

- **jobs/prospeccao/build_features.py:90-92** — Substituição de API deprecada. `datetime.utcnow()` → `datetime.now(timezone.utc)`. Alinhamento com deprecação Python 3.12+.

- **jobs/prospeccao/build_features.py:95-99** — Ajuste de tamanho de batch. `BATCH_SIZE`: `5.000` → `50.000`. Reduz overhead de transactions e round-trips ao banco por execução. Trade-off: aumento de 10x em latência de transaction (mitigado por batch write em memória antes de flush).

- **jobs/prospeccao/ranker_contract.py:164-166** — Substituição de API deprecada em ranker_contract. `datetime.utcnow()` → `datetime.now(timezone.utc)`.

- **jobs/prospeccao/labels_internal.py:192-194** — Substituição de API deprecada em labels_internal. `datetime.utcnow()` → `datetime.now(timezone.utc)`.

- **jobs/prospeccao/train_xgboost.py:218-220** — Substituição de API deprecada em train_xgboost. `datetime.utcnow()` → `datetime.now(timezone.utc)`.

- **jobs/prospeccao/score_candidates.py:235-237** — Substituição de API deprecada em score_candidates. `datetime.utcnow()` → `datetime.now(timezone.utc)`.

---

## Validações e Asserts

- **jobs/prospeccao/train_xgboost.py:211-216** — Validação de split temporal. Asserção adicionada pós-split com aviso se validação tiver < 5 qids distintos. Garante que validação representa distribuição suficientemente diversa para avaliação confiável.

- **jobs/prospeccao/build_features.py:72-77** — Filtro de situação cadastral para qualidade de dados. Em `qid_stats`, adicionado filtro `situacao_cadastral != "ATIVA"` antes de cálculo de estatísticas de grupo. Evita inclusão de empresas inativas em agregações (que afetariam distribuições de features).

- **jobs/prospeccao/build_features.py:79-88** — Conversão de referências ORM para primitivos em bucket de batch write. Bucket de batch write alterado de `(empresa_obj, local_obj, qid, features, raw, lid)` (objetos ORM) para `(empresa.id, None, qid, features, raw, lid)` (identificadores primitivos). Benefícios: libera referências ORM após extração, elimina necessidade de `db.expunge_all()` dentro do loop, reduz footprint de memória em grandes datasets (~87k empresas).

- **jobs/prospeccao/ranker_contract.py:152-157** — Tratamento seguro de coordenadas faltantes. `logistics_proximity_exp()` retorna `float('nan')` quando coordenadas são `None`. Antes: levantava exceção implícita durante operação numérica. Depois: NaN propagado como valor válido em cálculos downstream (compatível com XGBoost). Evita crash de pipeline durante scoring de empresas sem geocodificação.

- **jobs/prospeccao/ranker_contract.py:159-162** — Separação explícita de casos de porte. `porte_ordinal()`: casos de `"grande"→1.0` e `"demais"→0.5` separados em branches explícitos. Melhora legibilidade e permite otimização de branch prediction.

---

## Resumo por Arquivo

| Arquivo | Categoria | Nº de Mudanças |
|---------|-----------|----------------|
| jobs/prospeccao/build_features.py | N+1 queries, Performance, Instrumentação | 6 |
| jobs/prospeccao/enrichment_proxies.py | Performance, Thread-safety | 2 |
| jobs/prospeccao/ranker_contract.py | Performance, Robustez, API | 4 |
| jobs/prospeccao/labels_internal.py | Data leakage, API | 3 |
| jobs/prospeccao/train_xgboost.py | Data leakage, Validação, API | 3 |
| jobs/prospeccao/score_candidates.py | N+1 queries, API | 2 |
| jobs/prospeccao/db.py | Infraestrutura | 2 |
| jobs/prospeccao/pipeline_ops.py | Robustez | 1 |
| jobs/prospeccao/build_enrichment_staging.py | Atomicidade | 1 |
| jobs/prospeccao/normalize_candidates.py | N+1 queries, Performance | 3 |
| banco_dados/modelos.py | Schema, Cascatas, Índices | 7 |
| banco_dados/utils/db_session.py | Infraestrutura | 2 |
| banco_dados/services/account_service.py | Segurança | 1 |
| banco_dados/services/contrato_service.py | Performance | 1 |
| banco_dados/services/crm_service.py | Integridade | 1 |
| banco_dados/services/preview_service.py | Performance | 2 |
| banco_dados/services/comercial_service.py | Performance | 1 |
| banco_dados/services/ml_score.py | Robustez | 1 |
| banco_dados/services/nik_tools.py | Segurança | 1 |
| banco_dados/services/coleta_service.py | Atomicidade | 1 |
| banco_dados/notificacoes.py | N+1 queries | 1 |
| rotas/api/coletores.py | Integridade, Lock contention | 1 |
| run_pipeline.ps1 | Observabilidade | 1 |
| **Total** | | **49** |
