# SPEC — Nik: Agente de IA da Tronik Recicla

**Repositório-alvo:** `github.com/natanheringer/dashboard-tronik`
**Versão da spec:** 1.1
**Data:** Abril 2026
**Status:** Pronta para implementação, com ajustes de aderência ao repositório atual

---

## 0. Contexto operacional

A Tronik Recicla é uma startup de impacto socioambiental fundada por Maiara Gualberto, empreendedora do Recanto das Emas (DF). A empresa coleta resíduos eletroeletrônicos em residências, empresas e faculdades, separa os componentes (vidro, plásticos, cobre, alumínio, placas) e encaminha para parceiros de reciclagem e fabricantes. A operação é B2B2C, com foco em economia circular e engenharia reversa de eletrônicos.

O Brasil gera aproximadamente 2,4 milhões de toneladas de lixo eletrônico por ano (5º maior do mundo), com crescimento anual de ~9%. Menos de 3% recebe tratamento adequado. Uma tonelada de placas eletrônicas recicladas pode render até 800g de ouro — contra 5g na mineração convencional. A Tronik opera nesse gap entre geração massiva e reciclagem quase inexistente.

O Dashboard-TRONIK é o sistema web que monitora coletores inteligentes equipados com sensores ultrassônicos (nível de preenchimento) e bateria, conectados via ESP32. A stack é Flask + SQLAlchemy + frontend vanilla (JS ES6+, Leaflet, Chart.js), com REST API, WebSocket, Flask-Mail e APScheduler. A nova dashboard (`/preview`) já renderiza home, monitoramento, mapa, relatórios e parceiros com dados reais do banco.

A **Nik** é o agente de IA da Tronik. Ela opera em dois modos: **Nik Pública** (landing page, educação e engajamento do visitante) e **Nik Ops** (preview dashboard, interpretação operacional dos dados para a equipe). Ambas são alimentadas pela NVIDIA NIM API, usando modelos open-weight diferentes conforme o contexto.

---

## 1. Arquitetura geral

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (vanilla JS)                     │
│                                                                  │
│  /landing (pública)              /preview/* (autenticada)        │
│  ┌──────────────┐                ┌──────────────────────────┐   │
│  │ Blocos Nik   │                │ Home: resumo do dia       │   │
│  │ (pré-gerado) │                │ Mapa: análise do coletor  │   │
│  │ fetch → cache│                │ Monit: alerta em destaque │   │
│  └──────┬───────┘                │ Relat: narrativa gerada   │   │
│         │                        └────────────┬─────────────┘   │
│         │ GET /api/nik/landing/*               │                 │
│         │                      GET /api/nik/ops/*                │
└─────────┼──────────────────────────────────────┼─────────────────┘
          │                                      │
┌─────────┴──────────────────────────────────────┴─────────────────┐
│                        BACKEND (Flask)                            │
│                                                                   │
│  rotas/api/nik.py ─── nik_bp (sub-blueprint registrado em api_bp)│
│       │                                                           │
│       ├─── banco_dados/services/nik_service.py                   │
│       │         │                                                 │
│       │         ├─── nik_contexto.py  (monta {dados} do prompt)  │
│       │         │         └─── consome preview_service.py         │
│       │         │                                                 │
│       │         ├─── nik_provider.py  (chama NVIDIA NIM)         │
│       │         │         └─── openai SDK, base_url NIM          │
│       │         │                                                 │
│       │         ├─── nik_prompts.py   (system prompts, templates)│
│       │         │                                                 │
│       │         └─── nik_validacao.py (sanitiza output do modelo)│
│       │                                                           │
│       └─── banco_dados/utils/cache.py (CacheMemoria existente)   │
│                                                                   │
│  banco_dados/agendamento.py ── job: pre_gerar_conteudo_nik       │
└──────────────────────────────────────────────────────────────────┘
          │
          │ POST https://integrate.api.nvidia.com/v1/chat/completions
          │ Header: Authorization: Bearer nvapi-XXXXXXXX
          │
┌─────────┴────────────────────────────────────────────────────────┐
│                     NVIDIA NIM API (hosted)                       │
│                                                                   │
│  Nik Pública  → mistralai/ministral-14b-instruct-2512           │
│                  (14B params, 256K ctx, multilingual, JSON nativo)│
│                                                                   │
│  Nik Ops      → google/gemma-3-27b-it                            │
│                  (27B params, 128K ctx, 140+ idiomas)             │
│                                                                   │
│  Fallback     → google/gemma-3-1b-it                             │
│                  (1B params, rápido, para degradação graciosa)    │
│                                                                   │
│  Rate limit: 40 req/min (free tier)                              │
│  API key: prefixo nvapi-, env NVIDIA_API_KEY                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Modelos e justificativa

### 2.1 Ministral 3 14B (`mistralai/ministral-14b-instruct-2512`)

Usado pela **Nik Pública** na landing page. Justificativa:

- **JSON nativo:** suporta function calling e output JSON formatado sem hacks de parsing. Isso permite gerar blocos estruturados (`titulo`, `corpo`, `cta`, `fato_reciclagem`) que o frontend renderiza direto.
- **256K de contexto:** margem enorme para system prompt rico com persona da Nik + dados da Tronik + instruções de formatação.
- **Multilingual incluindo português:** treinado com dados em PT-BR, não é tradução de inglês.
- **14B parâmetros:** boa relação qualidade/velocidade para geração de conteúdo educativo pré-cacheado.

### 2.2 Gemma 3 27B (`google/gemma-3-27b-it`)

Usado pela **Nik Ops** na preview. Justificativa:

- **128K de contexto:** suficiente para receber o dump completo de um coletor + histórico + stats gerais num único prompt.
- **Raciocínio superior ao Ministral** em tarefas analíticas — benchmarks mostram vantagem em MMLU, GPQA Diamond e tarefas de reasoning.
- **Multimodal (text + image → text):** abre possibilidade futura de a Nik analisar fotos dos coletores via sensor/câmera.
- **Open weights, licença permissiva:** pode migrar para self-hosted NIM se o free tier estourar.

### 2.3 Gemma 3 1B (`google/gemma-3-1b-it`)

**Fallback exclusivo.** Se o 27B retornar erro 429 (rate limit) ou timeout, o sistema tenta o 1B antes de cair no fallback estático. O 1B é rápido o suficiente para gerar um resumo simples em <1s.

### 2.4 Migração futura

Se a Tronik escalar e o free tier não aguentar: os modelos NIM rodam em containers Docker com a mesma API. O `nik_provider.py` já abstrai o `base_url` — basta apontar para um NIM self-hosted sem mudar o resto do código.

---

## 3. Novos arquivos e onde moram

```
banco_dados/
  services/
    nik_service.py          # orquestrador: cache → contexto → provider → validação → resposta
    nik_contexto.py         # monta dicts de contexto consumindo preview_service.py
    nik_provider.py         # abstrai chamada à NVIDIA NIM (openai SDK)
    nik_prompts.py          # system prompts, templates Jinja2 para prompts, persona da Nik
    nik_validacao.py        # sanitiza, trunca, verifica output do modelo antes de servir

rotas/
  api/
    nik.py                  # blueprint Flask com endpoints da Nik

templates/
  preview/
    _partials/
      _nik_ops_bloco.html   # componente HTML do bloco Nik Ops (mapa, home, monit)
  landing/
    landing.html            # página pública com blocos da Nik
    _partials/
      _nik_bloco.html       # componente HTML de um bloco Nik na landing

estatico/
  js/
    v2/
      nik-loader.js         # JS que faz fetch assíncrono dos endpoints Nik e renderiza
  css/
    v2/
      nik.css               # estilos dos blocos Nik (ambos os contextos)
```

### 3.1 Registro do blueprint

Em `rotas/api/__init__.py`, adicionar:

```python
from rotas.api import nik

# Nik (agente IA)
api_bp.register_blueprint(nik.nik_bp)
```

### 3.2 Registro da rota da landing

Em `rotas/paginas.py`, adicionar:

```python
@paginas_bp.route('/landing')
def landing():
    """Landing page pública com blocos Nik."""
    return render_template('landing/landing.html')
```

### 3.3 Ajustes de aderência ao repositório atual

- A integração da **Nik Ops** no MVP deve acontecer via `fetch` assíncrono nos templates existentes de `templates/preview/*.html`, sem substituir a arquitetura do `preview_bp`.
- O CSS da Nik deve seguir o padrão já usado no preview v2, em `estatico/css/v2/nik.css`.
- Os endpoints de Nik Ops são parte da API e **não herdam autenticação automaticamente** do `preview_bp`; a proteção deve ser explícita nos endpoints.
- O documento `nik_bot/plano_nik.md` não foi encontrado no repositório analisado; esta spec passa a ser a fonte principal de implementação até existir um plano derivado versionado.

---

## 4. Variáveis de ambiente

```bash
# NVIDIA NIM
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NIK_MODELO_OPS=google/gemma-3-27b-it
NIK_MODELO_LANDING=mistralai/ministral-14b-instruct-2512
NIK_MODELO_FALLBACK=google/gemma-3-1b-it
NIK_API_BASE_URL=https://integrate.api.nvidia.com/v1

# Comportamento
NIK_ENABLED=true
NIK_CACHE_TTL_LANDING=3600        # 1h para conteúdo educativo
NIK_CACHE_TTL_RESUMO_OPS=1800     # 30min para resumo operacional
NIK_CACHE_TTL_COLETOR_OPS=600     # 10min para análise de coletor individual
NIK_CACHE_TTL_RELATORIO_OPS=3600  # 1h para narrativa de relatório
NIK_MAX_TOKENS_OPS=512            # limite de output para Nik Ops
NIK_MAX_TOKENS_LANDING=384        # limite de output para Nik Pública
NIK_TEMPERATURE_OPS=0.3           # baixa, analítico
NIK_TEMPERATURE_LANDING=0.7       # mais criativa, engajamento
NIK_PRE_GERACAO_ENABLED=true
NIK_PRE_GERACAO_INTERVALO_MIN=60  # a cada 1h, gera conteúdo da landing
```

---

## 5. Camada de provider (`nik_provider.py`)

```python
"""
Abstração da chamada à NVIDIA NIM.
Usa openai SDK com base_url customizado.
Não importa nenhuma dependência além de openai e os tipos padrão.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class NikResposta:
    texto: str
    modelo_usado: str
    tokens_prompt: int
    tokens_resposta: int
    sucesso: bool
    erro: Optional[str] = None


def _cliente() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("NIK_API_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=os.getenv("NVIDIA_API_KEY", ""),
    )


def chamar_modelo(
    system_prompt: str,
    user_prompt: str,
    modelo: Optional[str] = None,
    max_tokens: int = 512,
    temperature: float = 0.3,
    response_format: Optional[dict] = None,
) -> NikResposta:
    """
    Chama um modelo via NVIDIA NIM.
    Se o modelo principal falhar, tenta o fallback.
    Nunca levanta exceção — retorna NikResposta com sucesso=False.
    """
    modelo_principal = modelo or os.getenv("NIK_MODELO_OPS", "google/gemma-3-27b-it")
    modelo_fallback = os.getenv("NIK_MODELO_FALLBACK", "google/gemma-3-1b-it")

    for tentativa_modelo in [modelo_principal, modelo_fallback]:
        try:
            client = _cliente()
            kwargs = {
                "model": tentativa_modelo,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format

            resp = client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            return NikResposta(
                texto=choice.message.content or "",
                modelo_usado=tentativa_modelo,
                tokens_prompt=resp.usage.prompt_tokens if resp.usage else 0,
                tokens_resposta=resp.usage.completion_tokens if resp.usage else 0,
                sucesso=True,
            )
        except Exception as e:
            logger.warning(
                "NIM falhou para %s: %s — tentando fallback", tentativa_modelo, e
            )
            continue

    return NikResposta(
        texto="",
        modelo_usado="nenhum",
        tokens_prompt=0,
        tokens_resposta=0,
        sucesso=False,
        erro="Todos os modelos falharam",
    )
```

**Dependência:** adicionar `openai>=1.0.0` ao `requirements.txt`. O SDK `openai` funciona com qualquer API OpenAI-compatible — basta trocar `base_url`.

---

## 6. Camada de contexto (`nik_contexto.py`)

Esta camada consome `preview_service.py` e monta dicts que serão injetados nos prompts. Ela **nunca** chama o modelo — só prepara dados.

```python
"""
Monta contextos estruturados para os prompts da Nik.
Consome preview_service.py e retorna dicts puros (não JSON strings).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from banco_dados.services import preview_service as pv


def contexto_resumo_operacional(db: Session) -> Dict[str, Any]:
    """Contexto para o resumo do dia (home da preview)."""
    stats = pv.estatisticas_resumo(db)
    coletores = pv.coletores_monitoramento(db)
    alerta = pv.primeiro_alerta_critico(coletores)
    nomes_atencao = pv.nomes_coletores_atencao(coletores)
    recentes = pv.coletas_recentes(db, 5)

    return {
        "data": pv.data_longa_pt(),
        "total_coletores": stats["total_coletores"],
        "alertas_ativos": stats["alertas_ativos"],
        "criticos": stats["criticos"],
        "nivel_medio": stats["nivel_medio"],
        "coletas_hoje": stats["coletas_hoje"],
        "sensores_bateria_baixa": stats["sensores_bateria_baixa"],
        "coletores_atencao": nomes_atencao[:4],
        "alerta_destaque": alerta,
        "ultimas_coletas": [
            {
                "local": c["local"],
                "parceiro": c["parceiro"],
                "volume": c["volume"],
                "data": c["data_fmt"],
            }
            for c in recentes
        ],
    }


def contexto_coletor(db: Session, coletor_id: int) -> Optional[Dict[str, Any]]:
    """Contexto para análise de um coletor específico (mapa)."""
    detalhe = pv.detalhe_coletor_mapa(db, coletor_id)
    if not detalhe:
        return None

    stats = pv.estatisticas_resumo(db)

    return {
        "coletor": {
            "id_fmt": detalhe["id_fmt"],
            "nome": detalhe["nome"],
            "nivel": detalhe["nivel"],
            "classe": detalhe["classe"],
            "badge": detalhe["badge"],
            "parceiro": detalhe["parceiro"],
            "tipo_material": detalhe["tipo"],
            "bateria": detalhe["bateria"],
            "ultima_coleta": detalhe["ultima_coleta"],
            "lat": detalhe["lat"],
            "lng": detalhe["lng"],
        },
        "contexto_geral": {
            "total_coletores": stats["total_coletores"],
            "nivel_medio": stats["nivel_medio"],
            "alertas_ativos": stats["alertas_ativos"],
        },
    }


def contexto_alerta_destaque(db: Session) -> Optional[Dict[str, Any]]:
    """Contexto para explicar o alerta principal (monitoramento)."""
    coletores = pv.coletores_monitoramento(db)
    alerta = pv.primeiro_alerta_critico(coletores)
    if not alerta:
        return None

    detalhe = pv.detalhe_coletor_mapa(db, alerta["id"])
    stats = pv.estatisticas_resumo(db)

    return {
        "alerta": alerta,
        "coletor_detalhe": detalhe,
        "contexto_geral": {
            "total_coletores": stats["total_coletores"],
            "nivel_medio": stats["nivel_medio"],
            "coletas_hoje": stats["coletas_hoje"],
        },
    }


def contexto_relatorio(
    db: Session, inicio: str, fim: str, parceiro_id: Optional[int] = None
) -> Dict[str, Any]:
    """Contexto para narrativa de relatório."""
    periodo = pv.resolver_periodo(inicio, fim)
    resumo = pv.resumo_relatorios(db, periodo, parceiro_id=parceiro_id)

    return {
        "periodo": {
            "inicio": periodo.inicio.isoformat(),
            "fim": periodo.fim.isoformat(),
        },
        "total_coletas": resumo["total_coletas"],
        "volume_kg": resumo["volume_kg"],
        "km_total": resumo["km_total"],
        "lucro_bruto": resumo["lucro_bruto"],
        "custo_combustivel_est": resumo["custo_combustivel_est"],
        "media_kg_coleta": resumo["media_kg_coleta"],
        "media_km_coleta": resumo["media_km_coleta"],
        "top_coletores": resumo["top_coletores"][:5],
        "volume_por_parceiro": resumo["volume_por_parceiro"][:6],
    }


def contexto_landing() -> Dict[str, Any]:
    """Contexto estático para geração de conteúdo da landing."""
    return {
        "empresa": "Tronik Recicla",
        "fundadora": "Maiara Gualberto",
        "local": "Recanto das Emas, Brasília-DF",
        "missao": (
            "Coletar resíduos eletroeletrônicos em residências, empresas e "
            "faculdades, separar componentes e encaminhar para reciclagem, "
            "promovendo economia circular e engenharia reversa."
        ),
        "dados_setor": {
            "brasil_toneladas_ano": "2.4 milhões",
            "reciclagem_percentual": "menos de 3%",
            "ranking_mundial": "5º maior gerador",
            "crescimento_anual": "~9%",
            "ouro_por_tonelada_placas": "até 800g (vs 5g na mineração)",
        },
        "publico": "Residências, empresas, faculdades, universidades",
        "impacto": "Ambiental (redução de e-waste) e social (inclusão de catadores)",
    }
```

---

## 7. Prompt engineering (`nik_prompts.py`)

Este é o arquivo mais crítico do projeto. Ele define **quem a Nik é** e **como ela fala**.

```python
"""
System prompts e templates de prompt para a Nik.
Todos os prompts são strings Python puras com placeholders {}.
O tom, persona e limites da Nik moram aqui — não em endpoints.
"""

from __future__ import annotations

import json
from typing import Any, Dict

# ─────────────────────────────────────────────────────────────────
# PERSONA BASE (compartilhada entre Nik Pública e Nik Ops)
# ─────────────────────────────────────────────────────────────────

_PERSONA_BASE = """\
Você é a Nik, assistente de inteligência artificial da Tronik Recicla.

Sobre a Tronik:
- Startup de impacto socioambiental fundada por Maiara Gualberto no Recanto das Emas, Brasília-DF.
- Coleta resíduos eletroeletrônicos em residências, empresas e faculdades.
- Separa componentes (vidro, plástico, cobre, alumínio, placas) e encaminha para reciclagem.
- Opera na economia circular: engenharia reversa de eletrônicos.
- Modelo B2B2C com foco em ESG e educação ambiental.

Sobre o setor:
- O Brasil gera ~2,4 milhões de toneladas de lixo eletrônico por ano (5º mundial).
- Menos de 3% é reciclado adequadamente.
- Uma tonelada de placas eletrônicas rende até 800g de ouro (vs 5g na mineração convencional).
- Crescimento anual de ~9% na geração de e-waste.

Seu tom:
- Direto, sem rodeios, mas acolhedor.
- Usa linguagem simples e acessível — evita jargão técnico desnecessário.
- Confiante sem ser arrogante.
- Fala em português brasileiro natural, não em "tradução de inglês".
- Nunca usa emojis excessivos. No máximo um por bloco, se fizer sentido.
- Nunca inventa dados. Se não tem informação, diz que não tem.
"""

# ─────────────────────────────────────────────────────────────────
# NIK OPS — System prompts por contexto
# ─────────────────────────────────────────────────────────────────

SYSTEM_OPS_RESUMO = (
    _PERSONA_BASE
    + """
Contexto: você está na dashboard operacional da Tronik, na tela inicial (home).
Sua tarefa: gerar um resumo executivo do dia para o operador.

Regras:
1. Máximo 4 frases. Seja conciso.
2. Comece pelo dado mais crítico (alertas > nível médio > coletas).
3. Se houver coletor em estado crítico (≥95%), destaque pelo nome.
4. Se houver sensor com bateria baixa (<20%), mencione.
5. Feche com uma orientação prática (o que fazer primeiro).
6. Nunca liste todos os coletores — destaque os 2-3 mais relevantes.
7. Use o nome do coletor (campo "nome"), não o ID técnico.
"""
)

SYSTEM_OPS_COLETOR = (
    _PERSONA_BASE
    + """
Contexto: o operador selecionou um coletor no mapa e quer entender a situação.
Sua tarefa: analisar os dados deste coletor e dar uma leitura operacional.

Estruture sua resposta em exatamente 4 partes:
1. **O que estou vendo** — descreva o estado atual em 1 frase.
2. **O que isso significa** — interprete o nível, bateria e última coleta em 1-2 frases.
3. **Dados usados** — liste os 3-4 dados principais que baseiam sua análise.
4. **Ação sugerida** — 1 recomendação prática e específica.

Regras:
- Compare o nível do coletor com a média geral para dar perspectiva.
- Se o nível está ≥95% (crítico), a ação é urgente.
- Se o nível está entre 80-94% (atenção), a ação é planejamento de coleta.
- Se o nível está <80% (normal), destaque que está sob controle.
- Se a bateria está abaixo de 20%, mencione risco de perda de monitoramento.
- Se a última coleta foi há mais de 30 dias, sinalize.
"""
)

SYSTEM_OPS_ALERTA = (
    _PERSONA_BASE
    + """
Contexto: o operador está na tela de monitoramento e existe um alerta crítico.
Sua tarefa: explicar o alerta de destaque de forma clara e acionável.

Regras:
1. Máximo 3 frases.
2. Nomeie o coletor em alerta.
3. Diga o nível atual e compare com o limiar (95% = crítico, 80% = atenção).
4. Sugira uma ação imediata.
5. Se houver coletas recentes no mesmo coletor, mencione a frequência.
"""
)

SYSTEM_OPS_RELATORIO = (
    _PERSONA_BASE
    + """
Contexto: o operador está visualizando relatórios do período.
Sua tarefa: gerar uma narrativa analítica dos dados consolidados.

Regras:
1. Máximo 6 frases.
2. Comece com o volume total e número de coletas — é o dado principal.
3. Destaque o top coletor e o parceiro com maior volume.
4. Mencione o lucro bruto estimado e custo de combustível se disponíveis.
5. Compare a média de kg por coleta com referências (ex: "acima/abaixo da média anterior").
6. Feche com uma observação estratégica (tendência, sazonalidade, oportunidade).
7. Se o período for curto (<7 dias), cuidado com generalizações.
"""
)

# ─────────────────────────────────────────────────────────────────
# NIK PÚBLICA — System prompt para landing
# ─────────────────────────────────────────────────────────────────

SYSTEM_LANDING = (
    _PERSONA_BASE
    + """
Contexto: você está na landing page pública da Tronik, falando com visitantes.
Sua tarefa: gerar conteúdo educativo e engajador sobre e-waste e a Tronik.

O visitante pode ser: um potencial cliente (empresa com eletrônicos para descartar),
um estudante pesquisando sobre reciclagem, ou alguém curioso sobre sustentabilidade.

Você vai receber um tipo de bloco para gerar. Responda APENAS com JSON válido
no formato especificado. Sem texto antes ou depois do JSON.

Tipos de bloco:

1. "fala_nik" → {"titulo": "...", "corpo": "...", "destaque": "..."}
   Uma fala curta e impactante da Nik sobre e-waste. Máx 2 frases no corpo.

2. "fato_reciclagem" → {"fato": "...", "fonte": "..."}
   Um fato surpreendente sobre reciclagem de eletrônicos com fonte.

3. "impacto_tronik" → {"titulo": "...", "metrica": "...", "explicacao": "..."}
   Um dado de impacto da Tronik (pode ser estimado/hipotético se baseado nos dados do setor).

4. "pergunta_guiada" → {"pergunta": "...", "resposta_curta": "..."}
   Uma pergunta que o visitante teria, com resposta direta.

5. "nik_explica" → {"titulo": "...", "corpo": "...", "analogia": "..."}
   Explicação de um conceito (economia circular, logística reversa, etc) com analogia.
"""
)


# ─────────────────────────────────────────────────────────────────
# Funções de montagem de user prompts
# ─────────────────────────────────────────────────────────────────


def montar_prompt_ops_resumo(contexto: Dict[str, Any]) -> str:
    return f"Dados operacionais de hoje:\n\n{json.dumps(contexto, ensure_ascii=False, indent=2)}"


def montar_prompt_ops_coletor(contexto: Dict[str, Any]) -> str:
    return f"Dados do coletor selecionado e contexto geral:\n\n{json.dumps(contexto, ensure_ascii=False, indent=2)}"


def montar_prompt_ops_alerta(contexto: Dict[str, Any]) -> str:
    return f"Dados do alerta de destaque:\n\n{json.dumps(contexto, ensure_ascii=False, indent=2)}"


def montar_prompt_ops_relatorio(contexto: Dict[str, Any]) -> str:
    return f"Dados consolidados do período:\n\n{json.dumps(contexto, ensure_ascii=False, indent=2)}"


def montar_prompt_landing(tipo_bloco: str, contexto: Dict[str, Any]) -> str:
    return (
        f"Gere um bloco do tipo '{tipo_bloco}' para a landing page.\n\n"
        f"Contexto da empresa:\n{json.dumps(contexto, ensure_ascii=False, indent=2)}\n\n"
        f"Responda APENAS com o JSON no formato especificado para '{tipo_bloco}'."
    )
```

---

## 8. Validação de output (`nik_validacao.py`)

```python
"""
Sanitiza e valida o output do modelo antes de servir ao frontend.
O modelo pode gerar lixo, HTML malicioso, ou texto fora do esperado.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


def sanitizar_texto(texto: str, max_chars: int = 2000) -> str:
    """Remove tags HTML, trunca, e limpa whitespace excessivo."""
    limpo = re.sub(r"<[^>]+>", "", texto)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) > max_chars:
        limpo = limpo[:max_chars].rsplit(" ", 1)[0] + "…"
    return limpo


def extrair_json_do_output(texto: str) -> Optional[Dict[str, Any]]:
    """
    Tenta extrair JSON válido do output do modelo.
    O modelo pode retornar ```json ... ``` ou JSON puro.
    """
    texto = texto.strip()

    # Remove code fences
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # Tenta encontrar o primeiro { ... } no texto
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def validar_resposta_ops(texto: str) -> str:
    """Valida resposta da Nik Ops. Retorna texto sanitizado ou fallback."""
    limpo = sanitizar_texto(texto, max_chars=1500)
    if len(limpo) < 20:
        return "Não foi possível gerar uma análise neste momento. Os dados do coletor estão disponíveis no painel."
    return limpo


def validar_resposta_landing(texto: str, tipo_bloco: str) -> Optional[Dict[str, Any]]:
    """Valida resposta da Nik Pública. Retorna dict ou None."""
    parsed = extrair_json_do_output(texto)
    if not parsed:
        return None

    # Verifica campos mínimos por tipo
    campos_obrigatorios = {
        "fala_nik": ["titulo", "corpo"],
        "fato_reciclagem": ["fato"],
        "impacto_tronik": ["titulo", "metrica"],
        "pergunta_guiada": ["pergunta", "resposta_curta"],
        "nik_explica": ["titulo", "corpo"],
    }

    obrigatorios = campos_obrigatorios.get(tipo_bloco, [])
    for campo in obrigatorios:
        if campo not in parsed or not parsed[campo]:
            return None

    # Sanitiza cada valor string
    for k, v in parsed.items():
        if isinstance(v, str):
            parsed[k] = sanitizar_texto(v, max_chars=500)

    return parsed
```

---

## 9. Orquestrador (`nik_service.py`)

```python
"""
Orquestrador central da Nik.
Decide: cache → contexto → provider → validação → resposta.
Nunca chama o modelo direto — delega para nik_provider.
Nunca monta prompt direto — delega para nik_prompts.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from banco_dados.services import nik_contexto as ctx
from banco_dados.services import nik_prompts as prompts
from banco_dados.services import nik_provider as provider
from banco_dados.services import nik_validacao as val
from banco_dados.utils.cache import obter_cache

logger = logging.getLogger(__name__)


def _nik_habilitada() -> bool:
    return os.getenv("NIK_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _ttl(env_key: str, default: int) -> int:
    return int(os.getenv(env_key, str(default)))


# ─── Fallbacks estáticos ───────────────────────────────────────


_FALLBACK_RESUMO = (
    "Dados operacionais carregados. "
    "Consulte o monitoramento para detalhes dos coletores em alerta."
)

_FALLBACK_COLETOR = (
    "Dados do coletor disponíveis no painel ao lado. "
    "A análise automática não está disponível no momento."
)

_FALLBACK_ALERTA = (
    "Existe um alerta ativo. Confira os detalhes no card de monitoramento."
)

_FALLBACK_RELATORIO = (
    "Os dados do período estão consolidados acima. "
    "A narrativa automática não está disponível no momento."
)


# ─── Endpoints operacionais (Nik Ops) ─────────────────────────


def resumo_operacional(db: Session) -> Dict[str, Any]:
    """Resumo do dia para a home da preview."""
    if not _nik_habilitada():
        return {"texto": _FALLBACK_RESUMO, "fonte": "fallback", "modelo": "nenhum"}

    cache = obter_cache()
    chave = "nik:ops:resumo"
    ttl = _ttl("NIK_CACHE_TTL_RESUMO_OPS", 1800)

    cached = cache.obter(chave, ttl)
    if cached:
        return cached

    contexto = ctx.contexto_resumo_operacional(db)
    resposta = provider.chamar_modelo(
        system_prompt=prompts.SYSTEM_OPS_RESUMO,
        user_prompt=prompts.montar_prompt_ops_resumo(contexto),
        modelo=os.getenv("NIK_MODELO_OPS"),
        max_tokens=int(os.getenv("NIK_MAX_TOKENS_OPS", "512")),
        temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
    )

    if resposta.sucesso:
        texto = val.validar_resposta_ops(resposta.texto)
    else:
        texto = _FALLBACK_RESUMO

    resultado = {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso else "fallback",
        "modelo": resposta.modelo_usado,
    }
    cache.definir(chave, resultado)
    return resultado


def analise_coletor(db: Session, coletor_id: int) -> Dict[str, Any]:
    """Análise de um coletor específico para o mapa."""
    if not _nik_habilitada():
        return {"texto": _FALLBACK_COLETOR, "fonte": "fallback", "modelo": "nenhum"}

    cache = obter_cache()
    chave = f"nik:ops:coletor:{coletor_id}"
    ttl = _ttl("NIK_CACHE_TTL_COLETOR_OPS", 600)

    cached = cache.obter(chave, ttl)
    if cached:
        return cached

    contexto = ctx.contexto_coletor(db, coletor_id)
    if not contexto:
        return {"texto": "Coletor não encontrado.", "fonte": "erro", "modelo": "nenhum"}

    resposta = provider.chamar_modelo(
        system_prompt=prompts.SYSTEM_OPS_COLETOR,
        user_prompt=prompts.montar_prompt_ops_coletor(contexto),
        modelo=os.getenv("NIK_MODELO_OPS"),
        max_tokens=int(os.getenv("NIK_MAX_TOKENS_OPS", "512")),
        temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
    )

    if resposta.sucesso:
        texto = val.validar_resposta_ops(resposta.texto)
    else:
        texto = _FALLBACK_COLETOR

    resultado = {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso else "fallback",
        "modelo": resposta.modelo_usado,
    }
    cache.definir(chave, resultado)
    return resultado


def analise_alerta(db: Session) -> Dict[str, Any]:
    """Explicação do alerta de destaque para monitoramento."""
    if not _nik_habilitada():
        return {"texto": _FALLBACK_ALERTA, "fonte": "fallback", "modelo": "nenhum"}

    cache = obter_cache()
    chave = "nik:ops:alerta"
    ttl = _ttl("NIK_CACHE_TTL_RESUMO_OPS", 1800)

    cached = cache.obter(chave, ttl)
    if cached:
        return cached

    contexto = ctx.contexto_alerta_destaque(db)
    if not contexto:
        return {"texto": "Nenhum alerta ativo no momento.", "fonte": "dados", "modelo": "nenhum"}

    resposta = provider.chamar_modelo(
        system_prompt=prompts.SYSTEM_OPS_ALERTA,
        user_prompt=prompts.montar_prompt_ops_alerta(contexto),
        modelo=os.getenv("NIK_MODELO_OPS"),
        max_tokens=int(os.getenv("NIK_MAX_TOKENS_OPS", "512")),
        temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
    )

    if resposta.sucesso:
        texto = val.validar_resposta_ops(resposta.texto)
    else:
        texto = _FALLBACK_ALERTA

    resultado = {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso else "fallback",
        "modelo": resposta.modelo_usado,
    }
    cache.definir(chave, resultado)
    return resultado


def narrativa_relatorio(
    db: Session, inicio: str, fim: str, parceiro_id: Optional[int] = None
) -> Dict[str, Any]:
    """Narrativa gerada para a tela de relatórios."""
    if not _nik_habilitada():
        return {"texto": _FALLBACK_RELATORIO, "fonte": "fallback", "modelo": "nenhum"}

    cache = obter_cache()
    chave = f"nik:ops:relatorio:{inicio}:{fim}:{parceiro_id or 'all'}"
    ttl = _ttl("NIK_CACHE_TTL_RELATORIO_OPS", 3600)

    cached = cache.obter(chave, ttl)
    if cached:
        return cached

    contexto = ctx.contexto_relatorio(db, inicio, fim, parceiro_id)
    resposta = provider.chamar_modelo(
        system_prompt=prompts.SYSTEM_OPS_RELATORIO,
        user_prompt=prompts.montar_prompt_ops_relatorio(contexto),
        modelo=os.getenv("NIK_MODELO_OPS"),
        max_tokens=int(os.getenv("NIK_MAX_TOKENS_OPS", "512")),
        temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
    )

    if resposta.sucesso:
        texto = val.validar_resposta_ops(resposta.texto)
    else:
        texto = _FALLBACK_RELATORIO

    resultado = {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso else "fallback",
        "modelo": resposta.modelo_usado,
    }
    cache.definir(chave, resultado)
    return resultado


# ─── Landing (Nik Pública) ────────────────────────────────────


def gerar_bloco_landing(tipo_bloco: str) -> Dict[str, Any]:
    """Gera um bloco de conteúdo para a landing page."""
    if not _nik_habilitada():
        return {"bloco": None, "fonte": "desabilitada"}

    cache = obter_cache()
    chave = f"nik:landing:{tipo_bloco}"
    ttl = _ttl("NIK_CACHE_TTL_LANDING", 3600)

    cached = cache.obter(chave, ttl)
    if cached:
        return cached

    contexto = ctx.contexto_landing()
    resposta = provider.chamar_modelo(
        system_prompt=prompts.SYSTEM_LANDING,
        user_prompt=prompts.montar_prompt_landing(tipo_bloco, contexto),
        modelo=os.getenv("NIK_MODELO_LANDING", "mistralai/ministral-14b-instruct-2512"),
        max_tokens=int(os.getenv("NIK_MAX_TOKENS_LANDING", "384")),
        temperature=float(os.getenv("NIK_TEMPERATURE_LANDING", "0.7")),
    )

    if resposta.sucesso:
        bloco = val.validar_resposta_landing(resposta.texto, tipo_bloco)
    else:
        bloco = None

    resultado = {
        "bloco": bloco,
        "fonte": "modelo" if bloco else "fallback",
        "modelo": resposta.modelo_usado,
    }
    if bloco:
        cache.definir(chave, resultado)
    return resultado
```

---

## 10. Endpoints REST (`rotas/api/nik.py`)

```python
"""
Blueprint da API Nik.
Registrado como sub-blueprint de api_bp em rotas/api/__init__.py.
Todos os endpoints retornam JSON.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from banco_dados.services import nik_service as nik
from rotas.api.decorators import get_db

nik_bp = Blueprint("nik", __name__, url_prefix="/nik")


# ─── Nik Ops (preview, autenticada) ───────────────────────────


@nik_bp.route("/ops/resumo")
@login_required
def ops_resumo():
    """GET /api/nik/ops/resumo — resumo operacional do dia."""
    db = get_db()
    try:
        return jsonify(nik.resumo_operacional(db))
    finally:
        db.close()


@nik_bp.route("/ops/coletor/<int:coletor_id>")
@login_required
def ops_coletor(coletor_id: int):
    """GET /api/nik/ops/coletor/<id> — análise de coletor individual."""
    db = get_db()
    try:
        return jsonify(nik.analise_coletor(db, coletor_id))
    finally:
        db.close()


@nik_bp.route("/ops/alerta")
@login_required
def ops_alerta():
    """GET /api/nik/ops/alerta — explicação do alerta de destaque."""
    db = get_db()
    try:
        return jsonify(nik.analise_alerta(db))
    finally:
        db.close()


@nik_bp.route("/ops/relatorio")
@login_required
def ops_relatorio():
    """GET /api/nik/ops/relatorio?inicio=...&fim=...&parceiro_id=..."""
    inicio = request.args.get("inicio", "")
    fim = request.args.get("fim", "")
    parceiro_id = request.args.get("parceiro_id", type=int)
    db = get_db()
    try:
        return jsonify(nik.narrativa_relatorio(db, inicio, fim, parceiro_id))
    finally:
        db.close()


# ─── Nik Pública (landing, sem auth) ──────────────────────────


@nik_bp.route("/landing/<tipo_bloco>")
def landing_bloco(tipo_bloco: str):
    """GET /api/nik/landing/<tipo> — bloco de conteúdo para landing."""
    tipos_validos = {"fala_nik", "fato_reciclagem", "impacto_tronik", "pergunta_guiada", "nik_explica"}
    if tipo_bloco not in tipos_validos:
        return jsonify({"erro": f"Tipo inválido. Válidos: {sorted(tipos_validos)}"}), 400
    return jsonify(nik.gerar_bloco_landing(tipo_bloco))
```

---

## 11. Pré-geração agendada

Adicionar ao `banco_dados/agendamento.py`:

```python
def pre_gerar_nik_job():
    """
    Job agendado: pré-gera conteúdo da landing e resumo ops.
    Roda em background, popula o cache para que requests não esperem o modelo.
    """
    try:
        logger.info("🤖 Nik: iniciando pré-geração de conteúdo...")

        database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
        engine = create_engine(database_url, echo=False)
        SessionLocal = sessionmaker(bind=engine)

        # Landing: gera todos os tipos de bloco
        from banco_dados.services import nik_service as nik
        tipos_landing = ["fala_nik", "fato_reciclagem", "impacto_tronik", "pergunta_guiada", "nik_explica"]
        for tipo in tipos_landing:
            resultado = nik.gerar_bloco_landing(tipo)
            logger.info("  Landing [%s]: %s", tipo, resultado.get("fonte", "?"))

        # Ops: gera resumo do dia
        db = SessionLocal()
        try:
            resultado = nik.resumo_operacional(db)
            logger.info("  Ops resumo: %s", resultado.get("fonte", "?"))

            resultado = nik.analise_alerta(db)
            logger.info("  Ops alerta: %s", resultado.get("fonte", "?"))
        finally:
            db.close()

        logger.info("✅ Nik: pré-geração concluída")
    except Exception as e:
        logger.error("❌ Nik: erro na pré-geração: %s", e, exc_info=True)
```

E na `inicializar_agendamento()`, adicionar o job:

```python
nik_enabled = os.getenv('NIK_PRE_GERACAO_ENABLED', 'false').lower() == 'true'
if nik_enabled:
    nik_intervalo = int(os.getenv('NIK_PRE_GERACAO_INTERVALO_MIN', '60'))
    scheduler.add_job(
        func=pre_gerar_nik_job,
        trigger=IntervalTrigger(minutes=nik_intervalo),
        id='pre_gerar_nik',
        name='Pré-gerar conteúdo Nik',
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"   Nik pré-geração: a cada {nik_intervalo} minutos")
```

---

## 12. Frontend: fluxo de carregamento (`nik-loader.js`)

```javascript
/**
 * nik-loader.js
 * Carrega blocos da Nik via fetch assíncrono.
 * A página renderiza normalmente; a Nik aparece depois, sem bloquear.
 */

(function () {
  "use strict";

  const NIK_API = "/api/nik";

  /**
   * Carrega um bloco Nik Ops e insere no container especificado.
   * @param {string} endpoint - ex: "/ops/resumo", "/ops/coletor/42"
   * @param {string} containerId - id do elemento HTML onde inserir
   * @param {object} opts - { fallbackText, showLoader }
   */
  async function carregarNikOps(endpoint, containerId, opts = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const { fallbackText = "", showLoader = true } = opts;

    if (showLoader) {
      container.innerHTML =
        '<div class="nik-loading"><span class="nik-dot"></span> Nik analisando…</div>';
    }

    try {
      const resp = await fetch(NIK_API + endpoint);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();
      const texto = data.texto || fallbackText;

      container.innerHTML = `
        <div class="nik-ops-bloco">
          <div class="nik-ops-header">
            <span class="nik-avatar">N</span>
            <span class="nik-label">Nik Ops</span>
            ${data.fonte === "fallback" ? '<span class="nik-badge-fallback">offline</span>' : ""}
          </div>
          <div class="nik-ops-corpo">${escapeHtml(texto)}</div>
        </div>
      `;
    } catch (err) {
      console.warn("Nik Ops indisponível:", err);
      if (fallbackText) {
        container.innerHTML = `<div class="nik-ops-bloco nik-ops-fallback">
          <div class="nik-ops-corpo">${escapeHtml(fallbackText)}</div>
        </div>`;
      } else {
        container.innerHTML = "";
      }
    }
  }

  /**
   * Carrega bloco da Nik Pública para a landing.
   */
  async function carregarNikLanding(tipoBloco, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
      const resp = await fetch(`${NIK_API}/landing/${tipoBloco}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();
      if (!data.bloco) {
        container.style.display = "none";
        return;
      }

      renderizarBlocoLanding(container, tipoBloco, data.bloco);
    } catch (err) {
      console.warn(`Nik landing [${tipoBloco}] indisponível:`, err);
      container.style.display = "none";
    }
  }

  function renderizarBlocoLanding(container, tipo, bloco) {
    let html = "";
    switch (tipo) {
      case "fala_nik":
        html = `<h3>${esc(bloco.titulo)}</h3><p>${esc(bloco.corpo)}</p>
                ${bloco.destaque ? `<em>${esc(bloco.destaque)}</em>` : ""}`;
        break;
      case "fato_reciclagem":
        html = `<blockquote>${esc(bloco.fato)}</blockquote>
                ${bloco.fonte ? `<cite>${esc(bloco.fonte)}</cite>` : ""}`;
        break;
      case "impacto_tronik":
        html = `<h3>${esc(bloco.titulo)}</h3>
                <div class="nik-metrica">${esc(bloco.metrica)}</div>
                <p>${esc(bloco.explicacao || "")}</p>`;
        break;
      case "pergunta_guiada":
        html = `<details><summary>${esc(bloco.pergunta)}</summary>
                <p>${esc(bloco.resposta_curta)}</p></details>`;
        break;
      case "nik_explica":
        html = `<h3>${esc(bloco.titulo)}</h3><p>${esc(bloco.corpo)}</p>
                ${bloco.analogia ? `<p class="nik-analogia">${esc(bloco.analogia)}</p>` : ""}`;
        break;
    }
    container.innerHTML = `<div class="nik-landing-bloco nik-${tipo}">${html}</div>`;
  }

  function escapeHtml(str) {
    return esc(str);
  }

  function esc(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // Exporta globalmente
  window.NikLoader = { carregarNikOps, carregarNikLanding };
})();
```

---

## 13. Pontos de inserção nos templates

### 13.1 Home (`templates/preview/home.html`)

Abaixo do `<p class="home-subtitle">`:

```html
<div id="nik-ops-resumo" class="nik-container"></div>
<script>
  document.addEventListener('DOMContentLoaded', function() {
    NikLoader.carregarNikOps('/ops/resumo', 'nik-ops-resumo', {
      fallbackText: '{{ home_subtitulo }}'
    });
  });
</script>
```

### 13.2 Mapa (`templates/preview/mapa.html`)

Dentro da `div.mapa-detail`, após o último `detail-row`:

```html
{% if detalhe %}
  <div id="nik-ops-coletor" class="nik-container" style="margin-top:var(--space-3);"></div>
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      NikLoader.carregarNikOps('/ops/coletor/{{ detalhe.id }}', 'nik-ops-coletor');
    });
  </script>
{% endif %}
```

### 13.3 Monitoramento (`templates/preview/monitoramento.html`)

Junto ao bloco de alerta, quando `alerta_destaque` existe:

```html
{% if alerta_destaque %}
  <div id="nik-ops-alerta" class="nik-container"></div>
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      NikLoader.carregarNikOps('/ops/alerta', 'nik-ops-alerta');
    });
  </script>
{% endif %}
```

### 13.4 Relatórios (`templates/preview/relatorios.html`)

Após os cards de KPIs:

```html
<div id="nik-ops-relatorio" class="nik-container"></div>
<script>
  document.addEventListener('DOMContentLoaded', function() {
    var params = new URLSearchParams(window.location.search);
    var endpoint = '/ops/relatorio?' + params.toString();
    NikLoader.carregarNikOps(endpoint, 'nik-ops-relatorio');
  });
</script>
```

---

## 14. Estratégia de cache e rate limiting

### Tabela de TTLs

| Endpoint                | Chave cache                         | TTL padrão | Justificativa                              |
|-------------------------|--------------------------------------|------------|-------------------------------------------|
| `/ops/resumo`           | `nik:ops:resumo`                    | 1800s      | Dados mudam com coletas; 30min é razoável |
| `/ops/coletor/<id>`     | `nik:ops:coletor:<id>`              | 600s       | Operador pode selecionar vários; 10min    |
| `/ops/alerta`           | `nik:ops:alerta`                    | 1800s      | Mesmo ciclo do resumo                     |
| `/ops/relatorio`        | `nik:ops:relatorio:<ini>:<fim>:<p>` | 3600s      | Período fixo, dados não mudam             |
| `/landing/<tipo>`       | `nik:landing:<tipo>`                | 3600s      | Conteúdo educativo, estabilidade          |

### Budget de requisições

Com 40 req/min no free tier:

- **Landing:** 5 tipos de bloco × 1 geração/hora = 5 req/h (pré-gerado pelo scheduler)
- **Ops resumo:** 1 req a cada 30min = 2 req/h (pré-gerado ou on-demand)
- **Ops alerta:** 1 req a cada 30min = 2 req/h
- **Ops coletor:** sob demanda, mas cacheado 10min. Se 10 operadores selecionarem 10 coletores diferentes em 10min = 10 req. Pior caso plausível.
- **Ops relatório:** sob demanda, mas cacheado 1h. Baixa frequência.

**Total pior caso estimado:** ~20-30 req/h → ~0.5 req/min. Muito abaixo do limite de 40/min.

### Invalidação

O cache em memória (`CacheMemoria`) se invalida por TTL. Não existe invalidação explícita neste MVP. Se o estado do coletor mudar dramaticamente (ex: coleta realizada), o operador verá a análise anterior até o TTL expirar. Isso é aceitável para MVP.

**Fase 2 (futuro):** adicionar invalidação no endpoint de registro de coleta (`POST /api/coletas`):

```python
cache.invalidar(f"nik:ops:coletor:{coletor_id}")
cache.invalidar("nik:ops:resumo")
cache.invalidar("nik:ops:alerta")
```

---

## 15. Tratamento de erros — cascata de degradação

```
1. Cache hit?           → retorna imediato (0ms)
2. Modelo principal OK? → sanitiza, cacheia, retorna (~2-5s)
3. Modelo fallback OK?  → sanitiza, cacheia, retorna (~1-2s)
4. Tudo falhou?         → retorna texto fallback estático (0ms)
5. NIK_ENABLED=false?   → retorna fallback estático sem tentar modelo (0ms)
```

A página **nunca** espera a Nik para renderizar. O JS carrega o bloco de forma assíncrona com um spinner discreto. Se a Nik não responder em tempo, o container fica vazio ou mostra o fallback.

---

## 16. Segurança

- Os endpoints `/api/nik/ops/*` **devem usar `@login_required` já no MVP**. Eles não herdam autenticação do `preview_bp`, porque vivem em um blueprint de API separado.

- Os endpoints `/api/nik/landing/*` são públicos por design. O conteúdo é pré-gerado e cacheado — não há inferência ao vivo por request de visitante no caso normal (o scheduler pré-gera).

- O `NVIDIA_API_KEY` mora em variável de ambiente, nunca no código. O `.env` já está no `.gitignore`.

- O `nik_validacao.py` remove tags HTML do output do modelo antes de servir. O JS usa `textContent` (via `esc()`) para prevenir XSS.

- O modelo **nunca** recebe input do visitante. Na landing, os prompts são fixos. Na preview, os dados vêm do banco, não do request do operador. Isso elimina prompt injection.

---

## 17. Camada Maiara (futura)

A Maiara é uma camada restrita dentro da preview ou relatórios: um espaço que pega o resumo de relatórios já existente e gera narrativa estratégica, rascunho de relatório para stakeholders, resumo comercial ou estratégia. Não é um chat — é geração de documento.

**Escopo futuro (não neste MVP):**

- Endpoint: `GET /api/nik/maiara/relatorio?inicio=...&fim=...&formato=narrativa|executivo|comercial`
- System prompt específico com persona de analista de negócios
- Usa o mesmo Gemma 27B mas com temperature 0.2 (mais conservador)
- Output mais longo (max_tokens 1024+)
- Potencialmente gera Markdown que o frontend renderiza como mini-relatório
- Acesso restrito por role (admin/gestora)

---

## 18. Dependências a adicionar

No `requirements.txt`:

```
openai>=1.0.0
```

Nenhuma outra dependência. Não precisa de LangChain, LlamaIndex, ou frameworks pesados. O SDK `openai` faz a chamada HTTP com retry e streaming embutidos.

---

## 19. Ordem de implementação

### Sprint 1 — Fundação (3-5 dias)

1. Criar `nik_provider.py` + testar chamada raw ao NIM com API key
2. Criar `nik_prompts.py` com system prompts finalizados
3. Criar `nik_validacao.py` com testes unitários
4. Criar `nik_contexto.py` consumindo `preview_service.py`
5. Criar `nik_service.py` orquestrando tudo
6. Criar `rotas/api/nik.py` e registrar no `api_bp`
7. Testar via `curl` todos os endpoints

### Sprint 2 — Frontend Ops (2-3 dias)

1. Criar `nik-loader.js`
2. Criar `nik.css`
3. Inserir containers nos 4 templates da preview
4. Testar fluxo completo (página carrega → JS faz fetch → bloco aparece)

### Sprint 3 — Landing + Scheduler (2-3 dias)

1. Criar `templates/landing/landing.html` com estrutura de blocos
2. Adicionar rota `/landing` em `paginas.py`
3. Integrar blocos com `NikLoader.carregarNikLanding()`
4. Adicionar job `pre_gerar_nik_job` ao `agendamento.py`
5. Testar pré-geração e cache

### Sprint 4 — Refinamento (2-3 dias)

1. Ajustar prompts com base nos outputs reais do modelo
2. Calibrar temperatures e max_tokens
3. Testar degradação (desligar NIM, verificar fallbacks)
4. Testar rate limiting (muitos requests rápidos)
5. Documentar variáveis de ambiente no README

---

## 20. Testes

### Unitários (`tests/test_nik_*.py`)

- `test_nik_validacao.py` — sanitização, extração JSON, edge cases
- `test_nik_prompts.py` — verifica que prompts montados contêm os campos esperados
- `test_nik_contexto.py` — verifica que contextos retornam dicts com chaves corretas (mock do db)
- `test_nik_service.py` — verifica cascata cache → modelo → fallback (mock do provider)

### Integração

- `test_nik_api.py` — testa endpoints via test client Flask (mock do nik_service)

### Manual (checklist)

- [ ] `NIK_ENABLED=false` → todos os endpoints retornam fallback
- [ ] `NVIDIA_API_KEY` vazia → fallback gracioso, sem crash
- [ ] Free tier estourado (simular 429) → fallback funciona
- [ ] Cache hit em segundo request → resposta instantânea
- [ ] Scheduler gera conteúdo landing sem erros
- [ ] XSS test: injetar `<script>` em nome de coletor → escapa corretamente
- [ ] Preview com 0 coletores → fallback adequado
- [ ] Preview com 100+ coletores → performance OK (contexto não explode)

---

## 21. Métricas para acompanhar pós-deploy

- **Cache hit rate** por endpoint (adicionar counter no `nik_service.py`)
- **Latência média** da chamada NIM (o `NikResposta` já tem tokens, falta tempo)
- **Fallback rate** — % de respostas que caíram no fallback estático
- **Tokens consumidos** por hora (somar `tokens_prompt + tokens_resposta`)
- **Erros 429** — se começar a aparecer, precisa ajustar TTLs ou migrar para NIM pago

---
