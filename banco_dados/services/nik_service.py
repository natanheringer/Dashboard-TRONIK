"""
Orquestrador da Nik.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import re
import secrets
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import NikConversa, NikRelatorioGerado, Parceiro
from banco_dados.services import (
    nik_agent_planner,
    nik_contexto as ctx,
    nik_prompts as prompts,
    nik_provider as provider,
    nik_tools,
    nik_validacao as val,
)
from banco_dados.utils.cache import obter_cache

logger = logging.getLogger(__name__)

_FALLBACK_RESUMO = (
    "Painel operacional carregado. Consulte os indicadores e o monitoramento para priorizar os coletores em atenção."
)
_FALLBACK_COLETOR = (
    "Os dados do coletor já estão disponíveis no painel. A análise automática não está disponível neste momento."
)
_FALLBACK_ALERTA = (
    "Existe um alerta ativo no painel. Priorize o coletor destacado e valide a rota de coleta."
)
_FALLBACK_RELATORIO = (
    "Os dados do período estão consolidados acima. A narrativa automática não está disponível neste momento."
)
_FALLBACK_MULTIMODAL_DESABILITADO = "multimodal desabilitado"
NIK_IMAGEM_MAX_BYTES = 4 * 1024 * 1024
_FALLBACK_BLOCO_LANDING: dict[str, dict[str, str]] = {
    "fala_nik": {
        "titulo": "Lixo eletrônico não desaparece sozinho",
        "corpo": "Cada equipamento descartado do jeito certo evita contaminação e devolve materiais valiosos para a cadeia produtiva.",
        "destaque": "Reciclar eletrônico é também redesenhar o futuro da cidade.",
    },
    "fato_reciclagem": {
        "fato": "Placas eletrônicas concentram metais de alto valor e mostram por que a reciclagem correta é estratégica.",
        "fonte": "Contexto setorial de reciclagem eletrônica",
    },
    "impacto_tronik": {
        "titulo": "Logística reversa com propósito",
        "metrica": "Coleta, triagem e destinação responsável em uma mesma operação",
        "explicacao": "A Tronik conecta geradores, parceiros e recicladores para transformar descarte em reaproveitamento.",
    },
    "pergunta_guiada": {
        "pergunta": "O que fazer com eletrônicos parados na empresa?",
        "resposta_curta": "Separar, registrar a origem do material e encaminhar para uma operação de coleta e destinação rastreável.",
    },
    "nik_explica": {
        "titulo": "O que é logística reversa?",
        "corpo": "É o caminho de volta do produto após o uso, para desmontagem, reaproveitamento e destinação ambientalmente correta.",
        "analogia": "Em vez de terminar no lixo comum, o equipamento entra em uma rota de retorno para voltar à cadeia produtiva.",
    },
}


def _nik_habilitada() -> bool:
    return os.getenv("NIK_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def multimodal_habilitado() -> bool:
    return provider.multimodal_habilitado()


def _ttl(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)))
    except ValueError:
        return default


def _modelo_pequeno_padrao() -> str:
    """Llama 3.1 8B Instant ou ALLaM 7B — alternativa: defina só NIK_MODELO_FALLBACK."""
    return os.getenv("NIK_MODELO_FALLBACK", "llama-3.1-8b-instant")


def _evitar_llama_70b_e_compound(modelo: str) -> str:
    """
    Compound-mini na Groq roteia para Llama 3.3 70B (TPD agressivo). Por defeito bloqueamos
    compound e qualquer modelo com '70b' no id. Escape: NIK_ALLOW_LLAMA_70B=true.
    """
    if os.getenv("NIK_ALLOW_LLAMA_70B", "").strip().lower() in {"1", "true", "yes"}:
        return modelo
    m = (modelo or "").strip()
    if not m:
        return m
    low = m.lower()
    if "compound" in low or "70b" in low:
        return _modelo_pequeno_padrao()
    return m


def _modelo_tarefa(tarefa: str, mensagem: str = "") -> str:
    """Roteação determinística de modelos por tipo de tarefa."""
    # Prioriza NIK_MODELO_OPS para manter um único "modelo base" efetivo.
    # NIK_MODELO_CHAT fica apenas como legado/fallback.
    chat_default = os.getenv("NIK_MODELO_OPS", os.getenv("NIK_MODELO_CHAT", "llama-3.1-8b-instant"))
    analytics_default = os.getenv("NIK_MODELO_ANALYTICS", os.getenv("NIK_MODELO_OPS", chat_default))
    small = _modelo_pequeno_padrao()
    relatorio_default = os.getenv("NIK_MODELO_RELATORIO", small)
    landing_default = os.getenv("NIK_MODELO_LANDING", chat_default)
    web_default = os.getenv("NIK_MODELO_WEB", chat_default)
    web_safe = os.getenv("NIK_MODELO_WEB_SAFE", os.getenv("NIK_MODELO_FALLBACK", chat_default))

    msg = (mensagem or "").lower()
    escolha = chat_default
    if tarefa == "relatorio":
        escolha = relatorio_default
    elif tarefa == "landing":
        escolha = landing_default
    elif tarefa == "web":
        disable_compound = os.getenv("NIK_WEB_DISABLE_COMPOUND", "true").strip().lower() in {"1", "true", "yes"}
        wd = (web_default or "").lower()
        ws = (web_safe or "").lower()
        heavy = "compound" in wd or "70b" in wd
        heavy_safe = "compound" in ws or "70b" in ws
        if disable_compound and heavy:
            escolha = web_safe if not heavy_safe else small
        else:
            escolha = web_default
    elif tarefa in {"analytics", "ops_resumo", "ops_alerta", "ops_coletor"}:
        escolha = analytics_default
    elif tarefa == "conversa":
        # Prompts longos: por defeito usa o mesmo tier que OPS/analytics (evita modelo grande/TPD).
        # NIK_ROUTE_LONG_CONTEXT_TO_70B: se true, escala para NIK_MODELO_LONG_CONTEXT ou NIK_MODELO_ANALYTICS (não para RELATORIO).
        route_long = os.getenv("NIK_ROUTE_LONG_CONTEXT_TO_70B", "false").strip().lower() in {"1", "true", "yes"}
        if route_long:
            if len(msg) > 900 or any(k in msg for k in ["relatório completo", "analise profunda", "plano estratégico"]):
                explicit_lc = (os.getenv("NIK_MODELO_LONG_CONTEXT") or "").strip()
                if explicit_lc:
                    escolha = explicit_lc
                else:
                    escolha = os.getenv("NIK_MODELO_ANALYTICS", chat_default)
            else:
                escolha = chat_default
        else:
            escolha = chat_default
    return _evitar_llama_70b_e_compound(escolha)


def _modelo_web_writer(mensagem: str) -> str:
    """Modelo que redige a resposta final após pesquisa web (evita 70B/TPD na cola do fluxo web)."""
    explicit = (os.getenv("NIK_MODELO_WEB_WRITER") or "").strip()
    if explicit:
        return explicit
    return _modelo_tarefa("analytics", mensagem)


def _mensagem_pede_web(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    sinais_web = [
        "internet",
        "na web",
        "web",
        "notícia",
        "noticia",
        "fonte externa",
        "atualizado hoje",
        "dados recentes",
        "dados atualizados",
        "cenário atual",
        "cenario atual",
        "panorama atual",
        "estado da arte",
    ]
    if any(k in msg for k in sinais_web):
        return True

    if any(k in msg for k in ["fonte", "fontes", "links", "referência", "referencias", "referências"]):
        return True

    # Verbos de pesquisa + tema externo também disparam web research.
    verbos_busca = [
        "pesquise",
        "pesquisar",
        "busque",
        "buscar",
        "procure",
        "encontre",
        "pesquisa",
        "levantamento",
        "estudo",
    ]
    temas_externos = [
        "e-waste",
        "ewaste",
        "lixo eletronico",
        "lixo eletrônico",
        "residuo eletronico",
        "resíduo eletrônico",
        "reciclagem",
        "logistica reversa",
        "logística reversa",
        "residuos",
        "resíduos",
        "ambiental",
        "esg",
        "mercado",
        "setor",
        "concorr",
        "tendência",
        "tendencia",
        "benchmark",
        "demanda",
        "oportunidade",
        "legislação",
        "legislacao",
    ]
    if any(v in msg for v in verbos_busca) and any(t in msg for t in temas_externos):
        return True

    # Intenções frequentes sem verbo explícito de busca.
    frases_pesquisa = [
        "pesquisa de mercado",
        "analise de mercado",
        "análise de mercado",
        "estudo de mercado",
        "levantamento de mercado",
        "panorama de mercado",
        "mapeamento de mercado",
        "quais são as principais iniciativas",
        "quais sao as principais iniciativas",
    ]
    if any(f in msg for f in frases_pesquisa):
        return True

    # Perguntas de contexto geográfico/setorial tendem a exigir fonte externa.
    locais = ["brasil", "brasilia", "distrito federal", "df", "regional", "local", "mundo", "global"]
    return bool(any(t in msg for t in temas_externos) and any(loc in msg for loc in locais))


def _mensagem_pede_documento(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    gatilhos = [
        "gere um documento",
        "gerar documento",
        "modo documento",
        "com sumário",
        "com sumario",
        "relatório detalhado",
        "estilo manus",
        "documento executivo",
        "gere"
        "crie"
        "criar"
    ]
    return any(g in msg for g in gatilhos)


def _cache_get(chave: str, ttl: int) -> dict[str, Any] | None:
    return obter_cache().obter(chave, ttl)


def _cache_set(chave: str, valor: dict[str, Any]) -> dict[str, Any]:
    obter_cache().definir(chave, valor)
    return valor


def _resposta_ops(cache_key: str, ttl: int, fallback: str, chamada_modelo, contexto):
    cached = _cache_get(cache_key, ttl)
    if cached:
        return cached
    if not _nik_habilitada():
        return {"texto": fallback, "fonte": "desabilitada", "modelo": None}

    resposta = chamada_modelo(contexto)
    texto = val.validar_resposta_ops(
        resposta.texto if resposta.sucesso else "",
        fallback,
        max_chars=_ttl("NIK_MAX_CHARS_CONVERSA", 3200),
    )
    resultado = {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso and texto != fallback else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
        "tokens_prompt": resposta.tokens_prompt,
        "tokens_resposta": resposta.tokens_resposta,
        "latencia_ms": resposta.latencia_ms,
    }
    return _cache_set(cache_key, resultado)


def resumo_operacional(db: Session) -> dict[str, Any]:
    contexto = ctx.contexto_resumo_operacional(db)
    return _resposta_ops(
        "nik:ops:resumo",
        _ttl("NIK_CACHE_TTL_RESUMO_OPS", 1800),
        _FALLBACK_RESUMO,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_RESUMO,
            prompts.montar_prompt_ops_resumo(c),
            modelo=_modelo_tarefa("ops_resumo"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def analisar_imagem_coletor(
    db: Session,
    image_bytes: bytes,
    coletor_id: int | None = None,
    *,
    mime: str = "image/jpeg",
    pergunta: str | None = None,
) -> dict[str, Any]:
    """Análise visual de foto de coletor (foundation multimodal; sem câmera ao vivo)."""
    if len(image_bytes) > NIK_IMAGEM_MAX_BYTES:
        return {
            "texto": "Imagem excede o limite de 4 MB.",
            "fonte": "validacao",
            "modelo": None,
            "coletor_id": coletor_id,
        }

    if not multimodal_habilitado():
        return {
            "texto": _FALLBACK_MULTIMODAL_DESABILITADO,
            "fonte": "multimodal_desabilitado",
            "modelo": None,
            "coletor_id": coletor_id,
        }

    if not _nik_habilitada():
        return {
            "texto": _FALLBACK_MULTIMODAL_DESABILITADO,
            "fonte": "nik_desabilitada",
            "modelo": None,
            "coletor_id": coletor_id,
        }

    modelo = os.getenv("NIK_MODELO_OPS", "llama-3.1-8b-instant")
    routed = _modelo_tarefa("ops_coletor")
    if provider.modelo_suporta_visao(routed):
        modelo = routed
    elif not provider.modelo_suporta_visao(modelo):
        return {
            "texto": _FALLBACK_MULTIMODAL_DESABILITADO,
            "fonte": "modelo_sem_visao",
            "modelo": None,
            "coletor_id": coletor_id,
        }

    user_text = (pergunta or "Analise esta imagem no contexto operacional do coletor Tronik.").strip()
    if coletor_id is not None:
        contexto = ctx.contexto_coletor(db, coletor_id)
        if contexto:
            user_text = f"{user_text}\n\n{prompts.montar_prompt_ops_imagem(contexto)}"
        else:
            user_text = f"{user_text}\n\nColetor id={coletor_id} não encontrado no banco."

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    resposta = provider.chamar_modelo_visao(
        prompts.SYSTEM_OPS_IMAGEM,
        user_text,
        image_b64,
        mime=mime,
        modelo=modelo,
        max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
        temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
    )

    fallback = "Não foi possível analisar a imagem neste momento."
    texto = val.validar_resposta_ops(
        resposta.texto if resposta.sucesso else "",
        fallback,
        max_chars=_ttl("NIK_MAX_CHARS_CONVERSA", 3200),
    )
    return {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso and texto != fallback else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
        "coletor_id": coletor_id,
        "tokens_prompt": resposta.tokens_prompt,
        "tokens_resposta": resposta.tokens_resposta,
        "latencia_ms": resposta.latencia_ms,
    }


def analise_coletor(db: Session, coletor_id: int) -> dict[str, Any]:
    contexto = ctx.contexto_coletor(db, coletor_id)
    if not contexto:
        return {"texto": "Coletor não encontrado.", "fonte": "sistema", "modelo": None}
    return _resposta_ops(
        f"nik:ops:coletor:{coletor_id}",
        _ttl("NIK_CACHE_TTL_COLETOR_OPS", 600),
        _FALLBACK_COLETOR,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_COLETOR,
            prompts.montar_prompt_ops_coletor(c),
            modelo=_modelo_tarefa("ops_coletor"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def analise_alerta(db: Session) -> dict[str, Any]:
    contexto = ctx.contexto_alerta(db)
    if not contexto:
        return {"texto": "Nenhum alerta crítico ativo no momento.", "fonte": "sistema", "modelo": None}
    return _resposta_ops(
        "nik:ops:alerta",
        _ttl("NIK_CACHE_TTL_RESUMO_OPS", 1800),
        _FALLBACK_ALERTA,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_ALERTA,
            prompts.montar_prompt_ops_alerta(c),
            modelo=_modelo_tarefa("ops_alerta"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def narrativa_relatorio(
    db: Session,
    inicio: str | None,
    fim: str | None,
    parceiro_id: int | None,
) -> dict[str, Any]:
    contexto = ctx.contexto_relatorio(db, inicio, fim, parceiro_id)
    chave = f"nik:ops:relatorio:{contexto['periodo']['inicio']}:{contexto['periodo']['fim']}:{parceiro_id or 'all'}"
    return _resposta_ops(
        chave,
        _ttl("NIK_CACHE_TTL_RELATORIO_OPS", 3600),
        _FALLBACK_RELATORIO,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_RELATORIO,
            prompts.montar_prompt_ops_relatorio(c),
            modelo=_modelo_tarefa("relatorio"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def gerar_bloco_landing(tipo_bloco: str) -> dict[str, Any]:
    cache_key = f"nik:landing:{tipo_bloco}"
    cached = _cache_get(cache_key, _ttl("NIK_CACHE_TTL_LANDING", 3600))
    if cached:
        return cached

    fallback = _FALLBACK_BLOCO_LANDING.get(tipo_bloco)
    if not fallback:
        return {"bloco": None, "fonte": "invalido", "modelo": None}
    if not _nik_habilitada():
        return {"bloco": fallback, "fonte": "desabilitada", "modelo": None}

    use_nv_landing = os.getenv("NIK_LANDING_USE_NVIDIA", "true").strip().lower() in {"1", "true", "yes"}
    modelo_nv = (
        (os.getenv("NIK_MODELO_LANDING_NVIDIA") or os.getenv("NIK_MODELO_CHAT_NVIDIA") or "mistralai/mistral-nemotron")
        .strip()
    )
    modelo_groq = _modelo_tarefa("landing")

    resposta = provider.chamar_modelo(
        prompts.SYSTEM_LANDING,
        prompts.montar_prompt_landing(tipo_bloco, ctx.contexto_landing()),
        modelo=modelo_nv if use_nv_landing else modelo_groq,
        max_tokens=_ttl("NIK_MAX_TOKENS_LANDING", 384),
        temperature=float(os.getenv("NIK_TEMPERATURE_LANDING", "0.7")),
        prefer_nvidia_integrate_first=use_nv_landing,
        modelo_primario_se_sem_nv=modelo_groq if use_nv_landing else None,
    )
    bloco = (
        val.validar_resposta_landing(resposta.texto, tipo_bloco)
        if resposta.sucesso
        else None
    )
    resultado = {
        "bloco": bloco or fallback,
        "fonte": "modelo" if bloco else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
    }
    return _cache_set(cache_key, resultado)


def conversar_ops(db: Session, mensagem: str) -> dict[str, Any]:
    return conversar_ops_thread(db, mensagem, thread_id="main", usuario_id=None)


def _normalizar_thread_id(thread_id: str | None) -> str:
    raw = (thread_id or "main").strip().lower()
    if not raw:
        return "main"
    safe = re.sub(r"[^a-z0-9._-]", "-", raw)
    return safe[:80] or "main"


_THREAD_RESUMO_LIMIAR = 12
_THREAD_RESUMO_MSGS = 20
_THREAD_RESUMO_MAX_CHARS = 400


def _modelo_resumo_thread() -> str:
    return os.getenv("NIK_MODELO_RESUMO", "llama-3.1-8b-instant")


def _query_thread_conversas(
    db: Session,
    usuario_id: int | None,
    thread_id: str,
):
    tid = _normalizar_thread_id(thread_id)
    q = db.query(NikConversa).filter(NikConversa.thread_id == tid)
    if usuario_id is not None:
        q = q.filter(NikConversa.usuario_id == usuario_id)
    return q, tid


def _obter_resumo_thread(
    db: Session,
    usuario_id: int | None,
    thread_id: str,
) -> str | None:
    q, _ = _query_thread_conversas(db, usuario_id, thread_id)
    latest = q.order_by(NikConversa.criado_em.desc()).first()
    if not latest or not latest.resumo_thread:
        return None
    texto = (latest.resumo_thread or "").strip()
    return texto[:_THREAD_RESUMO_MAX_CHARS] if texto else None


def _montar_prompt_resumo_thread(rows: list[NikConversa]) -> str:
    linhas: list[str] = []
    for r in rows:
        pergunta = (r.pergunta or "").strip()[:500]
        resposta = (r.resposta or "").strip()[:500]
        linhas.append(f"Usuário: {pergunta}\nNik: {resposta}")
    corpo = "\n\n".join(linhas)
    return (
        "Resuma a conversa abaixo em português, em no máximo 400 caracteres. "
        "Mantenha fatos, nomes, números e decisões relevantes. Sem markdown.\n\n"
        f"{corpo}"
    )


def _resumir_thread_se_necessario(
    db: Session,
    usuario_id: int | None,
    thread_id: str,
) -> str | None:
    """Gera resumo LLM quando a thread passa de 12 mensagens; persiste na linha mais recente."""
    q, tid = _query_thread_conversas(db, usuario_id, thread_id)
    total = q.count()
    if total <= _THREAD_RESUMO_LIMIAR:
        return _obter_resumo_thread(db, usuario_id, tid)

    rows = q.order_by(NikConversa.criado_em.desc()).limit(_THREAD_RESUMO_MSGS).all()
    rows.reverse()
    if not rows:
        return None

    resposta = provider.chamar_modelo(
        "Você resume conversas operacionais de forma objetiva e factual.",
        _montar_prompt_resumo_thread(rows),
        modelo=_modelo_resumo_thread(),
        max_tokens=180,
        temperature=0.2,
    )
    if not resposta.sucesso or not (resposta.texto or "").strip():
        return _obter_resumo_thread(db, usuario_id, tid)

    resumo = re.sub(r"\s+", " ", resposta.texto.strip())[:_THREAD_RESUMO_MAX_CHARS]
    latest = q.order_by(NikConversa.criado_em.desc()).first()
    if latest and resumo:
        latest.resumo_thread = resumo
        db.commit()
    return resumo or None


def _historico_thread(
    db: Session,
    usuario_id: int | None,
    thread_id: str,
    limite: int = 8,
) -> list[dict[str, Any]]:
    q, tid = _query_thread_conversas(db, usuario_id, thread_id)
    rows = q.order_by(NikConversa.criado_em.desc()).limit(max(1, min(limite, 20))).all()
    rows.reverse()
    hist = [
        {
            "pergunta": r.pergunta,
            "resposta": r.resposta,
            "criado_em": r.criado_em.isoformat() if r.criado_em else None,
        }
        for r in rows
    ]
    resumo = _obter_resumo_thread(db, usuario_id, tid)
    if resumo:
        hist.insert(
            0,
            {
                "pergunta": "(resumo da thread)",
                "resposta": resumo,
                "criado_em": None,
                "tipo": "resumo_thread",
            },
        )
    return hist


def _mensagem_pede_prospeccao(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(
        k in msg
        for k in [
            "prospecção",
            "prospeccao",
            "prospecao",
            "fila de prospecção",
            "fila de prospeccao",
            "fila ree",
            "ranking de prospecção",
            "ranking ree",
            "candidatos ree",
            "leads ree",
            "score de prospecção",
            "score prospecção",
            "empresas para prospectar",
            "empresas para prospecção",
        ]
    ):
        return True
    return "prospec" in msg and any(
        k in msg for k in ["candidat", "ranking", "fila", "lista", "top", "melhor", "prioridade", "ree"]
    )


def _mensagem_pede_explicacao_lead(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(
        k in msg
        for k in [
            "por que esse lead",
            "por que este lead",
            "por que esse candidato",
            "por que este candidato",
            "por que o lead",
            "motivo do score",
            "motivos do score",
            "explicar candidato",
            "explicar o candidato",
            "explicar lead",
            "explicar o lead",
        ]
    ):
        return True
    return any(k in msg for k in ["por que", "motivo", "motivos", "explic"]) and any(
        k in msg for k in ["lead", "candidat", "score", "ranking", "prospec"]
    )


def _mensagem_pede_cruzar_crm_prospeccao(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(
        k in msg
        for k in [
            "crm e prospecção",
            "crm e prospeccao",
            "crm e prospecao",
            "cruzar crm",
            "cruze crm",
            "cruzamento crm",
            "pipeline e prospecção",
            "pipeline e prospeccao",
            "lead no ranker",
            "lead no ranking",
            "leads do crm",
            "leads no crm",
            "está no ranker",
            "esta no ranker",
            "está no ranking ree",
            "esta no ranking ree",
            "no ranker ree",
            "score do crm",
            "crm com prospecção",
            "crm com prospeccao",
            "crm com ree",
            "crm x ree",
            "crm e ree",
            "carteira",
            "minha carteira",
            "na carteira",
            "clientes ree",
            "clientes do ree",
            "prospecção ree",
            "prospeccao ree",
            "diferença entre crm",
            "diferenca entre crm",
            "não estão no crm",
            "nao estao no crm",
            "fora do crm",
            "fora da carteira",
            "prioridade ree",
            "prioridade de prospecção",
        ]
    ):
        return True
    if (
        any(k in msg for k in ["compare", "comparar", "comparação", "comparacao", "diferença", "diferenca"])
        and "crm" in msg
        and any(k in msg for k in ["ree", "score", "prospec", "ranking", "lead", "carteira"])
    ):
        return True
    if any(k in msg for k in ["carteira", "clientes"]) and any(
        k in msg for k in ["ree", "prospec", "ranking", "score", "crm"]
    ):
        return True
    return ("crm" in msg or "pipeline" in msg or "lead" in msg) and any(
        k in msg for k in ["prospec", "ree", "score", "ranking"]
    )


def _mensagem_pede_exportar_csv(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    gatilhos_arquivo = [
        "csv",
        "xlsx",
        "excel",
        "planilha",
        "arquivo",
        "exportar",
        "exportação",
        "exportacao",
        "baixar",
        "download",
        "me envie",
        "me mande",
        "me manda",
        "enviar o arquivo",
        "enviar arquivo",
        "puxar os dados",
    ]
    return any(g in msg for g in gatilhos_arquivo)


def _mensagem_pede_coleta_hoje(mensagem: str) -> bool:
    msg = (mensagem or "").lower().strip()
    return msg in {"coleta de hoje", "coletas de hoje", "coleta hoje", "coletas hoje"} or (
        "coleta" in msg and "hoje" in msg and len(msg) < 40
    )


def _extrair_coletor_id(mensagem: str) -> int | None:
    msg = (mensagem or "").strip()
    for pattern in (
        r"#L0*(\d{1,4})\b",
        r"\b[lL]\s*0*(\d{1,4})\b",
        r"\bcoletor\s*#?\s*0*(\d{1,4})\b",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _extrair_nomes_parceiros(db: Session, mensagem: str) -> list[str]:
    msg = (mensagem or "").lower()
    nomes: list[str] = []
    rows = db.query(Parceiro.nome).filter(Parceiro.ativo.is_(True)).all()
    for (nome,) in sorted(rows, key=lambda r: len(r[0] or ""), reverse=True):
        nome_l = (nome or "").strip().lower()
        if nome_l and nome_l in msg:
            nomes.append(nome.strip())
    return nomes


def _extrair_pipeline_id(mensagem: str) -> int | None:
    msg = (mensagem or "").strip()
    for pattern in (
        r"\bpipeline[_\s-]?id[=:\s]+(\d+)\b",
        r"\bpipeline\s*#?\s*(\d+)\b",
        r"\bpipeline\s+(\d+)\b",
        r"\bid\s+do\s+pipeline[=:\s]+(\d+)\b",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _extrair_empresa_crm(mensagem: str) -> str | None:
    msg = (mensagem or "").strip()
    for pattern in (
        r"\bempresa\s+[\"']([^\"']{3,120})[\"']",
        r"\bempresa\s+([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s.&-]{2,80}?)(?:\s+(?:no|na|do|da|está|esta|tem|com)\b|$)",
        r"\bda\s+empresa\s+([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s.&-]{2,80}?)(?:\s+(?:no|na|está|esta)\b|$)",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            nome = m.group(1).strip(" .,;:")
            if len(nome) >= 3:
                return nome
    return None


def _mensagem_pede_status_modelo(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(
        k in msg
        for k in [
            "modelo de prospecção",
            "modelo de prospeccao",
            "modelo de prospecao",
            "versão do modelo",
            "versao do modelo",
            "métricas do modelo",
            "metricas do modelo",
            "status do modelo",
            "qual modelo",
            "modelo ativo",
            "ndcg do modelo",
        ]
    ):
        return True
    return "modelo" in msg and "prospec" in msg


def _mensagem_pede_comparar_candidatos(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(k in msg for k in ["comparar candidatos", "compare candidatos", "comparar leads", "compare leads"]):
        return True
    return any(k in msg for k in ["comparar", "compare", "comparação", "comparacao"]) and any(
        k in msg for k in ["candidat", "lead", "prospec", "ree", "ranking"]
    )


def _mensagem_pede_roteiro_contato(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(
        k in msg
        for k in [
            "roteiro de contato",
            "roteiro de ligação",
            "roteiro de ligacao",
            "script de ligação",
            "script de ligacao",
            "script de contato",
            "gerar roteiro",
            "montar roteiro",
        ]
    ):
        return True
    return any(k in msg for k in ["roteiro", "script", "ligação", "ligacao"]) and any(
        k in msg for k in ["contato", "ligar", "liga", "comercial", "lead", "candidat"]
    )


def _mensagem_pede_criar_tarefa_comercial(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    if any(
        k in msg
        for k in [
            "criar tarefa",
            "crie tarefa",
            "nova tarefa",
            "criar lembrete",
            "follow-up crm",
            "follow up crm",
            "followup crm",
            "tarefa no crm",
            "tarefa comercial",
        ]
    ):
        return True
    return "tarefa" in msg and any(k in msg for k in ["crm", "comercial", "follow", "lembrete"])


def _extrair_score_ids(mensagem: str) -> list[int]:
    msg = (mensagem or "").strip()
    ids: list[int] = []
    for pattern in (
        r"\bscore[_\s-]?id[=:\s]+(\d+)\b",
        r"\bscore_id[=:\s]+(\d+)\b",
        r"\bscores?\s*[=:\s]+(\d+(?:\s*[,;/]\s*\d+)*)\b",
        r"\bcandidatos?\s+(\d+(?:\s*[,;/]\s*\d+)+)\b",
    ):
        for m in re.finditer(pattern, msg, flags=re.I):
            grupo = m.group(1)
            for parte in re.split(r"[,;/\s]+", grupo):
                parte = parte.strip()
                if parte.isdigit():
                    ids.append(int(parte))
    for m in re.finditer(r"\bscore\s+(\d+)\b", msg, flags=re.I):
        ids.append(int(m.group(1)))
    vistos: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i in vistos:
            continue
        vistos.add(i)
        out.append(i)
    return out


def _extrair_empresa_ids(mensagem: str) -> list[int]:
    msg = (mensagem or "").strip()
    ids: list[int] = []
    for m in re.finditer(r"\bempresa[_\s-]?id[=:\s]+(\d+)\b", msg, flags=re.I):
        ids.append(int(m.group(1)))
    vistos: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i in vistos:
            continue
        vistos.add(i)
        out.append(i)
    return out


def _extrair_titulo_tarefa(mensagem: str) -> str | None:
    msg = (mensagem or "").strip()
    for pattern in (
        r"\btarefa\s+[\"']([^\"']{3,200})[\"']",
        r"\btítulo\s+[\"']([^\"']{3,200})[\"']",
        r"\btitulo\s+[\"']([^\"']{3,200})[\"']",
        r"\bcriar\s+tarefa[:\s]+(.{5,200}?)(?:\s+pipeline|\s+empresa|\s+data|\s+para\s+o\s+crm|$)",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            titulo = m.group(1).strip(" .,:;")
            if len(titulo) >= 3:
                return titulo
    return None


def _extrair_data_limite_tarefa(mensagem: str) -> str | None:
    msg = (mensagem or "").strip()
    m = re.search(r"\bdata[_\s-]?limite[=:\s]+(\S+)", msg, flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b(?:até|ate|para)\s+(\d{2}/\d{2}/\d{4})\b", msg, flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", msg)
    if m:
        return m.group(1)
    return None


def _extrair_score_id(mensagem: str) -> int | None:
    msg = (mensagem or "").strip()
    for pattern in (
        r"\bscore[_\s-]?id[=:\s]+(\d+)\b",
        r"\bscore_id[=:\s]+(\d+)\b",
        r"\bid\s+do\s+score[=:\s]+(\d+)\b",
        r"\bscore\s+(\d+)\b",
        r"\bcandidato\s+(\d+)\b",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _extrair_filtros_prospeccao(mensagem: str) -> dict[str, Any]:
    msg = (mensagem or "").lower()
    kwargs: dict[str, Any] = {}
    if any(k in msg for k in ["prioridade alta", "alta prioridade", "prioridade: alta"]):
        kwargs["prioridade"] = "alta"
    elif any(k in msg for k in ["prioridade media", "prioridade média", "media prioridade", "média prioridade"]):
        kwargs["prioridade"] = "media"
    elif any(k in msg for k in ["prioridade baixa", "baixa prioridade"]):
        kwargs["prioridade"] = "baixa"
    m_lim = re.search(r"\b(?:top|primeiros?)\s+(\d{1,2})\b", msg)
    if m_lim:
        kwargs["limite"] = int(m_lim.group(1))
    m_cand = re.search(r"\b(\d{1,2})\s+candidatos?\b", msg)
    if m_cand and "limite" not in kwargs:
        kwargs["limite"] = int(m_cand.group(1))
    m_qid = re.search(r"\bqid[=:]\s*([^\s,;.]+)", msg, flags=re.I)
    if m_qid:
        kwargs["qid"] = m_qid.group(1).strip()
    return kwargs


def _planejar_ferramentas(mensagem: str) -> list[dict[str, Any]]:
    msg = (mensagem or "").lower()
    anos = _extrair_anos(msg)
    ano_inicio = min(anos) if anos else None
    ano_fim = max(anos) if anos else None

    plano: list[dict[str, Any]] = [{"nome": "snapshot_operacional", "kwargs": {}}]
    pede_web = _mensagem_pede_web(mensagem)
    pede_prospeccao = _mensagem_pede_prospeccao(mensagem)
    pede_explicacao_lead = _mensagem_pede_explicacao_lead(mensagem)
    pede_status_modelo = _mensagem_pede_status_modelo(mensagem)
    pede_cruzar_crm = _mensagem_pede_cruzar_crm_prospeccao(mensagem)
    pede_comparar = _mensagem_pede_comparar_candidatos(mensagem)
    pede_roteiro = _mensagem_pede_roteiro_contato(mensagem)
    pede_tarefa_crm = _mensagem_pede_criar_tarefa_comercial(mensagem)
    pede_busca_interna = any(k in msg for k in ["busque", "buscar", "procure", "encontre", "no sistema"])
    pergunta_exploratoria = any(k in msg for k in ["quais", "qual", "quem", "onde"]) and not any(
        k in msg for k in ["relatório", "relatorio", "timeline", "impacto"]
    )

    if pede_status_modelo:
        plano.append({"nome": "status_modelo_prospeccao", "kwargs": {}})
    if pede_explicacao_lead:
        kwargs_explicar: dict[str, Any] = {}
        score_id = _extrair_score_id(mensagem)
        if score_id is not None:
            kwargs_explicar["score_id"] = score_id
        plano.append({"nome": "explicar_candidato_prospeccao", "kwargs": kwargs_explicar})
    if pede_prospeccao:
        plano.append({"nome": "listar_candidatos_prospeccao", "kwargs": _extrair_filtros_prospeccao(mensagem)})
    if pede_cruzar_crm:
        kwargs_cruzar: dict[str, Any] = {"modo_global": True}
        pipeline_id = _extrair_pipeline_id(mensagem)
        if pipeline_id is not None:
            kwargs_cruzar["pipeline_id"] = pipeline_id
            kwargs_cruzar["modo_global"] = False
        empresa_nome = _extrair_empresa_crm(mensagem)
        if empresa_nome:
            kwargs_cruzar["empresa"] = empresa_nome
            kwargs_cruzar["modo_global"] = False
        plano.append({"nome": "cruzar_crm_prospeccao", "kwargs": kwargs_cruzar})
        plano.append({"nome": "listar_candidatos_prospeccao", "kwargs": {"limite": 15, "prioridade": "alta"}})
    if pede_comparar:
        kwargs_cmp: dict[str, Any] = {}
        score_ids = _extrair_score_ids(mensagem)
        empresa_ids = _extrair_empresa_ids(mensagem)
        if score_ids:
            kwargs_cmp["score_ids"] = score_ids
        if empresa_ids:
            kwargs_cmp["empresa_ids"] = empresa_ids
        m_lim = re.search(r"\b(?:top|compare|comparar)\s+(\d{1,2})\b", msg)
        if m_lim:
            kwargs_cmp["limite"] = int(m_lim.group(1))
        plano.append({"nome": "comparar_candidatos", "kwargs": kwargs_cmp})
    if pede_roteiro:
        kwargs_rot: dict[str, Any] = {}
        score_id = _extrair_score_id(mensagem)
        if score_id is not None:
            kwargs_rot["score_id"] = score_id
        empresa_ids = _extrair_empresa_ids(mensagem)
        if empresa_ids:
            kwargs_rot["empresa_id"] = empresa_ids[0]
        pipeline_id = _extrair_pipeline_id(mensagem)
        if pipeline_id is not None:
            kwargs_rot["pipeline_id"] = pipeline_id
        plano.append({"nome": "gerar_roteiro_contato", "kwargs": kwargs_rot})
    if pede_tarefa_crm:
        kwargs_tar: dict[str, Any] = {}
        titulo = _extrair_titulo_tarefa(mensagem)
        if titulo:
            kwargs_tar["titulo"] = titulo
        else:
            kwargs_tar["titulo"] = mensagem.strip()[:200]
        pipeline_id = _extrair_pipeline_id(mensagem)
        if pipeline_id is not None:
            kwargs_tar["pipeline_id"] = pipeline_id
        empresa_ids = _extrair_empresa_ids(mensagem)
        if empresa_ids:
            kwargs_tar["empresa_id"] = empresa_ids[0]
        data_lim = _extrair_data_limite_tarefa(mensagem)
        if data_lim:
            kwargs_tar["data_limite"] = data_lim
        plano.append({"nome": "criar_tarefa_comercial", "kwargs": kwargs_tar})
    if pede_busca_interna or (
        pergunta_exploratoria
        and not pede_prospeccao
        and not pede_explicacao_lead
        and not pede_cruzar_crm
        and not pede_comparar
        and not pede_roteiro
        and not pede_tarefa_crm
    ):
        plano.append({"nome": "busca_unificada", "kwargs": {"consulta": mensagem.strip()}})
    if pede_web:
        plano.append({"nome": "catalogo_fontes_web", "kwargs": {}})
        plano.append({"nome": "busca_web", "kwargs": {"consulta": mensagem.strip()}})
    if any(k in msg for k in ["linha do tempo", "timeline", "dados antigos", "histórico", "historico", "desde"]) or len(anos) >= 1:
        plano.append({"nome": "timeline_anual", "kwargs": {"ano_inicio": ano_inicio, "ano_fim": ano_fim}})
    if any(k in msg for k in ["impacto", "completo", "ostensivo", "estratég", "estrateg"]):
        plano.append({"nome": "impacto_geral", "kwargs": {"ano_inicio": ano_inicio, "ano_fim": ano_fim}})
    if "relatório" in msg or "relatorio" in msg:
        plano.append({"nome": "resumo_periodo", "kwargs": {}})
    coletor_id = _extrair_coletor_id(mensagem)
    if coletor_id is not None:
        plano.append({"nome": "info_coletor", "kwargs": {"coletor_id": coletor_id}})
    if _mensagem_pede_exportar_csv(mensagem):
        plano.append({"nome": "exportar_coletas_csv", "kwargs": {}})
    if _mensagem_pede_coleta_hoje(mensagem):
        hoje = date.today().isoformat()
        plano.append({"nome": "resumo_periodo", "kwargs": {"inicio": hoje, "fim": hoje}})
    # Dedupe mantendo ordem (evita chamadas repetidas)
    vistos: set[str] = set()
    final: list[dict[str, Any]] = []
    for p in plano:
        nome = str(p.get("nome") or "")
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        final.append(p)
    return final


def _agent_planner_mode() -> str:
    modo = (os.getenv("NIK_AGENT_PLANNER", "heuristic") or "heuristic").strip().lower()
    if modo not in {"llm", "heuristic", "auto"}:
        return "heuristic"
    return modo


def _planejar_ferramentas_completo(mensagem: str) -> tuple[list[dict[str, Any]], str]:
    modo = _agent_planner_mode()
    if modo == "heuristic":
        return _planejar_ferramentas(mensagem), "heuristic"
    plano_llm = nik_agent_planner.planejar_ferramentas_llm(mensagem)
    if modo == "llm":
        if plano_llm:
            return plano_llm, "llm"
        return _planejar_ferramentas(mensagem), "heuristic"
    if plano_llm:
        return plano_llm, "auto_llm"
    return _planejar_ferramentas(mensagem), "auto_heuristic"


def _extrair_datas_iso_ou_br(texto: str) -> list[date]:
    out: list[date] = []
    for a, b, c in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", texto):
        with contextlib.suppress(ValueError):
            out.append(date(int(a), int(b), int(c)))
    for d, m, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", texto):
        with contextlib.suppress(ValueError):
            out.append(date(int(y), int(m), int(d)))
    return out


def _extrair_mes_ano(texto: str) -> tuple[int, int] | None:
    meses = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    msg = (texto or "").lower()
    for nome, numero in meses.items():
        m = re.search(rf"\b{re.escape(nome)}\s+(?:de\s+)?(20\d{{2}})\b", msg)
        if m:
            return numero, int(m.group(1))
    return None


def _fim_mes(ano: int, mes: int) -> date:
    if mes == 12:
        return date(ano, 12, 31)
    return date(ano, mes + 1, 1) - timedelta(days=1)


def _periodo_ultimo_ano_com_dados(db: Session) -> dict[str, str] | None:
    limites = nik_tools.ferramenta_limites_historico(db)
    fim_raw = limites.get("fim")
    if not fim_raw:
        return None
    fim = datetime.fromisoformat(fim_raw).date()
    inicio = fim - timedelta(days=365)
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat()}


def _pedido_relatorio_ultimo_ano(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    gatilhos = [
        "último ano",
        "ultimo ano",
        "últimos 12 meses",
        "ultimos 12 meses",
        "12 meses",
        "ano passado",
    ]
    return any(g in msg for g in gatilhos) and ("relatório" in msg or "relatorio" in msg or "resumo" in msg)


def _extrair_parceiro_id_por_texto(db: Session, mensagem: str) -> int | None:
    msg = (mensagem or "").lower()
    rows = db.query(Parceiro.id, Parceiro.nome).all()
    for pid, nome in sorted(rows, key=lambda r: len(r[1] or ""), reverse=True):
        nome_l = (nome or "").strip().lower()
        if nome_l and nome_l in msg:
            return int(pid)
    m = re.search(r"\bparceiro\s*#?\s*(\d{1,6})\b", msg)
    return int(m.group(1)) if m else None


_MES_PARA_NUM: dict[str, int] = {
    "janeiro": 1,
    "jan": 1,
    "fevereiro": 2,
    "fev": 2,
    "marco": 3,
    "março": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "maio": 5,
    "mai": 5,
    "junho": 6,
    "jun": 6,
    "julho": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "setembro": 9,
    "set": 9,
    "outubro": 10,
    "out": 10,
    "novembro": 11,
    "nov": 11,
    "dezembro": 12,
    "dez": 12,
}


def _normalizar_token_mes(token: str) -> str:
    return (token or "").strip().lower().rstrip(".")


def _extrair_intervalo_meses(texto: str, ano_default: int | None = None) -> tuple[date, date] | None:
    ano_ref = ano_default or date.today().year
    msg = (texto or "").lower().strip().strip("'\"")
    meses_alt = "|".join(re.escape(k) for k in sorted(_MES_PARA_NUM.keys(), key=len, reverse=True))
    m = re.search(
        rf"(?:de\s+)?({meses_alt})\s+(?:a|at[eé]|-)\s+({meses_alt})(?:\s+de)?(?:\s+(20\d{{2}}))?",
        msg,
    )
    if not m:
        return None
    mes_ini = _MES_PARA_NUM.get(_normalizar_token_mes(m.group(1)))
    mes_fim = _MES_PARA_NUM.get(_normalizar_token_mes(m.group(2)))
    if mes_ini is None or mes_fim is None:
        return None
    ano = int(m.group(3)) if m.group(3) else ano_ref
    if mes_ini > mes_fim:
        mes_ini, mes_fim = mes_fim, mes_ini
    return date(ano, mes_ini, 1), _fim_mes(ano, mes_fim)


def _inferir_consulta_usuario(db: Session, mensagem: str) -> dict[str, Any]:
    msg = (mensagem or "").lower()
    limites = nik_tools.ferramenta_limites_historico(db)
    data_max = date.fromisoformat(limites["fim"]) if limites.get("fim") else date.today()
    datas = sorted(_extrair_datas_iso_ou_br(mensagem))
    anos = _extrair_anos(msg)
    mes_ano = _extrair_mes_ano(msg)
    parceiro_id = _extrair_parceiro_id_por_texto(db, mensagem)
    parceiro_nomes = _extrair_nomes_parceiros(db, mensagem)
    intervalo_meses = _extrair_intervalo_meses(mensagem, ano_default=data_max.year)

    inicio: date | None = None
    fim: date | None = None
    ano_inicio: int | None = None
    ano_fim: int | None = None

    if intervalo_meses:
        inicio, fim = intervalo_meses
    elif len(datas) >= 2:
        inicio, fim = datas[0], datas[-1]
    elif len(datas) == 1:
        inicio = datas[0]
        fim = datas[0]
    elif _pedido_relatorio_ultimo_ano(mensagem):
        per = _periodo_ultimo_ano_com_dados(db)
        if per:
            inicio = date.fromisoformat(per["inicio"])
            fim = date.fromisoformat(per["fim"])
    elif re.search(r"\bultim[oa]s?\s+(\d{1,3})\s+dias\b", msg):
        dias = int(re.search(r"\bultim[oa]s?\s+(\d{1,3})\s+dias\b", msg).group(1))
        fim = data_max
        inicio = fim - timedelta(days=max(1, dias) - 1)
    elif (
        re.search(r"ultim[oa]s?\s+dias\b", msg)
        or "ultima semana" in msg
        or "última semana" in msg
    ):
        fim = data_max
        inicio = fim - timedelta(days=6)
    elif "ultimo trimestre" in msg or "último trimestre" in msg:
        fim = data_max
        inicio = fim - timedelta(days=89)
    elif "ultimo mes" in msg or "último mês" in msg:
        fim = data_max
        inicio = fim - timedelta(days=29)
    elif "este mes" in msg or "este mês" in msg:
        fim = data_max
        inicio = date(fim.year, fim.month, 1)
    elif mes_ano:
        mes, ano = mes_ano
        inicio = date(ano, mes, 1)
        fim = _fim_mes(ano, mes)
    elif len(anos) >= 2:
        ano_inicio = min(anos)
        ano_fim = max(anos)
    elif len(anos) == 1:
        ano_inicio = anos[0]
        ano_fim = anos[0]

    if inicio and fim:
        ano_inicio = inicio.year
        ano_fim = fim.year

    return {
        "inicio": inicio.isoformat() if inicio else None,
        "fim": fim.isoformat() if fim else None,
        "ano_inicio": ano_inicio,
        "ano_fim": ano_fim,
        "parceiro_id": parceiro_id,
        "parceiro_nomes": parceiro_nomes,
    }


def _executar_plano_ferramentas(
    db: Session,
    plano: list[dict[str, Any]],
    usuario_id: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    resultado_contexto: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []
    mapa = {
        "snapshot_operacional": nik_tools.ferramenta_snapshot_operacional,
        "resumo_periodo": nik_tools.ferramenta_resumo_periodo,
        "timeline_anual": nik_tools.ferramenta_timeline_anual,
        "impacto_geral": nik_tools.ferramenta_impacto_geral,
        "limites_historico": nik_tools.ferramenta_limites_historico,
        "busca_unificada": nik_tools.ferramenta_busca_unificada,
        "busca_web": nik_tools.ferramenta_busca_web,
        "catalogo_fontes_web": lambda _db: nik_tools.catalogo_fontes_web(),
        "listar_candidatos_prospeccao": nik_tools.ferramenta_listar_candidatos_prospeccao,
        "explicar_candidato_prospeccao": nik_tools.ferramenta_explicar_candidato_prospeccao,
        "status_modelo_prospeccao": nik_tools.ferramenta_status_modelo_prospeccao,
        "cruzar_crm_prospeccao": nik_tools.ferramenta_cruzar_crm_prospeccao,
        "comparar_candidatos": nik_tools.ferramenta_comparar_candidatos,
        "gerar_roteiro_contato": nik_tools.ferramenta_gerar_roteiro_contato,
        "criar_tarefa_comercial": nik_tools.ferramenta_criar_tarefa_comercial,
        "info_coletor": nik_tools.ferramenta_info_coletor,
        "exportar_coletas_csv": nik_tools.ferramenta_exportar_coletas_csv,
    }
    for item in plano:
        nome = item.get("nome")
        kwargs = dict(item.get("kwargs", {}) or {})
        if nome == "criar_tarefa_comercial" and usuario_id is not None:
            kwargs["usuario_id"] = usuario_id
        if nome == "exportar_coletas_csv" and usuario_id is not None:
            kwargs["usuario_id"] = usuario_id
        fn = mapa.get(nome)
        if not fn:
            trace.append({"tool": nome, "status": "unknown_tool", "kwargs": kwargs})
            continue
        try:
            if nome == "resumo_periodo" and not kwargs:
                kwargs = item["kwargs"] = {}
            saida = fn(db, **kwargs)
            if nome == "snapshot_operacional":
                resultado_contexto.update(saida if isinstance(saida, dict) else {"snapshot_operacional": saida})
            else:
                resultado_contexto[nome] = saida
            trace.append({"tool": nome, "status": "ok", "kwargs": kwargs})
        except Exception as exc:
            trace.append({"tool": nome, "status": "error", "kwargs": kwargs, "erro": str(exc)})
    return resultado_contexto, trace


def _quebrar_em_blocos(texto: str) -> list[str]:
    bruto = (texto or "").strip()
    if not bruto:
        return []
    partes = [p.strip() for p in re.split(r"\n{2,}", bruto) if p.strip()]
    if len(partes) >= 2:
        return partes[:6]
    sentencas = [s.strip() for s in re.split(r"(?<=[.!?])\s+", bruto) if s.strip()]
    if len(sentencas) <= 2:
        return [bruto]
    blocos: list[str] = []
    i = 0
    while i < len(sentencas):
        blocos.append(" ".join(sentencas[i:i + 2]).strip())
        i += 2
    return blocos[:6]


def _fontes_para_bloco(bloco: str, fontes_disponiveis: list[str]) -> list[str]:
    b = (bloco or "").lower()
    fontes: list[str] = []
    if any(k in b for k in ["timeline", "histórico", "historico", "ano"]):
        fontes.append("timeline_anual")
    if any(k in b for k in ["impacto", "eficiência", "eficiencia", "kg/km", "quilometragem", "km"]):
        fontes.append("impacto_geral")
    if any(k in b for k in ["período", "periodo", "resumo", "coletas", "volume"]):
        fontes.append("resumo_periodo")
    if any(k in b for k in ["prospec", "candidat", "ranking", "prioridade", "cnpj", "cnae", "ree"]):
        fontes.append("listar_candidatos_prospeccao")
    if any(k in b for k in ["motivo", "motivos", "explic", "evidência", "evidencia", "por que"]):
        fontes.append("explicar_candidato_prospeccao")
    if any(k in b for k in ["modelo", "ndcg", "xgboost", "versão", "versao", "métrica", "metrica"]):
        fontes.append("status_modelo_prospeccao")
    if any(k in b for k in ["compar", "lado a lado", "versus", "vs "]):
        fontes.append("comparar_candidatos")
    if any(k in b for k in ["roteiro", "script", "ligação", "ligacao", "objeção", "objecao"]):
        fontes.append("gerar_roteiro_contato")
    if any(k in b for k in ["tarefa", "lembrete", "follow-up", "follow up"]):
        fontes.append("criar_tarefa_comercial")
    if not fontes:
        fontes.append("snapshot_operacional")
    finais = [f for f in fontes if f in fontes_disponiveis]
    return finais or (fontes_disponiveis[:1] if fontes_disponiveis else ["snapshot_operacional"])


def _gerar_citacoes_por_bloco(texto: str, contexto: dict[str, Any]) -> list[dict[str, Any]]:
    blocos = _quebrar_em_blocos(texto)
    fontes_disponiveis = contexto.get("used_tools", []) or ["snapshot_operacional"]
    citacoes: list[dict[str, Any]] = []
    for idx, bloco in enumerate(blocos, start=1):
        citacoes.append(
            {
                "bloco_id": idx,
                "trecho": bloco,
                "fontes": _fontes_para_bloco(bloco, fontes_disponiveis),
            }
        )
    return citacoes


def _contexto_para_modelo(contexto: dict[str, Any]) -> dict[str, Any]:
    """Reduz payload para economizar tokens sem perder sinal analítico."""
    slim = dict(contexto)
    resumo_thr = slim.get("thread_resumo")
    if isinstance(resumo_thr, str) and resumo_thr.strip():
        slim["thread_resumo"] = resumo_thr.strip()[:_THREAD_RESUMO_MAX_CHARS]
    hist = slim.get("historico_thread", [])
    if isinstance(hist, list):
        slim["historico_thread"] = [
            {
                "pergunta": str(h.get("pergunta", ""))[:240],
                "resposta": str(h.get("resposta", ""))[:320],
                "criado_em": h.get("criado_em"),
                **({"tipo": h["tipo"]} if h.get("tipo") else {}),
            }
            for h in hist[-3:]
            if isinstance(h, dict)
        ]
    bu = slim.get("busca_unificada")
    if isinstance(bu, dict):
        itens = bu.get("itens", [])
        if isinstance(itens, list):
            bu["itens"] = itens[:6]
    bw = slim.get("busca_web")
    if isinstance(bw, dict):
        itensw = bw.get("itens", [])
        if isinstance(itensw, list):
            # Snippets são essenciais: sem eles o modelo só repete títulos.
            bw["itens"] = [
                {
                    "titulo": i.get("titulo"),
                    "url": i.get("url"),
                    "fonte": i.get("fonte"),
                    "snippet": (str(i.get("snippet") or i.get("resumo") or "")[:420]).strip(),
                }
                for i in itensw[:5]
                if isinstance(i, dict)
            ]
            bw.pop("queries_executadas", None)
            bw.pop("dominios_catalogo", None)
    pros = slim.get("listar_candidatos_prospeccao")
    if isinstance(pros, dict):
        cand = pros.get("candidatos", [])
        if isinstance(cand, list):
            pros["candidatos"] = [
                {
                    "id": c.get("id"),
                    "ranking_contexto": c.get("ranking_contexto"),
                    "prioridade": c.get("prioridade"),
                    "score": c.get("score"),
                    "score_percentil": c.get("score_percentil"),
                    "qid": c.get("qid"),
                    "empresa": {
                        "razao_social": (c.get("empresa") or {}).get("razao_social"),
                        "cnae_principal": (c.get("empresa") or {}).get("cnae_principal"),
                    }
                    if isinstance(c.get("empresa"), dict)
                    else None,
                    "local": {
                        "bairro": (c.get("local") or {}).get("bairro"),
                        "ra": (c.get("local") or {}).get("ra"),
                    }
                    if isinstance(c.get("local"), dict)
                    else None,
                    "motivos": (c.get("motivos") or [])[:3] if isinstance(c.get("motivos"), list) else [],
                }
                for c in cand[:15]
                if isinstance(c, dict)
            ]
    exp = slim.get("explicar_candidato_prospeccao")
    if isinstance(exp, dict):
        score = exp.get("score")
        if isinstance(score, dict):
            exp["score"] = {
                "id": score.get("id"),
                "prioridade": score.get("prioridade"),
                "ranking_contexto": score.get("ranking_contexto"),
                "score": score.get("score"),
                "qid": score.get("qid"),
                "empresa": {
                    "razao_social": (score.get("empresa") or {}).get("razao_social"),
                    "cnae_principal": (score.get("empresa") or {}).get("cnae_principal"),
                }
                if isinstance(score.get("empresa"), dict)
                else None,
            }
        expl = exp.get("explicacao")
        if isinstance(expl, list):
            exp["explicacao"] = expl[:8]
    st = slim.get("status_modelo_prospeccao")
    if isinstance(st, dict) and isinstance(st.get("metricas"), dict):
        metricas = st["metricas"]
        st["metricas"] = {k: metricas[k] for k in list(metricas.keys())[:12]}
    cmp = slim.get("comparar_candidatos")
    if isinstance(cmp, dict):
        comp = cmp.get("comparacao", [])
        if isinstance(comp, list):
            cmp["comparacao"] = [
                {
                    "score_id": c.get("score_id"),
                    "razao_social": c.get("razao_social"),
                    "prioridade": c.get("prioridade"),
                    "score": c.get("score"),
                    "cnae_principal": c.get("cnae_principal"),
                    "local": c.get("local"),
                    "motivos": (c.get("motivos") or [])[:4] if isinstance(c.get("motivos"), list) else [],
                }
                for c in comp[:8]
                if isinstance(c, dict)
            ]
    rot = slim.get("gerar_roteiro_contato")
    if isinstance(rot, dict) and isinstance(rot.get("roteiro"), dict):
        roteiro = rot["roteiro"]
        rot["roteiro"] = {
            "abertura": (roteiro.get("abertura") or "")[:500],
            "argumentos_ree": (roteiro.get("argumentos_ree") or [])[:5],
            "objecoes": (roteiro.get("objecoes") or [])[:4],
            "proximo_passo": (roteiro.get("proximo_passo") or "")[:300],
        }
    # Catálogo completo aumenta muito o prompt e pouco ajuda no raciocínio final.
    slim.pop("catalogo_ferramentas", None)
    return slim


def _fontes_web_contexto(contexto: dict[str, Any]) -> list[dict[str, str]]:
    bruto = (contexto.get("busca_web") or {}).get("itens", [])
    fontes: list[dict[str, str]] = []
    for item in bruto[:5]:
        if not isinstance(item, dict):
            continue
        titulo = str(item.get("titulo") or "").strip()
        url = str(item.get("url") or "").strip()
        fonte = str(item.get("fonte") or "").strip()
        if not url:
            continue
        fontes.append({"titulo": titulo[:140], "url": url[:500], "fonte": fonte[:80]})
    return fontes


def _resumo_web_sem_modelo(consulta: str, itens_busca: list | None = None) -> str:
    """Fallback quando o modelo falha: ainda usa snippets da Serper se existirem."""
    bruto = itens_busca if isinstance(itens_busca, list) else []
    validos = [i for i in bruto if isinstance(i, dict) and (i.get("titulo") or i.get("url"))]
    if not validos:
        return "Não encontrei fontes externas válidas para esta pesquisa."
    linhas = [
        "Resumo automático (modelo indisponível nesta tentativa). Trechos vindos da busca:",
        f"Pedido: {(consulta or '').strip()[:280]}",
        "",
    ]
    for idx, item in enumerate(validos[:5], start=1):
        titulo = str(item.get("titulo") or item.get("url") or "Fonte").strip()
        sn = str(item.get("snippet") or item.get("resumo") or "").strip()
        if sn:
            linhas.append(f"{idx}) {titulo}\n   Trecho: {sn[:520]}")
        else:
            linhas.append(f"{idx}) {titulo}\n   (Sem trecho resumido na busca — confira o link nas fontes.)")
    linhas.append("")
    linhas.append("Os cards abaixo trazem os links para conferência.")
    return "\n".join(linhas).strip()


def _remover_links_texto(texto: str) -> str:
    bruto = texto or ""
    sem_urls = re.sub(r"https?://\S+", "", bruto)
    sem_www = re.sub(r"\bwww\.\S+", "", sem_urls)
    limpo = re.sub(r"\s{2,}", " ", sem_www).strip()
    return limpo


def _contexto_web_para_sintese(contexto: dict[str, Any]) -> dict[str, Any]:
    base = _contexto_para_modelo(contexto)
    bw = base.get("busca_web")
    if isinstance(bw, dict):
        itens = bw.get("itens", [])
        if isinstance(itens, list):
            bw["itens"] = [
                {
                    "titulo": i.get("titulo"),
                    "fonte": i.get("fonte"),
                    "snippet": i.get("snippet") or i.get("resumo") or "",
                }
                for i in itens[:6]
                if isinstance(i, dict)
            ]
    return base


def _sintese_web_modelo(contexto: dict[str, Any], mensagem: str) -> dict[str, Any] | None:
    resposta = provider.chamar_modelo(
        prompts.SYSTEM_OPS_WEB_RESEARCH,
        prompts.montar_prompt_ops_web_research(_contexto_web_para_sintese(contexto), mensagem),
        modelo=_modelo_tarefa("web", mensagem),
        max_tokens=_ttl("NIK_MAX_TOKENS_WEB_SYNTH", 1100),
        temperature=float(os.getenv("NIK_TEMPERATURE_WEB_SYNTH", "0.1")),
        response_format={"type": "json_object"},
    )
    if not resposta.sucesso:
        return None
    parsed = val.extrair_json_do_output(resposta.texto)
    if not parsed:
        return None
    resumo_web = parsed.get("resumo_web")
    achados = parsed.get("achados")
    por_fonte = parsed.get("por_fonte")
    tem_resumo = isinstance(resumo_web, str) and len(resumo_web.strip()) >= 30
    tem_achados = isinstance(achados, list) and len(achados) >= 1
    tem_por_fonte = isinstance(por_fonte, list) and len(por_fonte) >= 1
    if not (tem_resumo or tem_achados or tem_por_fonte):
        return None
    return parsed


def _fallback_documento_chat(mensagem: str, contexto: dict[str, Any]) -> dict[str, Any]:
    topicos = ["Contexto e objetivo", "Achados principais", "Riscos e oportunidades", "Recomendações"]
    resumo_contexto = "Documento gerado em fallback estruturado com base no contexto disponível."
    return {
        "titulo": f"Documento Nik · {mensagem[:80].strip()}",
        "sumario": topicos,
        "secoes": [
            {"titulo": "Contexto e objetivo", "conteudo": resumo_contexto},
            {"titulo": "Achados principais", "conteudo": "Os principais sinais operacionais foram consolidados a partir das ferramentas acionadas."},
            {"titulo": "Riscos e oportunidades", "conteudo": "Há oportunidade de aprofundar análise por período, parceiro e eficiência logística."},
            {"titulo": "Recomendações", "conteudo": "Validar dados críticos e executar plano de ação de curto prazo com acompanhamento semanal."},
        ],
        "conclusao": "Este documento oferece uma leitura executiva inicial e deve ser refinado com novos dados conforme necessário.",
        "proximos_passos": [
            "Revisar indicadores com o time operacional.",
            "Definir prioridades da semana com base nos riscos identificados.",
        ],
    }


def _planner_mode_resposta(contexto: dict[str, Any]) -> dict[str, str]:
    return {"planner_mode": str(contexto.get("planner_mode") or "heuristic")}


def _deterministic_ops_habilitado() -> bool:
    """Modo legado: respostas fixas sem LLM. Desligado por padrão — só cadastro de coleta permanece transacional."""
    return os.getenv("NIK_DETERMINISTIC_OPS", "false").strip().lower() in {"1", "true", "yes"}


def _grounding_estrito() -> bool:
    return os.getenv("NIK_GROUNDING_STRICT", "false").strip().lower() in {"1", "true", "yes"}


def _mensagem_pede_relatorio(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    return any(
        k in msg
        for k in [
            "relatório",
            "relatorio",
            "resumo operacional",
            "resumo da tronik",
            "resumo da operação",
            "resumo da operacao",
            "como está a operação",
            "como esta a operacao",
        ]
    )


def _fallback_conversacional(mensagem: str, contexto: dict[str, Any]) -> str:
    """Fallback que orienta ou pergunta — não manda 'reformule'."""
    consulta = contexto.get("consulta_interpretada") if isinstance(contexto.get("consulta_interpretada"), dict) else {}
    msg = (mensagem or "").lower()
    if consulta.get("periodo_nao_especificado") or (
        not consulta.get("inicio") and _mensagem_pede_relatorio(mensagem)
    ):
        return (
            "Consigo montar o relatório — só preciso do período. "
            "Quer os últimos 7 dias, o mês atual, ou um intervalo específico (ex.: janeiro a maio de 2026)?"
        )
    rp = contexto.get("resumo_periodo")
    if isinstance(rp, dict):
        resumo = rp.get("resumo") if isinstance(rp.get("resumo"), dict) else {}
        periodo = rp.get("periodo") if isinstance(rp.get("periodo"), dict) else {}
        if resumo.get("total_coletas", 0) == 0 and periodo.get("inicio"):
            return (
                f"No período de {periodo.get('inicio')} a {periodo.get('fim')} não há coletas registradas "
                f"(0 kg, 0 km). Quer ampliar o intervalo ou filtrar por parceiro?"
            )
    if any(k in msg for k in ["parceiro", "instituto", "cliente"]) and not consulta.get("parceiro_id"):
        return "Qual parceiro devo considerar? Informe o nome ou peça o consolidado de todos."
    return (
        "Não consegui fechar a resposta com os dados atuais. "
        "Pode detalhar período, parceiro ou o que exatamente quer ver (relatório, fila REE, exportação)?"
    )


def _enriquecer_orientacao_contexto(contexto: dict[str, Any], mensagem: str) -> None:
    consulta = contexto.get("consulta_interpretada")
    if not isinstance(consulta, dict):
        consulta = {}
        contexto["consulta_interpretada"] = consulta

    pede_relatorio = _mensagem_pede_relatorio(mensagem) or _mensagem_pede_exportar_csv(mensagem)
    if pede_relatorio and not consulta.get("inicio"):
        consulta["periodo_nao_especificado"] = True

    rp = contexto.get("resumo_periodo")
    if isinstance(rp, dict):
        resumo = rp.get("resumo") if isinstance(rp.get("resumo"), dict) else {}
        periodo = rp.get("periodo") if isinstance(rp.get("periodo"), dict) else {}
        if resumo.get("total_coletas") == 0:
            contexto["dados_periodo_vazio"] = {
                "periodo": periodo,
                "total_coletas": 0,
                "volume_kg": resumo.get("volume_kg", 0),
                "km_total": resumo.get("km_total", 0),
            }


def _resposta_publica(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove metadados de engenharia do payload enviado ao frontend."""
    if os.getenv("NIK_DEBUG_UI", "false").strip().lower() in {"1", "true", "yes"}:
        return payload
    publico = dict(payload)
    for chave in (
        "routing_mode",
        "routing_model",
        "planner_mode",
        "used_tools",
        "tool_trace",
        "data_sources",
        "citacoes",
    ):
        publico.pop(chave, None)
    if publico.get("texto"):
        publico["texto"] = val.sanitizar_resposta_usuario(str(publico["texto"]))
    return publico


_META_RESPOSTA_KEYS = (
    "fontes_web",
    "documento",
    "arquivo_export",
    "web_status",
    "planner_mode",
    "coleta_pendente",
    "coleta_id",
    "coletor_id",
    "used_tools",
    "tool_trace",
    "data_sources",
    "citacoes",
    "routing_mode",
    "routing_model",
    "agent_loop",
    "agent_rounds",
    "imagem",
    "import_pendente",
    "import_stats",
    "turno",
)


def _extrair_meta_resposta(payload: dict[str, Any]) -> dict[str, Any]:
    """Coleta apenas os campos ricos que valem persistir para rehidratar o histórico."""
    meta: dict[str, Any] = {"v": 1}
    for chave in _META_RESPOSTA_KEYS:
        valor = payload.get(chave)
        if valor in (None, [], {}, ""):
            continue
        meta[chave] = valor
    meta.setdefault("turno", "ops")
    return meta


def _nik_agent_loop_habilitado() -> bool:
    return os.getenv("NIK_AGENT_LOOP", "false").strip().lower() in {"1", "true", "yes"}


def _formatar_resposta_crm_ree(payload: dict[str, Any]) -> str:
    if payload.get("modo") == "global":
        linhas = [payload.get("resumo", "Cruzamento CRM ↔ REE.")]
        cruz = payload.get("cruzamentos") or []
        if cruz:
            linhas.append("\nLeads CRM com score REE:")
            for item in cruz[:12]:
                linhas.append(
                    f"- Pipeline #{item.get('pipeline_id')} ({item.get('status_crm')}): "
                    f"score REE {item.get('score_ree', '—')} ({item.get('prioridade_ree', '—')}). "
                    f"{item.get('situacao', '')}"
                )
        sem_crm = payload.get("ree_alta_prioridade_sem_crm") or []
        if sem_crm:
            linhas.append("\nAlta prioridade REE sem lead no CRM:")
            for item in sem_crm[:8]:
                linhas.append(
                    f"- {item.get('empresa', '—')}: score {item.get('score_ree', '—')} "
                    f"(rank {item.get('ranking_ree', '—')}). {item.get('situacao', '')}"
                )
        return "\n".join(linhas)
    return str(payload.get("resumo") or "Cruzamento CRM ↔ REE concluído.")


def _formatar_resposta_export_csv(payload: dict[str, Any]) -> str:
    if payload.get("status") != "ok":
        return str(payload.get("resumo") or "Não foi possível gerar o arquivo.")
    url = payload.get("download_url", "")
    return (
        f"Arquivo pronto: {payload.get('total_linhas', 0)} coleta(s) "
        f"de {payload.get('periodo', {}).get('inicio', '?')} a {payload.get('periodo', {}).get('fim', '?')}. "
        f"Baixe em {url} ({payload.get('filename', 'coletas.csv')})."
    )


def _formatar_resposta_coletor(payload: dict[str, Any]) -> str | None:
    if not payload.get("encontrado"):
        return str(payload.get("resumo") or "Coletor não encontrado.")
    return (
        f"Coletor {payload.get('id_fmt')} — {payload.get('nome', '—')} "
        f"(parceiro: {payload.get('parceiro', '—')}). "
        f"No período {payload.get('periodo', {}).get('inicio')} a {payload.get('periodo', {}).get('fim')}: "
        f"{payload.get('total_coletas', 0)} coleta(s), "
        f"volume {payload.get('volume_kg_periodo', 0)} kg, "
        f"quilometragem {payload.get('km_percorrido_km_periodo', 0)} km. "
        f"Preenchimento: {payload.get('nivel_preenchimento_pct', '—')}%."
    )


def _formatar_resposta_coleta_hoje(payload: dict[str, Any]) -> str | None:
    resumo = payload.get("resumo") if isinstance(payload.get("resumo"), dict) else {}
    periodo = payload.get("periodo") if isinstance(payload.get("periodo"), dict) else {}
    total = resumo.get("total_coletas", 0)
    vol = resumo.get("volume_kg", 0)
    km = resumo.get("km_total") or resumo.get("km_percorrido_km") or 0
    return (
        f"Coletas de hoje ({periodo.get('inicio', date.today().isoformat())}): "
        f"{total} coleta(s), {vol} kg movimentados, {km} km percorridos."
    )


def _formatar_resposta_fila_ree(payload: dict[str, Any]) -> str:
    candidatos = payload.get("candidatos") or []
    if not candidatos:
        return str(payload.get("resumo") or "Nenhum candidato REE publicado na fila.")
    linhas = [str(payload.get("resumo") or f"Top {len(candidatos)} candidato(s) REE:")]
    for idx, cand in enumerate(candidatos[:15], 1):
        if not isinstance(cand, dict):
            continue
        empresa = cand.get("empresa") if isinstance(cand.get("empresa"), dict) else {}
        nome = empresa.get("razao_social") or empresa.get("nome_fantasia") or "—"
        local = cand.get("local") if isinstance(cand.get("local"), dict) else {}
        bairro = local.get("bairro") or empresa.get("bairro") or ""
        local_txt = f" ({bairro})" if bairro else ""
        linhas.append(
            f"{idx}. {nome}{local_txt}: score {cand.get('score', '—')} "
            f"(prioridade {cand.get('prioridade', '—')}, rank {cand.get('ranking_contexto', '—')})."
        )
    return "\n".join(linhas)


def _formatar_resposta_status_modelo(payload: dict[str, Any]) -> str:
    if not payload.get("encontrado"):
        return str(payload.get("resumo") or "Nenhum modelo de prospecção ativo encontrado.")
    modelo = payload.get("modelo") if isinstance(payload.get("modelo"), dict) else {}
    metricas = payload.get("metricas") if isinstance(payload.get("metricas"), dict) else {}
    prioridade = payload.get("prioridade") if isinstance(payload.get("prioridade"), dict) else {}
    ndcg = metricas.get("validation_ndcg_mean") or metricas.get("train_ndcg_mean")
    ndcg_txt = f" NDCG validação: {ndcg:.4f}." if isinstance(ndcg, (int, float)) else ""
    pri_txt = ""
    if prioridade:
        pri_txt = (
            f" Prioridades publicadas: alta {prioridade.get('alta', 0)}, "
            f"média {prioridade.get('media', 0)}, baixa {prioridade.get('baixa', 0)}."
        )
    return (
        f"{payload.get('resumo', 'Modelo ativo.')}"
        f" Features: {modelo.get('feature_count', '—')}.{ndcg_txt}{pri_txt}"
    )


def _anexos_resposta_from_contexto(contexto: dict[str, Any]) -> dict[str, Any]:
    exp = contexto.get("exportar_coletas_csv")
    if isinstance(exp, dict) and exp.get("status") == "ok" and exp.get("download_url"):
        return {
            "arquivo_export": {
                "url": exp["download_url"],
                "filename": exp.get("filename", "coletas.csv"),
                "total_linhas": exp.get("total_linhas", 0),
                "periodo": exp.get("periodo"),
            }
        }
    return {}


def _payload_resposta_ops(base: dict[str, Any], contexto: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(base)
    if contexto:
        payload.update(_anexos_resposta_from_contexto(contexto))
    return payload


def _tentar_resposta_deterministica(mensagem: str, contexto: dict[str, Any]) -> str | None:
    """Respostas 100% ancoradas nos dados das ferramentas — sem passar pelo LLM."""
    if _mensagem_pede_exportar_csv(mensagem):
        exp = contexto.get("exportar_coletas_csv")
        if isinstance(exp, dict) and exp.get("status") == "ok":
            return _formatar_resposta_export_csv(exp)

    if _mensagem_pede_cruzar_crm_prospeccao(mensagem):
        cruz = contexto.get("cruzar_crm_prospeccao")
        if isinstance(cruz, dict) and (
            cruz.get("modo") == "global"
            or cruz.get("encontrado")
            or cruz.get("cruzamentos")
            or cruz.get("scores_prospeccao")
        ):
            return _formatar_resposta_crm_ree(cruz)

    coletor_id = _extrair_coletor_id(mensagem)
    if coletor_id is not None:
        info = contexto.get("info_coletor")
        if isinstance(info, dict):
            return _formatar_resposta_coletor(info)

    if _mensagem_pede_coleta_hoje(mensagem):
        rp = contexto.get("resumo_periodo")
        if isinstance(rp, dict):
            txt = _formatar_resposta_coleta_hoje(rp)
            if txt:
                return txt

    if _mensagem_pede_status_modelo(mensagem):
        status = contexto.get("status_modelo_prospeccao")
        if isinstance(status, dict):
            return _formatar_resposta_status_modelo(status)

    if _mensagem_pede_prospeccao(mensagem) and not _mensagem_pede_cruzar_crm_prospeccao(mensagem):
        fila = contexto.get("listar_candidatos_prospeccao")
        if isinstance(fila, dict) and isinstance(fila.get("candidatos"), list):
            return _formatar_resposta_fila_ree(fila)

    return None


def _finalizar_resposta_ops_chat(
    texto_bruto: str,
    *,
    sucesso: bool,
    modelo_usado: str | None,
    contexto: dict[str, Any],
    contexto_modelo: dict[str, Any],
    fallback: str,
    fontes_web: list[Any],
    modo_routing: str,
    modelo_planejado: str,
    thread: str,
    web_status: str,
    planner_fields: dict[str, Any],
    pediu_web: bool = False,
) -> dict[str, Any]:
    max_chars = _ttl("NIK_MAX_CHARS_WEB_RELATORIO", 7200) if pediu_web else _ttl("NIK_MAX_CHARS_CONVERSA", 3200)
    texto = val.validar_resposta_ops(
        texto_bruto if sucesso else "",
        fallback,
        max_chars=max_chars,
        preservar_paragrafos=pediu_web,
        contexto=contexto_modelo,
        grounding_estrito=_grounding_estrito(),
    )
    if fontes_web:
        texto = _remover_links_texto(texto)
    citacoes = _gerar_citacoes_por_bloco(texto, contexto)
    return _payload_resposta_ops(
        {
            "texto": texto,
            "fonte": "modelo" if sucesso and texto != fallback else "fallback",
            "modelo": modelo_usado if sucesso else None,
            "routing_mode": modo_routing,
            "routing_model": modelo_planejado,
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": citacoes,
            "fontes_web": fontes_web,
            "thread_id": thread,
            "web_status": web_status or ("ok" if fontes_web else "n/a"),
            **planner_fields,
        },
        contexto,
    )


def conversar_ops_thread(
    db: Session,
    mensagem: str,
    thread_id: str | None = None,
    usuario_id: int | None = None,
) -> dict[str, Any]:
    mensagem = (mensagem or "").strip()
    if not mensagem:
        return {"texto": "Escreva uma pergunta para a Nik.", "fonte": "sistema", "modelo": None}

    thread = _normalizar_thread_id(thread_id)
    pediu_web = _mensagem_pede_web(mensagem)
    pediu_documento = _mensagem_pede_documento(mensagem)

    from banco_dados.services import nik_coleta_chat, nik_coleta_import

    fluxo_import = nik_coleta_import.processar_mensagem_import(db, mensagem, usuario_id, thread)
    if fluxo_import:
        return {
            "texto": fluxo_import["texto"],
            "fonte": "transacional",
            "modelo": None,
            "routing_mode": "import_coletas",
            "routing_model": None,
            "modo_contexto": "real",
            "used_tools": ["import_coletas_csv"],
            "data_sources": ["import_coletas_csv"],
            "tool_trace": [{"tool": "import_coletas_csv", "status": fluxo_import.get("status"), "kwargs": {}}],
            "citacoes": [],
            "fontes_web": [],
            "thread_id": thread,
            "web_status": "n/a",
            "import_pendente": bool(fluxo_import.get("pendente")),
            "import_stats": fluxo_import.get("stats"),
            "planner_mode": "import_transacional",
        }

    fluxo_coleta = nik_coleta_chat.processar_mensagem_coleta(db, mensagem, usuario_id, thread)
    if fluxo_coleta:
        planner_fields = {"planner_mode": "coleta_transacional"}
        return {
            "texto": fluxo_coleta["texto"],
            "fonte": "transacional",
            "modelo": None,
            "routing_mode": "cadastro_coleta",
            "routing_model": None,
            "modo_contexto": "real",
            "used_tools": ["cadastro_coleta"],
            "data_sources": ["cadastro_coleta"],
            "tool_trace": [{"tool": "cadastro_coleta", "status": fluxo_coleta.get("status"), "kwargs": {}}],
            "citacoes": [],
            "fontes_web": [],
            "thread_id": thread,
            "web_status": "n/a",
            "coleta_pendente": bool(fluxo_coleta.get("pendente")),
            "coleta_id": fluxo_coleta.get("coleta_id"),
            **planner_fields,
        }

    if _nik_agent_loop_habilitado() and not pediu_web and not pediu_documento:
        from banco_dados.services import nik_agent_loop

        return nik_agent_loop.executar_loop_agente(db, mensagem, usuario_id, thread)

    contexto = _montar_contexto_conversa_integrada(db, mensagem, usuario_id=usuario_id, thread_id=thread)
    _enriquecer_orientacao_contexto(contexto, mensagem)
    planner_fields = _planner_mode_resposta(contexto)
    contexto_modelo = prompts.rotular_unidades_contexto(_contexto_para_modelo(contexto))

    if _deterministic_ops_habilitado():
        texto_det = _tentar_resposta_deterministica(mensagem, contexto)
        if texto_det:
            return _payload_resposta_ops(
                {
                    "texto": texto_det,
                    "fonte": "ferramentas",
                    "modelo": None,
                    "routing_mode": "deterministic",
                    "routing_model": None,
                    "modo_contexto": contexto.get("modo", "real"),
                    "used_tools": contexto.get("used_tools", []),
                    "data_sources": contexto.get("data_sources", []),
                    "tool_trace": contexto.get("tool_trace", []),
                    "citacoes": [],
                    "fontes_web": [],
                    "thread_id": thread,
                    "web_status": "n/a",
                    **planner_fields,
                },
                contexto,
            )

    modo_routing = "web_research_report" if pediu_web else "chat_ops"
    modelo_conversa_groq = _modelo_tarefa("conversa", mensagem)
    use_nv_chat = (
        os.getenv("NIK_CHAT_USE_NVIDIA", "").strip().lower() in {"1", "true", "yes"}
        and not pediu_web
    )
    modelo_chat_nvidia = (os.getenv("NIK_MODELO_CHAT_NVIDIA") or "nvidia/nemotron-3-super-120b-a12b").strip()
    modelo_planejado = (
        f"{_modelo_tarefa('web', mensagem)} -> {_modelo_web_writer(mensagem)}"
        if pediu_web
        else (f"{modelo_chat_nvidia} -> {modelo_conversa_groq}" if use_nv_chat else modelo_conversa_groq)
    )
    web_payload = contexto.get("busca_web") if isinstance(contexto.get("busca_web"), dict) else {}
    web_status = str((web_payload or {}).get("status") or "").strip().lower()
    web_itens = (web_payload or {}).get("itens") if isinstance(web_payload, dict) else []

    # Guardrail determinístico: quando o usuário pede internet e a tool não está operacional,
    # devolvemos status explícito sem "simular" busca.
    if pediu_web and (web_status in {"disabled", "missing_key", "rate_limited", "unsupported_provider", "error"} or not web_itens):
        mapa = {
            "disabled": "A busca na internet está desabilitada (NIK_WEB_ENABLED=false).",
            "missing_key": "A busca na internet está habilitada, mas falta configurar NIK_WEB_API_KEY.",
            "rate_limited": "A busca na internet atingiu limite temporário. Tente novamente em instantes.",
            "unsupported_provider": "O provider web configurado não é suportado nesta versão.",
            "error": "A busca na internet falhou nesta tentativa por erro de integração.",
        }
        detalhe = mapa.get(web_status, "Não encontrei fontes externas válidas para essa consulta nesta tentativa.")
        texto_web = (
            f"{detalhe} "
            "Se você quiser, eu já faço a busca assim que a integração web estiver operacional e retorno com links auditáveis."
        )
        return {
            "texto": texto_web,
            "fonte": "sistema",
            "modelo": None,
            "routing_mode": modo_routing,
            "routing_model": modelo_planejado,
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": [],
            "fontes_web": [],
            "thread_id": thread,
            "web_status": web_status or "empty",
            **planner_fields,
        }

    fontes_web = _fontes_web_contexto(contexto)
    sintese_web = _sintese_web_modelo(contexto, mensagem) if pediu_web else None
    if sintese_web:
        contexto["sintese_web"] = sintese_web
    if pediu_documento:
        resposta_doc = provider.chamar_modelo(
            prompts.SYSTEM_OPS_DOCUMENTO,
            prompts.montar_prompt_ops_documento(_contexto_para_modelo(contexto), mensagem),
            modelo=_modelo_tarefa("relatorio", mensagem),
            max_tokens=_ttl("NIK_MAX_TOKENS_DOCUMENTO", 1400),
            temperature=float(os.getenv("NIK_TEMPERATURE_DOCUMENTO", "0.2")),
            response_format={"type": "json_object"},
        )
        documento = val.validar_documento_chat(resposta_doc.texto) if resposta_doc.sucesso else None
        if not documento:
            documento = _fallback_documento_chat(mensagem, contexto)
        texto_doc = f"Documento pronto: {documento.get('titulo', 'Documento Nik')}"
        return {
            "texto": texto_doc,
            "fonte": "modelo" if resposta_doc.sucesso else "fallback",
            "modelo": resposta_doc.modelo_usado if resposta_doc.sucesso else None,
            "routing_mode": "documento",
            "routing_model": modelo_planejado if pediu_web else _modelo_tarefa("relatorio", mensagem),
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": [],
            "fontes_web": fontes_web,
            "documento": documento,
            "thread_id": thread,
            "web_status": web_status or ("ok" if fontes_web else "n/a"),
            **planner_fields,
        }

    fallback = _fallback_conversacional(mensagem, contexto)
    if pediu_web:
        resposta = provider.chamar_modelo(
            prompts.SYSTEM_OPS_RELATORIO_PESQUISA_WEB,
            prompts.montar_prompt_ops_relatorio_pesquisa_web(_contexto_para_modelo(contexto), mensagem),
            modelo=_modelo_web_writer(mensagem),
            max_tokens=_ttl("NIK_MAX_TOKENS_WEB_RELATORIO", 2400),
            temperature=float(os.getenv("NIK_TEMPERATURE_WEB_RELATORIO", os.getenv("NIK_TEMPERATURE_OPS", "0.45"))),
        )
    else:
        resposta = provider.chamar_modelo(
            prompts.SYSTEM_OPS_CONVERSA,
            prompts.montar_prompt_ops_conversa(contexto_modelo, mensagem),
            modelo=modelo_chat_nvidia if use_nv_chat else modelo_planejado,
            max_tokens=_ttl("NIK_MAX_TOKENS_CONVERSA", max(_ttl("NIK_MAX_TOKENS_OPS", 512), 420)),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.55")),
            prefer_nvidia_integrate_first=use_nv_chat,
            modelo_primario_se_sem_nv=modelo_conversa_groq if use_nv_chat else None,
        )
    if pediu_web and not resposta.sucesso and fontes_web:
        texto = _resumo_web_sem_modelo(mensagem, (contexto.get("busca_web") or {}).get("itens"))
        return {
            "texto": texto,
            "fonte": "sistema",
            "modelo": None,
            "routing_mode": modo_routing,
            "routing_model": modelo_planejado,
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": [],
            "fontes_web": fontes_web,
            "thread_id": thread,
            "web_status": web_status or "ok",
            **planner_fields,
        }

    return _finalizar_resposta_ops_chat(
        resposta.texto if resposta.sucesso else "",
        sucesso=resposta.sucesso,
        modelo_usado=resposta.modelo_usado if resposta.sucesso else None,
        contexto=contexto,
        contexto_modelo=contexto_modelo,
        fallback=fallback,
        fontes_web=fontes_web,
        modo_routing=modo_routing,
        modelo_planejado=modelo_planejado,
        thread=thread,
        web_status=web_status or ("ok" if fontes_web else "n/a"),
        planner_fields=planner_fields,
        pediu_web=pediu_web,
    )


def conversar_ops_thread_stream(
    db: Session,
    mensagem: str,
    thread_id: str | None = None,
    usuario_id: int | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Gera eventos SSE para chat ops com streaming de tokens.

    Rotas nao-streamable (import, coleta, agent loop, deterministico, web,
    documento) delegam para conversar_ops_thread() e emitem um unico done.
    """
    mensagem = (mensagem or "").strip()
    thread = _normalizar_thread_id(thread_id)
    pediu_web = _mensagem_pede_web(mensagem)
    pediu_documento = _mensagem_pede_documento(mensagem)

    from banco_dados.services import nik_coleta_chat, nik_coleta_import

    if not mensagem:
        yield {"event": "done", "data": conversar_ops_thread(db, mensagem, thread_id=thread, usuario_id=usuario_id)}
        return

    if nik_coleta_import.processar_mensagem_import(db, mensagem, usuario_id, thread):
        yield {"event": "done", "data": conversar_ops_thread(db, mensagem, thread_id=thread, usuario_id=usuario_id)}
        return

    if nik_coleta_chat.processar_mensagem_coleta(db, mensagem, usuario_id, thread):
        yield {"event": "done", "data": conversar_ops_thread(db, mensagem, thread_id=thread, usuario_id=usuario_id)}
        return

    if _nik_agent_loop_habilitado() and not pediu_web and not pediu_documento:
        yield {"event": "done", "data": conversar_ops_thread(db, mensagem, thread_id=thread, usuario_id=usuario_id)}
        return

    if pediu_web or pediu_documento:
        yield {"event": "done", "data": conversar_ops_thread(db, mensagem, thread_id=thread, usuario_id=usuario_id)}
        return

    yield {"event": "status", "data": {"phase": "context"}}
    contexto = _montar_contexto_conversa_integrada(db, mensagem, usuario_id=usuario_id, thread_id=thread)
    _enriquecer_orientacao_contexto(contexto, mensagem)
    planner_fields = _planner_mode_resposta(contexto)
    contexto_modelo = prompts.rotular_unidades_contexto(_contexto_para_modelo(contexto))

    if _deterministic_ops_habilitado():
        texto_det = _tentar_resposta_deterministica(mensagem, contexto)
        if texto_det:
            payload = _payload_resposta_ops(
                {
                    "texto": texto_det,
                    "fonte": "ferramentas",
                    "modelo": None,
                    "routing_mode": "deterministic",
                    "routing_model": None,
                    "modo_contexto": contexto.get("modo", "real"),
                    "used_tools": contexto.get("used_tools", []),
                    "data_sources": contexto.get("data_sources", []),
                    "tool_trace": contexto.get("tool_trace", []),
                    "citacoes": [],
                    "fontes_web": [],
                    "thread_id": thread,
                    "web_status": "n/a",
                    **planner_fields,
                },
                contexto,
            )
            yield {"event": "done", "data": payload}
            return

    modo_routing = "chat_ops"
    modelo_conversa_groq = _modelo_tarefa("conversa", mensagem)
    use_nv_chat = os.getenv("NIK_CHAT_USE_NVIDIA", "").strip().lower() in {"1", "true", "yes"}
    modelo_chat_nvidia = (os.getenv("NIK_MODELO_CHAT_NVIDIA") or "nvidia/nemotron-3-super-120b-a12b").strip()
    modelo_planejado = (
        f"{modelo_chat_nvidia} -> {modelo_conversa_groq}" if use_nv_chat else modelo_conversa_groq
    )
    web_payload = contexto.get("busca_web") if isinstance(contexto.get("busca_web"), dict) else {}
    web_status = str((web_payload or {}).get("status") or "").strip().lower()
    fontes_web = _fontes_web_contexto(contexto)
    fallback = _fallback_conversacional(mensagem, contexto)

    texto_bruto = ""
    sucesso = False
    modelo_usado: str | None = None

    for ev in provider.chamar_modelo_stream(
        prompts.SYSTEM_OPS_CONVERSA,
        prompts.montar_prompt_ops_conversa(contexto_modelo, mensagem),
        modelo=modelo_chat_nvidia if use_nv_chat else modelo_planejado,
        max_tokens=_ttl("NIK_MAX_TOKENS_CONVERSA", max(_ttl("NIK_MAX_TOKENS_OPS", 512), 420)),
        temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.55")),
        prefer_nvidia_integrate_first=use_nv_chat,
        modelo_primario_se_sem_nv=modelo_conversa_groq if use_nv_chat else None,
    ):
        if ev.kind == "token":
            texto_bruto += ev.texto
            yield {"event": "token", "data": {"delta": ev.texto}}
        elif ev.kind == "done":
            texto_bruto = ev.texto or texto_bruto
            sucesso = bool(texto_bruto.strip())
            modelo_usado = ev.modelo_usado or modelo_usado
        elif ev.kind == "error":
            yield {"event": "error", "data": {"erro": ev.erro or "Falha no modelo"}}
            sucesso = False
            break

    final = _finalizar_resposta_ops_chat(
        texto_bruto,
        sucesso=sucesso,
        modelo_usado=modelo_usado,
        contexto=contexto,
        contexto_modelo=contexto_modelo,
        fallback=fallback,
        fontes_web=fontes_web,
        modo_routing=modo_routing,
        modelo_planejado=modelo_planejado,
        thread=thread,
        web_status=web_status or ("ok" if fontes_web else "n/a"),
        planner_fields=planner_fields,
    )
    if final.get("texto") != texto_bruto:
        yield {"event": "replace", "data": {"texto": final["texto"], "motivo": "validacao"}}
    yield {"event": "done", "data": final}


def _extrair_anos(texto: str) -> list[int]:
    anos = re.findall(r"\b(20\d{2})\b", texto)
    return [int(a) for a in anos]


def _montar_contexto_conversa_integrada(
    db: Session,
    mensagem: str,
    usuario_id: int | None = None,
    thread_id: str = "main",
) -> dict[str, Any]:
    consulta = _inferir_consulta_usuario(db, mensagem)
    limites_hist = nik_tools.ferramenta_limites_historico(db)
    data_max = date.fromisoformat(limites_hist["fim"]) if limites_hist.get("fim") else date.today()
    if _mensagem_pede_relatorio(mensagem) and not consulta.get("inicio"):
        msg_l = (mensagem or "").lower()
        if any(k in msg_l for k in ["ultim", "recente", "hoje", "semana", "dias", "mês", "mes"]):
            consulta["inicio"] = (data_max - timedelta(days=6)).isoformat()
            consulta["fim"] = data_max.isoformat()
            consulta["periodo_inferido"] = "ultimos_7_dias"
    plano, planner_mode = _planejar_ferramentas_completo(mensagem)

    for item in plano:
        nome = item.get("nome")
        if nome == "resumo_periodo":
            if consulta.get("inicio"):
                item["kwargs"]["inicio"] = consulta["inicio"]
            if consulta.get("fim"):
                item["kwargs"]["fim"] = consulta["fim"]
            if consulta.get("parceiro_id"):
                item["kwargs"]["parceiro_id"] = consulta["parceiro_id"]
        if nome == "busca_unificada" and consulta.get("parceiro_id"):
            item["kwargs"]["parceiro_id"] = consulta["parceiro_id"]
        if nome in {"timeline_anual", "impacto_geral"}:
            if consulta.get("ano_inicio"):
                item["kwargs"]["ano_inicio"] = consulta["ano_inicio"]
            if consulta.get("ano_fim"):
                item["kwargs"]["ano_fim"] = consulta["ano_fim"]
            if consulta.get("parceiro_id"):
                item["kwargs"]["parceiro_id"] = consulta["parceiro_id"]
        if nome == "exportar_coletas_csv":
            if consulta.get("inicio"):
                item["kwargs"]["inicio"] = consulta["inicio"]
            if consulta.get("fim"):
                item["kwargs"]["fim"] = consulta["fim"]
            if consulta.get("parceiro_id"):
                item["kwargs"]["parceiro_ids"] = [consulta["parceiro_id"]]
            if consulta.get("parceiro_nomes"):
                item["kwargs"]["parceiro_nomes"] = consulta["parceiro_nomes"]
            if not item["kwargs"].get("inicio") or not item["kwargs"].get("fim"):
                item["kwargs"]["inicio"] = date(data_max.year, 1, 1).isoformat()
                item["kwargs"]["fim"] = data_max.isoformat()
        if nome == "cruzar_crm_prospeccao" and not item.get("kwargs"):
            item["kwargs"] = {"modo_global": True}

    if consulta.get("inicio") and consulta.get("fim") and not any(i.get("nome") == "resumo_periodo" for i in plano):
        plano.append({"nome": "resumo_periodo", "kwargs": {"inicio": consulta["inicio"], "fim": consulta["fim"], "parceiro_id": consulta.get("parceiro_id")}})

    contexto_exec, trace = _executar_plano_ferramentas(db, plano, usuario_id=usuario_id)
    contexto: dict[str, Any] = dict(contexto_exec)
    contexto["planner_mode"] = planner_mode
    contexto["used_tools"] = [t["tool"] for t in trace if t.get("status") == "ok"]
    contexto["data_sources"] = [t["tool"] for t in trace if t.get("status") == "ok"]
    contexto["tool_trace"] = trace
    contexto["catalogo_ferramentas"] = nik_tools.catalogo_ferramentas()
    contexto["consulta_interpretada"] = consulta
    contexto["thread_id"] = thread_id
    thread_resumo = _resumir_thread_se_necessario(db, usuario_id, thread_id)
    if thread_resumo:
        contexto["thread_resumo"] = thread_resumo
    contexto["historico_thread"] = _historico_thread(db, usuario_id, thread_id, limite=8)
    if _pedido_relatorio_ultimo_ano(mensagem):
        contexto["periodo_interpretado"] = "ultimo_ano_com_dados"
        contexto["nota_periodo"] = (
            "Quando a pergunta pede último ano, usar o último intervalo de 12 meses com dados efetivos na base."
        )
    return contexto


def salvar_conversa_ops(
    db: Session,
    usuario_id: int | None,
    pergunta: str,
    resposta_payload: dict[str, Any],
    thread_id: str | None = None,
) -> dict[str, Any]:
    texto_resposta = val.sanitizar_resposta_usuario(str(resposta_payload.get("texto", "")))
    meta = _extrair_meta_resposta(resposta_payload)
    meta_json = None
    if len(meta) > 1:  # além da chave "v"
        with contextlib.suppress(TypeError, ValueError):
            meta_json = json.dumps(meta, ensure_ascii=False)
    registro = NikConversa(
        usuario_id=usuario_id,
        thread_id=_normalizar_thread_id(thread_id),
        pergunta=(pergunta or "").strip(),
        resposta=texto_resposta,
        contexto_modo=resposta_payload.get("modo_contexto", "real"),
        modelo_usado=resposta_payload.get("modelo"),
        fonte=resposta_payload.get("fonte", "modelo"),
        meta_resposta=meta_json,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    saida = dict(resposta_payload)
    saida["historico_id"] = registro.id
    return _resposta_publica(saida)


def listar_conversas_ops(db: Session, usuario_id: int | None, limite: int = 20) -> list[dict[str, Any]]:
    q = db.query(NikConversa)
    if usuario_id is not None:
        q = q.filter(NikConversa.usuario_id == usuario_id)
    rows = q.order_by(NikConversa.criado_em.desc()).limit(max(1, min(limite, 50))).all()
    return [row.to_dict() for row in rows]


def listar_conversas_thread(
    db: Session,
    usuario_id: int | None,
    thread_id: str | None,
    limite: int = 50,
) -> list[dict[str, Any]]:
    tid = _normalizar_thread_id(thread_id)
    q = db.query(NikConversa).filter(NikConversa.thread_id == tid)
    if usuario_id is not None:
        q = q.filter(NikConversa.usuario_id == usuario_id)
    rows = q.order_by(NikConversa.criado_em.asc()).limit(max(1, min(limite, 100))).all()
    return [_resposta_publica(row.to_dict()) for row in rows]


def criar_thread_id() -> str:
    return f"chat-{secrets.token_urlsafe(8).lower()}"


def listar_threads_ops(db: Session, usuario_id: int | None, limite: int = 40) -> list[dict[str, Any]]:
    """Lista conversas (threads) do usuário com título derivado da primeira pergunta."""
    if usuario_id is None:
        return []
    limite_efetivo = max(1, min(int(limite or 40), 80))
    agregados = (
        db.query(
            NikConversa.thread_id,
            func.max(NikConversa.criado_em).label("atualizado_em"),
            func.count(NikConversa.id).label("total_mensagens"),
            func.min(NikConversa.id).label("primeira_id"),
        )
        .filter(NikConversa.usuario_id == usuario_id)
        .group_by(NikConversa.thread_id)
        .order_by(func.max(NikConversa.criado_em).desc())
        .limit(limite_efetivo)
        .all()
    )
    threads: list[dict[str, Any]] = []
    for thread_id, atualizado_em, total, primeira_id in agregados:
        titulo = str(thread_id or "main")
        if primeira_id:
            first = db.get(NikConversa, int(primeira_id))
            if first and first.pergunta:
                titulo = first.pergunta.strip()[:72]
        threads.append(
            {
                "thread_id": thread_id,
                "titulo": titulo,
                "total_mensagens": int(total or 0),
                "atualizado_em": atualizado_em.isoformat() if atualizado_em else None,
            }
        )
    return threads


def excluir_thread_ops(db: Session, usuario_id: int | None, thread_id: str) -> int:
    if usuario_id is None:
        return 0
    tid = _normalizar_thread_id(thread_id)
    removidos = (
        db.query(NikConversa)
        .filter(NikConversa.usuario_id == usuario_id, NikConversa.thread_id == tid)
        .delete(synchronize_session=False)
    )
    db.commit()
    from banco_dados.services import nik_coleta_chat, nik_coleta_import

    nik_coleta_chat._limpar_pending(usuario_id, tid)
    nik_coleta_import.limpar_pending_import(usuario_id, tid)
    return int(removidos or 0)


def excluir_mensagem_ops(db: Session, usuario_id: int | None, conversa_id: int) -> bool:
    if usuario_id is None:
        return False
    row = db.get(NikConversa, int(conversa_id))
    if not row or row.usuario_id != usuario_id:
        return False
    db.delete(row)
    db.commit()
    return True


def truncar_thread_a_partir_de(db: Session, usuario_id: int | None, conversa_id: int) -> str | None:
    """Remove a mensagem indicada e tudo que veio depois na mesma thread."""
    if usuario_id is None:
        return None
    row = db.get(NikConversa, int(conversa_id))
    if not row or row.usuario_id != usuario_id:
        return None
    tid = _normalizar_thread_id(row.thread_id)
    (
        db.query(NikConversa)
        .filter(
            NikConversa.usuario_id == usuario_id,
            NikConversa.thread_id == tid,
            NikConversa.id >= row.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    from banco_dados.services import nik_coleta_chat, nik_coleta_import

    nik_coleta_chat._limpar_pending(usuario_id, tid)
    nik_coleta_import.limpar_pending_import(usuario_id, tid)
    return tid


def _fallback_relatorio_maiara(contexto: dict[str, Any], formato: str) -> dict[str, Any]:
    resumo = contexto.get("resumo", {})
    periodo = contexto.get("periodo", {})
    top_coletor = contexto.get("top_coletor") or {}
    top_parceiro = contexto.get("top_parceiro") or {}
    eficiencia = (contexto.get("insights_base") or {}).get("eficiencia_kg_km", 0)
    metricas = [
        {
            "nome": "Total de coletas",
            "valor": str(resumo.get("total_coletas", 0)),
            "insight": "Mede o ritmo operacional do período.",
        },
        {
            "nome": "Volume coletado",
            "valor": f"{resumo.get('volume_kg', 0)} kg",
            "insight": "Indica a escala real de material movimentado.",
        },
        {
            "nome": "Quilometragem",
            "valor": f"{resumo.get('km_total', 0)} km",
            "insight": "Ajuda a avaliar custo logístico e desenho de rota.",
        },
        {
            "nome": "Eficiência kg/km",
            "valor": str(eficiencia),
            "insight": "Aproxima a relação entre massa movimentada e esforço logístico.",
        },
    ]
    titulo_prefixo = {
        "executivo": "Relatório executivo",
        "comercial": "Relatório comercial",
        "stakeholders": "Relatório para stakeholders",
    }.get(formato, "Relatório executivo")
    return {
        "titulo": f"{titulo_prefixo} Tronik · {periodo.get('inicio', '')} a {periodo.get('fim', '')}",
        "visao": formato,
        "resumo_executivo": (
            f"No período analisado, a operação registrou {resumo.get('total_coletas', 0)} coleta(s), "
            f"{resumo.get('volume_kg', 0)} kg movimentados e {resumo.get('km_total', 0)} km percorridos. "
            f"O principal coletor foi {top_coletor.get('nome', 'N/D')} e o maior volume por parceiro ficou com "
            f"{top_parceiro.get('nome', 'N/D')}. Este é um relatório estruturado baseado em dados consolidados."
        ),
        "riscos": [
            "Oscilação de volume entre parceiros pode mascarar gargalos operacionais.",
            "Quilometragem elevada sem revisão de rota pressiona margem e combustível.",
        ],
        "oportunidades": [
            "Priorizar parceiros com maior volume pode elevar eficiência de coleta.",
            "Consolidar dados por período ajuda a preparar narrativa comercial e institucional.",
        ],
        "recomendacoes": [
            "Revisar os coletores com maior recorrência de coleta e avaliar redistribuição de capacidade.",
            "Cruzar volume, quilometragem e parceiro para identificar rotas e contratos mais rentáveis.",
        ],
        "metricas_chave": metricas,
    }


def _markdown_relatorio_maiara(relatorio: dict[str, Any]) -> str:
    linhas = [
        f"# {relatorio.get('titulo', 'Relatório Nik')}",
        "",
        "## Resumo executivo",
        relatorio.get("resumo_executivo", ""),
        "",
        "## Riscos",
    ]
    for item in relatorio.get("riscos", []):
        linhas.append(f"- {item}")
    linhas.extend(["", "## Oportunidades"])
    for item in relatorio.get("oportunidades", []):
        linhas.append(f"- {item}")
    linhas.extend(["", "## Recomendações"])
    for item in relatorio.get("recomendacoes", []):
        linhas.append(f"- {item}")
    linhas.extend(["", "## Métricas-chave"])
    for item in relatorio.get("metricas_chave", []):
        linhas.append(f"- **{item.get('nome')}**: {item.get('valor')} — {item.get('insight')}")
    return "\n".join(linhas)


def gerar_relatorio_maiara(
    db: Session,
    usuario_id: int | None,
    inicio: str | None,
    fim: str | None,
    parceiro_id: int | None,
    formato: str = "executivo",
) -> dict[str, Any]:
    formato = (formato or "executivo").strip().lower()
    if formato not in {"executivo", "comercial", "stakeholders"}:
        formato = "executivo"
    contexto = ctx.contexto_relatorio(db, inicio, fim, parceiro_id)
    cache_key = (
        f"nik:maiara:{formato}:{contexto['periodo']['inicio']}:{contexto['periodo']['fim']}:{parceiro_id or 'all'}:{usuario_id or 'anon'}"
    )
    cached = _cache_get(cache_key, _ttl("NIK_CACHE_TTL_RELATORIO_OPS", 3600))
    if cached:
        return cached
    resposta = provider.chamar_modelo(
        prompts.SYSTEM_MAIARA_RELATORIO,
        prompts.montar_prompt_maiara_relatorio(contexto, formato),
        modelo=_modelo_tarefa("relatorio"),
        max_tokens=max(_ttl("NIK_MAX_TOKENS_OPS", 512), 700),
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    relatorio = (
        val.validar_relatorio_maiara(resposta.texto)
        if resposta.sucesso
        else None
    )
    if not relatorio:
        motivo = "Resposta do modelo falhou" if not resposta.sucesso else "Validação JSON falhou"
        logger.warning(
            f"Fallback relatorio_maiara acionado ({motivo}): "
            f"sucesso={resposta.sucesso}, erro={resposta.erro}, modelo={resposta.modelo_usado}"
        )
        relatorio = _fallback_relatorio_maiara(contexto, formato)
    else:
        relatorio["visao"] = formato

    markdown = _markdown_relatorio_maiara(relatorio)
    periodo_inicio = datetime.fromisoformat(contexto["periodo"]["inicio"])
    periodo_fim = datetime.combine(datetime.fromisoformat(contexto["periodo"]["fim"]).date(), time.max)

    registro = NikRelatorioGerado(
        usuario_id=usuario_id,
        parceiro_id=parceiro_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        formato=formato,
        titulo=relatorio["titulo"],
        conteudo_json=json.dumps(relatorio, ensure_ascii=False),
        conteudo_markdown=markdown,
        modelo_usado=resposta.modelo_usado if resposta.sucesso else None,
        fonte="modelo" if resposta.sucesso and val.validar_relatorio_maiara(resposta.texto) else "fallback",
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)

    resultado = {
        "id": registro.id,
        "titulo": relatorio["titulo"],
        "visao": formato,
        "conteudo": relatorio,
        "markdown": markdown,
        "fonte": registro.fonte,
        "modelo": registro.modelo_usado,
        "periodo": contexto["periodo"],
        "parceiro_id": parceiro_id,
    }
    return _cache_set(cache_key, resultado)


def obter_relatorio_maiara(
    db: Session,
    relatorio_id: int,
    *,
    usuario_id: int | None = None,
    admin: bool = False,
) -> dict[str, Any] | None:
    row = db.get(NikRelatorioGerado, relatorio_id)
    if not row:
        return None
    if usuario_id is not None and not admin and row.usuario_id != usuario_id:
        return None
    return row.to_dict()
