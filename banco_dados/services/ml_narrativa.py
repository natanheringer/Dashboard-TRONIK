"""Módulo 3 — Narrativa de Impacto por IA Generativa (NLP).

Gera texto narrativo ESG personalizado por parceiro.
Chain de LLM: Groq (primário) → Ollama (fallback) → Gemini (fallback 2).
Todos gratuitos, sem custo.

Executado via APScheduler 1x/mês ou sob demanda.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import Coleta, NarrativaGerada, Parceiro
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)

# ==============================================================
# CONFIGURAÇÃO DOS PROVIDERS LLM
# ==============================================================

# Groq (primário) — free tier: 14.400 tokens/min, Llama 3.1 70B
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-70b-versatile')

# Ollama (fallback 1) — local ou cloud, zero custo
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:8b')

# Gemini (fallback 2) — Google AI, free tier generoso
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

# Timeout padrão para chamadas LLM
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '60'))

# Fator de conversão EPA WARM
CO2_FATOR = 1.44  # kgCO₂eq evitados por kg de e-waste reciclado

# Caminho do prompt template
PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / 'prompts' / 'narrativa_parceiro.txt'

# ==============================================================
# SYSTEM PROMPT
# ==============================================================

SYSTEM_PROMPT = """Você é um redator especializado em comunicação corporativa de sustentabilidade e ESG.
Sua tarefa é gerar resumos executivos mensais de impacto ambiental para parceiros de uma empresa
de coleta de resíduos eletrônicos (e-waste) chamada TRONIK Recicla, localizada em Brasília, DF.

Regras obrigatórias:
1. Responda EXCLUSIVAMENTE em português brasileiro.
2. Use tom profissional mas acessível — o leitor é um gerente, não um cientista.
3. Gere de 3 a 5 frases, totalizando 80-150 palavras.
4. Inclua PELO MENOS uma equivalência concreta (árvores, carros, energia, água).
5. TODOS os números no texto devem corresponder EXATAMENTE aos dados fornecidos.
6. NÃO invente dados que não foram fornecidos.
7. Use o nome do parceiro no texto.
8. Se houver comparativo com mês anterior, mencione crescimento ou queda.
"""


# ==============================================================
# PROVIDERS LLM
# ==============================================================

def _chamar_groq(prompt: str) -> Optional[str]:
    """Chama a API do Groq (OpenAI-compatible)."""
    if not GROQ_API_KEY:
        logger.debug("GROQ_API_KEY não configurada, pulando Groq")
        return None

    try:
        response = requests.post(
            f"{GROQ_API_BASE}/chat/completions",
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.7,
                'max_tokens': 500,
            },
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        texto = data['choices'][0]['message']['content'].strip()
        logger.info(f"✅ Groq ({GROQ_MODEL}) respondeu com {len(texto)} chars")
        return texto
    except Exception as e:
        logger.warning(f"Groq falhou: {e}")
        return None


def _chamar_ollama(prompt: str) -> Optional[str]:
    """Chama a API do Ollama (local ou remoto)."""
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                'model': OLLAMA_MODEL,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                'stream': False,
            },
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        texto = data['message']['content'].strip()
        logger.info(f"✅ Ollama ({OLLAMA_MODEL}) respondeu com {len(texto)} chars")
        return texto
    except Exception as e:
        logger.warning(f"Ollama falhou: {e}")
        return None


def _chamar_gemini(prompt: str) -> Optional[str]:
    """Chama a API do Google Gemini."""
    if not GEMINI_API_KEY:
        logger.debug("GEMINI_API_KEY não configurada, pulando Gemini")
        return None

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{
                        'text': f"{SYSTEM_PROMPT}\n\n{prompt}"
                    }]
                }],
                'generationConfig': {
                    'temperature': 0.7,
                    'maxOutputTokens': 500,
                },
            },
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        texto = data['candidates'][0]['content']['parts'][0]['text'].strip()
        logger.info(f"✅ Gemini ({GEMINI_MODEL}) respondeu com {len(texto)} chars")
        return texto
    except Exception as e:
        logger.warning(f"Gemini falhou: {e}")
        return None


def _chamar_llm_chain(prompt: str) -> tuple[Optional[str], str, str]:
    """Tenta LLMs em cadeia: Groq → Ollama → Gemini.

    Returns:
        (texto, provider, modelo) — texto é None se todos falharem
    """
    providers = [
        ('groq', GROQ_MODEL, _chamar_groq),
        ('ollama', OLLAMA_MODEL, _chamar_ollama),
        ('gemini', GEMINI_MODEL, _chamar_gemini),
    ]

    for provider_name, model_name, call_fn in providers:
        texto = call_fn(prompt)
        if texto:
            return texto, provider_name, f"{provider_name}/{model_name}"

    logger.error("❌ Todos os providers LLM falharam")
    return None, 'nenhum', 'nenhum'


# ==============================================================
# AGREGAÇÃO DE DADOS DO PARCEIRO
# ==============================================================

def _agregar_dados_parceiro(
    db: Session,
    parceiro_id: int,
    periodo_inicio: datetime,
    periodo_fim: datetime,
) -> Optional[Dict[str, Any]]:
    """Agrega dados de coleta do parceiro no período."""
    parceiro = db.query(Parceiro).filter(Parceiro.id == parceiro_id).first()
    if not parceiro:
        return None

    coletas = (
        db.query(Coleta)
        .filter(
            Coleta.parceiro_id == parceiro_id,
            Coleta.data_hora >= periodo_inicio,
            Coleta.data_hora < periodo_fim,
        )
        .all()
    )

    if not coletas:
        return None

    total_kg = sum(float(c.volume_estimado or 0) for c in coletas)
    num_coletas = len(coletas)
    co2_evitado = round(total_kg * CO2_FATOR, 1)

    # Top material (se disponível)
    materiais: Dict[str, float] = {}
    for c in coletas:
        tipo = c.tipo_coletor.nome if c.tipo_coletor else 'Geral'
        materiais[tipo] = materiais.get(tipo, 0) + float(c.volume_estimado or 0)
    top_material = max(materiais, key=materiais.get) if materiais else 'e-waste geral'

    # Comparativo mês anterior
    delta_dias = (periodo_fim - periodo_inicio).days
    anterior_inicio = periodo_inicio - timedelta(days=delta_dias)
    anterior_fim = periodo_inicio

    coletas_anterior = (
        db.query(Coleta)
        .filter(
            Coleta.parceiro_id == parceiro_id,
            Coleta.data_hora >= anterior_inicio,
            Coleta.data_hora < anterior_fim,
        )
        .all()
    )
    kg_anterior = sum(float(c.volume_estimado or 0) for c in coletas_anterior)

    if kg_anterior > 0:
        delta_percentual = round(((total_kg - kg_anterior) / kg_anterior) * 100, 1)
    else:
        delta_percentual = None  # sem dado anterior

    return {
        'parceiro_nome': parceiro.nome,
        'periodo_inicio': periodo_inicio.strftime('%d/%m/%Y'),
        'periodo_fim': periodo_fim.strftime('%d/%m/%Y'),
        'total_kg': round(total_kg, 1),
        'num_coletas': num_coletas,
        'co2_evitado': co2_evitado,
        'delta_percentual': delta_percentual,
        'top_material': top_material,
    }


# ==============================================================
# MONTAGEM DO PROMPT
# ==============================================================

def _montar_prompt(dados: Dict[str, Any]) -> str:
    """Monta prompt a partir dos dados agregados.

    Tenta usar template de arquivo, fallback para template inline.
    """
    # Tentar carregar template
    template = None
    if PROMPT_TEMPLATE_PATH.exists():
        try:
            template = PROMPT_TEMPLATE_PATH.read_text(encoding='utf-8')
        except Exception:
            pass

    if template:
        # Substituir variáveis no template
        for key, value in dados.items():
            template = template.replace(f'{{{key}}}', str(value if value is not None else 'N/D'))
        return template

    # Fallback: prompt inline
    partes = [
        f"Gere um resumo executivo de impacto ambiental para o parceiro {dados['parceiro_nome']}.",
        f"Período: {dados['periodo_inicio']} a {dados['periodo_fim']}.",
        f"Total coletado: {dados['total_kg']} kg de resíduos eletrônicos.",
        f"Número de coletas realizadas: {dados['num_coletas']}.",
        f"CO₂ evitado: {dados['co2_evitado']} kg (fator 1.44 kgCO₂/kg e-waste, fonte EPA WARM).",
    ]

    if dados.get('delta_percentual') is not None:
        if dados['delta_percentual'] > 0:
            partes.append(f"Crescimento de {dados['delta_percentual']}% em relação ao período anterior.")
        elif dados['delta_percentual'] < 0:
            partes.append(f"Queda de {abs(dados['delta_percentual'])}% em relação ao período anterior.")
        else:
            partes.append("Volume estável em relação ao período anterior.")

    partes.append(f"Principal tipo de material: {dados['top_material']}.")
    partes.append("")
    partes.append("Gere 3 a 5 frases. Inclua pelo menos uma equivalência concreta (árvores, carros, energia).")
    partes.append("Todos os números devem corresponder EXATAMENTE aos dados acima.")

    return '\n'.join(partes)


# ==============================================================
# VALIDAÇÃO PÓS-GERAÇÃO
# ==============================================================

def _validar_numeros(texto: str, dados: Dict[str, Any]) -> bool:
    """Valida se os números no texto batem com os dados de input.

    Extrai números do texto via regex e verifica se os valores-chave
    aparecem corretamente.
    """
    numeros_texto = re.findall(r'[\d.,]+', texto.replace('.', '').replace(',', '.'))

    # Verificações críticas
    total_kg_str = str(int(dados['total_kg'])) if dados['total_kg'] == int(dados['total_kg']) else str(dados['total_kg'])
    co2_str = str(int(dados['co2_evitado'])) if dados['co2_evitado'] == int(dados['co2_evitado']) else str(dados['co2_evitado'])

    # Se total_kg aparece no texto com valor diferente, rejeitar
    # Abordagem: verificar que pelo menos os valores-chave aparecem
    texto_numeros = re.sub(r'[^\d]', ' ', texto)
    kg_encontrado = str(int(dados['total_kg'])) in texto_numeros or str(dados['total_kg']) in texto
    co2_encontrado = str(int(dados['co2_evitado'])) in texto_numeros or str(dados['co2_evitado']) in texto

    if not kg_encontrado:
        logger.warning(f"Validação falhou: total_kg ({dados['total_kg']}) não encontrado no texto")
        return False

    if not co2_encontrado:
        logger.warning(f"Validação falhou: co2_evitado ({dados['co2_evitado']}) não encontrado no texto")
        return False

    return True


# ==============================================================
# API PÚBLICA
# ==============================================================

def gerar_narrativa_parceiro(
    db: Session,
    parceiro_id: int,
    periodo_inicio: Optional[datetime] = None,
    periodo_fim: Optional[datetime] = None,
    forcar_nova: bool = False,
) -> Dict[str, Any]:
    """Gera narrativa de impacto para um parceiro.

    Args:
        db: sessão SQLAlchemy
        parceiro_id: ID do parceiro
        periodo_inicio: início do período (default: 30 dias atrás)
        periodo_fim: fim do período (default: agora)
        forcar_nova: se True, ignora cache

    Returns:
        dict com texto, provider, timing, etc.
    """
    agora = utc_now_naive()

    if not periodo_fim:
        periodo_fim = agora
    if not periodo_inicio:
        periodo_inicio = periodo_fim - timedelta(days=30)

    # Verificar cache (última narrativa para este parceiro/período)
    if not forcar_nova:
        cache = (
            db.query(NarrativaGerada)
            .filter(
                NarrativaGerada.parceiro_id == parceiro_id,
                NarrativaGerada.periodo_inicio == periodo_inicio,
                NarrativaGerada.periodo_fim == periodo_fim,
            )
            .order_by(NarrativaGerada.gerado_em.desc())
            .first()
        )
        if cache:
            logger.info(f"Cache hit: narrativa para parceiro {parceiro_id}")
            result = cache.to_dict()
            result['cache'] = True
            return result

    # Agregar dados
    dados = _agregar_dados_parceiro(db, parceiro_id, periodo_inicio, periodo_fim)
    if not dados:
        return {
            'erro': 'Sem dados de coleta para este parceiro no período',
            'parceiro_id': parceiro_id,
        }

    # Montar prompt
    prompt = _montar_prompt(dados)

    # Chamar LLM com chain de fallback
    inicio_ms = time.time()
    texto, provider, modelo = _chamar_llm_chain(prompt)
    tempo_ms = int((time.time() - inicio_ms) * 1000)

    if not texto:
        return {
            'erro': 'Todos os providers LLM falharam. Verifique GROQ_API_KEY, OLLAMA_HOST ou GEMINI_API_KEY.',
            'parceiro_id': parceiro_id,
        }

    # Validar números
    validacao_ok = _validar_numeros(texto, dados)

    if not validacao_ok:
        # Retry uma vez
        logger.warning("Validação falhou, retentando com prompt mais explícito...")
        prompt_retry = prompt + "\n\nATENÇÃO: Use EXATAMENTE os números fornecidos, sem arredondar."
        texto_retry, provider, modelo = _chamar_llm_chain(prompt_retry)
        if texto_retry and _validar_numeros(texto_retry, dados):
            texto = texto_retry
            validacao_ok = True
            tempo_ms = int((time.time() - inicio_ms) * 1000)

    # Salvar no banco
    narrativa = NarrativaGerada(
        parceiro_id=parceiro_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        texto=texto,
        dados_input_json=json.dumps(dados, default=str),
        modelo_usado=modelo,
        provider_usado=provider,
        tempo_geracao_ms=tempo_ms,
        validacao_ok=validacao_ok,
        gerado_em=agora,
    )
    db.add(narrativa)
    db.commit()

    result = narrativa.to_dict()
    result['cache'] = False
    return result


def gerar_narrativas_todos_parceiros(db: Session) -> Dict[str, Any]:
    """Gera narrativas para todos os parceiros ativos.

    Chamado pelo APScheduler 1x/mês.
    """
    stats = {'processados': 0, 'sucesso': 0, 'falha': 0, 'sem_dados': 0}

    parceiros = db.query(Parceiro).filter(Parceiro.ativo.is_(True)).all()
    logger.info(f"🔄 Gerando narrativas para {len(parceiros)} parceiros...")

    for parceiro in parceiros:
        stats['processados'] += 1
        try:
            resultado = gerar_narrativa_parceiro(db, parceiro.id)
            if resultado.get('erro'):
                stats['sem_dados'] += 1
                logger.info(f"Parceiro {parceiro.nome}: {resultado['erro']}")
            else:
                stats['sucesso'] += 1
                logger.info(f"✅ Narrativa gerada para {parceiro.nome} ({resultado.get('provider_usado')})")
        except Exception as e:
            stats['falha'] += 1
            logger.error(f"Erro ao gerar narrativa para {parceiro.nome}: {e}")

    logger.info(
        f"✅ Narrativas concluídas: {stats['sucesso']} geradas, "
        f"{stats['sem_dados']} sem dados, {stats['falha']} falhas"
    )
    return stats


def obter_ultima_narrativa(
    db: Session, parceiro_id: int
) -> Optional[Dict[str, Any]]:
    """Retorna a última narrativa gerada para um parceiro."""
    narrativa = (
        db.query(NarrativaGerada)
        .filter(NarrativaGerada.parceiro_id == parceiro_id)
        .order_by(NarrativaGerada.gerado_em.desc())
        .first()
    )
    if not narrativa:
        return None
    return narrativa.to_dict()
