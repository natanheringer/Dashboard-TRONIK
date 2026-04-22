# TRONIK Recicla — Plano de Machine Learning
## Alinhado com o edital Porto Digital / Residência em Software & IA

**Data:** 22/04/2026
**Prazo entrega parcial GrowUp:** 27/04/2026
**Prazo final do semestre:** 18/06/2026

---

## Contexto

O projeto TRONIK Recicla está no terceiro semestre com a Porto Digital. Nos semestres anteriores, a equipe construiu a infraestrutura completa: dashboard Flask com 120+ testes, sistema de telemetria IoT com autenticação, mapa com Leaflet, CRM, contratos, relatórios. O sensor ISU (ESP32 + VL53L0X + MPU6050) está em montagem com chegada dos componentes entre 17–30/abr.

O edital desse semestre pede ênfase em IA. A camada de ML se encaixa como evolução natural: os dois primeiros semestres construíram a base de dados e a infraestrutura; o terceiro semestre adiciona inteligência sobre esses dados.

A stack é toda Python. O APScheduler já está integrado. O Railway hospeda tudo. Não precisa de GPU — tudo roda em CPU.

---

## Três módulos de ML — do que entrega valor real ao que impressiona

### Módulo 1 — Predição de enchimento (séries temporais)

**O que resolve:** hoje a dashboard diz "coletor a 84%". Isso é reativo — a Maiara só sabe que precisa coletar quando já está cheio. Com predição, a dashboard diz "coletor a 84%, **enche quinta às 14h**". Isso permite planejar coletas com antecedência, otimizar rotas, evitar viagens desperdiçadas.

**Dados de entrada:**
- Série temporal de `nivel_preenchimento` por coletor (telemetria do ESP32, a cada 15 min)
- Dia da semana e hora (sazonalidade: shopping enche mais em dia útil, condomínio é constante)
- Histórico de coletas realizadas (tabela `coletas` com `data_hora`, `volume_estimado`)

**Modelo:**
- **Prophet** (Facebook/Meta) — feito para séries temporais com sazonalidade semanal e feriados brasileiros. Alternativa: `statsmodels.ARIMA` se quiser algo mais leve.
- Um modelo por coletor. Com 2-3 semanas de leituras a cada 15 min = ~1.300 pontos por coletor. Suficiente para Prophet.
- Output: `predicted_full_datetime` (quando atinge 90%) + intervalo de confiança superior/inferior.

**Onde aparece na dashboard:**
- Card do coletor no Monitoramento: "84% · enche em ~52h"
- Gráfico de linha do coletor ganha projeção pontilhada com faixa de incerteza sombreada
- Alerta muda de "nível > 80%" para "previsão de encher em < 48h"

**Implementação:**
- Novo model: `PredicaoEnchimento` (coletor_id, predicted_full_at, confianca_lower, confianca_upper, calculado_em)
- Novo service: `banco_dados/services/ml_predicao.py`
- Job no APScheduler: roda 2x/dia, recalcula previsões para todos os coletores ativos
- Endpoint: `GET /api/preview/coletor/<id>/predicao` retorna previsão + série histórica + projeção

**Dependências:** `prophet` ou `statsmodels` no `requirements.txt`

**Esforço:** 1 semana

---

### Módulo 2 — TRONIK Score (classificação de prioridade)

**O que resolve:** a decisão "qual coletor coletar primeiro" hoje é baseada só em nível. Mas isso ignora: distância da sede (coletor cheio a 50km vale menos que um a 5km), valor do material (parceiro que gera mais lucro/kg deve ser priorizado), agrupamento geográfico (dois coletores próximos ambos a 70% valem mais que um isolado a 90%), custo de combustível, dias sem coleta.

O TRONIK Score sintetiza tudo isso num número de 0 a 100 por coletor, que significa "urgência × viabilidade × valor".

**Dados de entrada (feature engineering):**
- `nivel_preenchimento` atual (do sensor)
- `velocidade_enchimento` (derivada da predição — Módulo 1)
- `km_da_sede` (calculado via coordenadas)
- `dias_sem_coleta` (diff entre agora e `ultima_coleta`)
- `lucro_medio_por_kg` (média histórica do parceiro, da tabela `coletas`)
- `volume_medio_historico` (média de `volume_estimado` das coletas anteriores desse coletor)
- `coletores_proximos_acima_60` (contagem de outros coletores num raio de 5km com nível > 60%)
- `preco_combustivel_atual` (configurável, env var ou campo no banco)

**Modelo:**
- **XGBoost** ou **LightGBM** — gradient boosting, padrão da indústria para tabular data
- Target de treino: score derivado do histórico de coletas reais: `lucro_total / (km_percorrido + 1)` normalizado 0-100. Coletas com alto retorno/km = score alto, coletas com baixo retorno/km = score baixo.
- Dataset de treino: as 50+ coletas reais da TRONIK já importadas no banco via CSV, com volume, km, lucro/kg, parceiro. É pouco mas suficiente para um modelo baseline + cross-validation.

**Onde aparece na dashboard:**
- Card do coletor: badge circular com o score (97, 82, 45...) em cor semântica
- Monitoramento ganha toggle "Ordenar por: Nível | TRONIK Score"
- Mapa: tamanho do pin proporcional ao score, não ao nível
- Relatórios: "Top 5 coletores por eficiência" baseado no score

**Implementação:**
- Novo service: `banco_dados/services/ml_score.py`
- Job no APScheduler: roda 1x/dia, recalcula score para todos os coletores
- Endpoint: `GET /api/preview/coletores/ranking` retorna lista ordenada por score
- Modelo serializado em `banco_dados/ml_models/score_model.pkl` (joblib)

**Dependências:** `scikit-learn`, `xgboost` no `requirements.txt`

**Esforço:** 1 semana (depende do Módulo 1 para feature de velocidade)

---

### Módulo 3 — Narrativa de impacto por IA generativa (NLP)

**O que resolve:** o painel do parceiro mostra números (512 kg coletados, 738 kgCO₂ evitados). Números frios não emocionam. O parceiro precisa de narrativa para usar em relatório ESG, post em rede social, argumento de renovação de contrato.

**Como funciona:**
- Backend agrega dados do parceiro no período (kg total, número de coletas, composição estimada, comparativo com mês anterior, equivalências ambientais)
- Monta um prompt estruturado com esses dados
- Chama um modelo open-source via **Ollama** (DeepSeek, GLM-4, Qwen 2.5, ou GPT4All — todos gratuitos, sem chave de API paga)
- Recebe texto narrativo personalizado
- Armazena no banco para cache (não chama o modelo toda vez)
- Renderiza no painel do parceiro com tipografia editorial

**Infraestrutura de IA — Ollama:**
- Ollama disponibiliza modelos open-source com endpoint HTTP compatível com OpenAI (`/api/chat`, `/api/generate`)
- Modelos candidatos (todos gratuitos, sem licença restritiva):
  - **DeepSeek-R1** ou **DeepSeek-V3** — melhor qualidade de texto em português entre os open-source, raciocínio forte
  - **GLM-4** (9B) — bom em português, leve o suficiente pra CPU
  - **Qwen 2.5** (7B/14B) — alternativa multilíngue sólida
  - **Llama 3.1** (8B) — fallback universal, ampla documentação
- Ollama roda local (notebook da equipe / servidor da faculdade) ou em cloud gratuita
- SDK Python: `ollama` (pip install ollama) ou chamada HTTP direta com `requests` (sem dependência extra)

**Exemplo de output:**
> "Em abril, o Taguatinga Shopping recolheu 512 kg de resíduos eletrônicos — crescimento de 23% em relação a março. Isso equivale a evitar a emissão de 738 kg de CO₂, o mesmo que retirar 3 carros de circulação por um mês inteiro. O volume sugere adesão crescente dos frequentadores ao ponto de coleta, especialmente em dias úteis."

**Onde aparece na dashboard:**
- Painel do Parceiro: bloco editorial abaixo do hero de impacto
- Relatórios: seção "Resumo executivo gerado por IA" no topo
- Exportação PDF: o texto narrativo é incluído automaticamente

**Implementação:**
- Novo service: `banco_dados/services/ml_narrativa.py`
- Prompt template em `banco_dados/prompts/narrativa_parceiro.txt`
- Job no APScheduler: roda 1x/mês por parceiro (ou sob demanda pelo operador)
- Endpoint: `GET /api/preview/parceiro/<id>/narrativa`
- Cache: tabela `NarrativaGerada` (parceiro_id, periodo, texto, gerado_em, modelo_usado)
- Config via env vars: `OLLAMA_HOST` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `deepseek-r1:8b`)

**Dependências:** `ollama` ou apenas `requests` no `requirements.txt`. **Custo: zero.** Sem chave de API, sem plano pago, sem rate limit externo.

**Esforço:** 2-3 dias (é a mais rápida de implementar)

---

## Dados externos — cruzamento ambiental

Para enriquecer os relatórios e o painel do parceiro, a equipe pode cruzar dados internos com fontes externas:

**CEMPRE (Compromisso Empresarial para Reciclagem):**
- Fator de conversão: 1 kg e-waste ≈ 1.44 kgCO₂eq evitados (fonte EPA WARM)
- Preço médio de material reciclado por categoria (cobre, alumínio, plástico PCB)
- Atualizado anualmente, pode ser hardcoded como constante no MVP

**IBGE / SNIS (Sistema Nacional de Informações sobre Saneamento):**
- Dados de geração de resíduo per capita por região do DF
- Permite calcular "% do e-waste da região que a TRONIK está capturando"
- Narrativa: "Vocês coletaram 3% de todo o e-waste gerado em Taguatinga neste mês"

**Open Weather / INMET:**
- Correlação clima × volume de descarte (hipótese: dias de chuva = menos descarte)
- Feature adicional pro modelo de predição de enchimento
- API gratuita, fácil de integrar

---

## Mapeamento para o edital Porto Digital

### Seção 1 — Definição do Problema e Personas "IA-Augmented"

**Onde a IA gera valor:**
- **Predição** → Módulo 1 (quando o coletor vai encher)
- **Automação** → Módulo 2 (priorização automática por TRONIK Score)
- **Geração de conteúdo** → Módulo 3 (narrativa de impacto ESG)

**Personas IA-augmented:**
- **Maiara (operadora TRONIK):** sem IA, verifica manualmente 40 coletores. Com IA, recebe previsão de enchimento e ranking automático. Decide olhando o score, não o nível.
- **Parceiro (ex: gerente do Taguatinga Shopping):** sem IA, não sabe o impacto do coletor. Com IA, recebe relatório narrativo mensal gerado automaticamente.
- **Analista ambiental (futuro):** sem IA, compila dados manualmente. Com IA, dashboard cruza dados TRONIK com dados CEMPRE/IBGE e gera análise comparativa.

**Cenários de falha / edge cases:**
- Sensor sem dados suficientes (< 3 dias de leituras): modelo retorna "dados insuficientes", dashboard mostra "—" em vez de previsão errada
- Coleta realizada mas sensor não zerou (hardware delay): pipeline detecta delta negativo anômalo, marca como "coleta provável" e reseta baseline do modelo
- API de IA generativa indisponível (Ollama offline, timeout): sistema usa cache do último texto gerado + flag "gerado em DD/MM" para transparência. Se Ollama nunca rodou, mostra estado vazio com botão "Gerar relatório"
- Score absurdo (coletor novo sem histórico): modelo usa prior conservador (score = 50) até acumular 5+ coletas

### Seção 2 — Backlog AI-First

**Épico: Inteligência Preditiva**
- US01: Como operadora, quero ver a previsão de quando cada coletor vai encher, para planejar coletas com antecedência
- US02: Como operadora, quero que os coletores sejam ranqueados automaticamente por prioridade, para otimizar minhas rotas
- US03: Como parceiro, quero receber um resumo narrativo do meu impacto ambiental, para usar em relatórios ESG

**Critérios de aceite de IA:**
- US01: previsão com erro médio < 24h (MAPE < 15%) em coletores com > 14 dias de dados
- US02: score correlaciona com lucro/km histórico (Spearman ρ > 0.6) em cross-validation
- US03: texto gerado em < 30s via Ollama local, factualmente correto (validação pós-geração confirma que números no texto batem com input), tom profissional em PT-BR

### Seção 3 — Banco de dados e API

**Entidades novas relacionadas a IA:**
- `LeituraSensor` (sensor_id, nivel, bateria, timestamp) — série temporal para predição
- `PredicaoEnchimento` (coletor_id, predicted_full_at, confianca, calculado_em)
- `TronikScore` (coletor_id, score, features_json, calculado_em)
- `NarrativaGerada` (parceiro_id, periodo_inicio, periodo_fim, texto, modelo, gerado_em)

**Endpoints ML:**
- `GET /api/ml/predicao/<coletor_id>` → previsão de enchimento + série + projeção
- `GET /api/ml/ranking` → coletores ordenados por TRONIK Score
- `GET /api/ml/narrativa/<parceiro_id>` → texto narrativo do período
- `POST /api/ml/retreinar` (admin) → força recálculo de todos os modelos

**Fluxo completo:**
```
ESP32 → POST /api/sensor/telemetria (a cada 15min)
  → Persiste em LeituraSensor
  → WebSocket atualiza dashboard em tempo real

APScheduler (2x/dia):
  → Lê séries de LeituraSensor
  → Roda Prophet/ARIMA por coletor → salva PredicaoEnchimento
  → Calcula features → roda XGBoost → salva TronikScore

APScheduler (1x/mês por parceiro):
  → Agrega dados por parceiro
  → Chama Ollama (DeepSeek/GLM/Qwen) com prompt template
  → Salva NarrativaGerada

Dashboard Preview:
  → GET endpoints ML
  → Renderiza previsão, score, narrativa nas views v2
```

### Seção 4 — Arquitetura e Stack

**Stack de IA (100% gratuita):**
- `scikit-learn` (pipeline de features, métricas) — gratuito, open-source
- `Prophet` ou `statsmodels` (séries temporais) — gratuito, open-source
- `XGBoost` (TRONIK Score) — gratuito, open-source
- **Ollama + modelos open-source** (narrativa NLP) — gratuito, sem chave de API:
  - DeepSeek-R1/V3 (preferencial, melhor português)
  - GLM-4 9B (alternativa leve)
  - Qwen 2.5 7B (fallback multilíngue)
- `joblib` (serialização de modelos) — gratuito

**Nota sobre custos:** toda a stack de IA é gratuita. Não há dependência de API paga. O Ollama roda local ou em cloud sem custo. Modelos open-source com licenças permissivas (Apache 2.0, MIT).

**Estrutura de pastas ML:**
```
banco_dados/
├── services/
│   ├── ml_predicao.py        # Prophet/ARIMA por coletor
│   ├── ml_score.py           # XGBoost feature engineering + treino + inferência
│   └── ml_narrativa.py       # Prompt template + chamada Ollama + cache
├── ml_models/                # modelos serializados (.pkl)
│   ├── predicao_coletor_1.pkl
│   ├── predicao_coletor_2.pkl
│   └── score_model.pkl
└── prompts/
    └── narrativa_parceiro.txt
```

**Tratamento de erros:**
- Ollama offline ou timeout (>30s): retry com backoff exponencial (3 tentativas), fallback para cache da última narrativa gerada. Se nunca gerou, UI mostra estado vazio com explicação
- Modelo Ollama gera texto com números errados: validação pós-geração compara valores no texto com dados do banco, rejeita e retenta se divergir
- Modelo com dados insuficientes para predição: retorna `{"status": "insuficiente", "minimo_dias": 14}`, UI mostra estado vazio
- XGBoost com dataset pequeno (<30 amostras): usa fallback para heurística simples (regra de 3 com nível e km)
- Job do APScheduler falha: log + notificação no sistema de notificações existente, não impede dashboard de funcionar

### Seção 5 — Prompt Engineering

**Modelo utilizado:** Ollama com DeepSeek-R1 8B (open-source, gratuito, sem API key)
**Infraestrutura:** Ollama rodando local ou em servidor da equipe, endpoint HTTP `http://localhost:11434/api/chat`

**Prompt da narrativa (exemplo documentado):**

```
Objetivo: gerar resumo executivo mensal de impacto ambiental para parceiro

Contexto informado:
- Nome do parceiro: {parceiro_nome}
- Período: {periodo_inicio} a {periodo_fim}
- Total coletado: {total_kg} kg
- Número de coletas: {num_coletas}
- CO₂ evitado: {co2_evitado} kg (fator 1.44 kgCO₂/kg e-waste, fonte EPA WARM)
- Comparativo mês anterior: {delta_percentual}%
- Top material: {top_material}

Saída esperada:
- 3 a 5 frases em português brasileiro
- Tom profissional mas acessível
- Incluir pelo menos uma equivalência concreta (árvores, carros, energia)
- Todos os números devem corresponder exatamente aos dados fornecidos
- Não inventar dados que não foram fornecidos

Problemas encontrados:
- Sem guardrail, o modelo inventa números → resolvido com validação pós-geração (regex extrai números do texto, compara com input)
- Textos genéricos demais → resolvido adicionando nome do parceiro e comparativo temporal no prompt
- Inconsistência de tom entre modelos → resolvido com few-shot examples no prompt (2 exemplos de output ideal antes da instrução)
- DeepSeek responde em inglês se prompt não for explícito → resolvido com instrução "Responda exclusivamente em português brasileiro" no system prompt

Ajustes por modelo:
- DeepSeek-R1: melhor qualidade, mas precisa de system prompt explícito em PT-BR
- GLM-4: bom em PT-BR nativo, texto mais curto, precisa pedir elaboração
- Qwen 2.5: multilíngue sólido, às vezes mistura formalidade, ajustar tom no prompt
```

**Chamada via SDK Python:**
```python
import ollama

response = ollama.chat(
    model='deepseek-r1:8b',
    messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': prompt_com_dados}
    ]
)
texto = response['message']['content']
```

**Alternativa sem SDK (apenas requests):**
```python
import requests

response = requests.post(
    f"{OLLAMA_HOST}/api/chat",
    json={
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_com_dados}
        ],
        "stream": False
    }
)
texto = response.json()["message"]["content"]
```

---

## Cronograma de implementação

**Semana 22-27 abril (entrega parcial Porto Digital):**
- Documentar plano ML no formato do edital (seções 1-5)
- Criar modelos de dados das 4 entidades novas
- Criar esqueleto dos 3 services (ml_predicao, ml_score, ml_narrativa) com interface definida

**Semana 28 abril - 4 maio:**
- Implementar Módulo 3 primeiro (narrativa NLP) — é o mais rápido e mais demonstrável
- Gerar dados simulados de telemetria para desenvolvimento do Módulo 1

**Semana 5-11 maio:**
- Implementar Módulo 1 (predição de enchimento) com dados simulados
- Integrar na dashboard preview (projeção visual no card do coletor)

**Semana 12-18 maio:**
- Implementar Módulo 2 (TRONIK Score) com dados reais de coleta
- Integrar ranking na tela de Monitoramento

**Semana 19 maio - 18 junho:**
- Validar com dados reais do sensor (hardware em campo)
- Ajustar modelos, preparar demonstração final
- Documentar resultados para bancas