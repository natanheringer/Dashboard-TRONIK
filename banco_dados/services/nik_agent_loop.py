"""
Loop nativo de tool-calling para Nik Ops (Michael / Phase 4).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.services import (
    nik_prompts as prompts,
    nik_provider as provider,
    nik_tools,
    nik_validacao as val,
)
from banco_dados.services.nik_provider import NikResposta, NikToolCall

logger = logging.getLogger(__name__)

_SYSTEM_AGENT_LOOP = (
    prompts.SYSTEM_OPS_CONVERSA
    + """

Você pode chamar ferramentas internas da Tronik para obter dados antes de responder.
Use as ferramentas quando precisar de números, filas de prospecção, buscas ou histórico.
Quando tiver dados suficientes, responda em texto claro ao usuário (sem JSON de plano).\
"""
)


def _ttl(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)))
    except ValueError:
        return default


def _tool_calls_para_plano(tool_calls: list[NikToolCall]) -> list[dict[str, Any]]:
    plano: list[dict[str, Any]] = []
    for tc in tool_calls:
        try:
            kwargs = json.loads(tc.arguments or "{}")
        except json.JSONDecodeError:
            kwargs = {}
        if not isinstance(kwargs, dict):
            kwargs = {}
        plano.append({"nome": tc.name, "kwargs": kwargs})
    return plano


def _mensagem_assistente_com_tools(resposta: NikResposta) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "role": "assistant",
        "content": resposta.texto or None,
    }
    if resposta.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments or "{}"},
            }
            for tc in resposta.tool_calls
        ]
    return msg


def _serializar_resultado_ferramenta(saida: Any) -> str:
    try:
        return json.dumps(saida, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"resultado": str(saida)[:4000]}, ensure_ascii=False)


def executar_loop_agente(
    db: Session,
    mensagem: str,
    usuario_id: int | None,
    thread_id: str,
    max_rounds: int = 4,
) -> dict[str, Any]:
    from banco_dados.services import nik_service as svc

    mensagem = (mensagem or "").strip()
    thread = svc._normalizar_thread_id(thread_id)
    historico = svc._historico_thread(db, usuario_id, thread, limite=6)
    modelo = svc._modelo_tarefa("conversa", mensagem)
    tools = nik_tools.ferramentas_openai_schema()

    messages: list[dict[str, Any]] = []
    for h in historico[-4:]:
        pergunta = str(h.get("pergunta") or "").strip()
        resposta_hist = str(h.get("resposta") or "").strip()
        if pergunta:
            messages.append({"role": "user", "content": pergunta})
        if resposta_hist:
            messages.append({"role": "assistant", "content": resposta_hist})
    messages.append({"role": "user", "content": mensagem})

    contexto_exec: dict[str, Any] = {}
    tool_trace: list[dict[str, Any]] = []
    ultima_resposta: NikResposta | None = None
    modelo_usado: str | None = None

    for _round in range(max(1, max_rounds)):
        ultima_resposta = provider.chamar_modelo_com_ferramentas(
            _SYSTEM_AGENT_LOOP,
            messages,
            tools,
            modelo=modelo,
            max_tokens=_ttl("NIK_MAX_TOKENS_CONVERSA", max(_ttl("NIK_MAX_TOKENS_OPS", 512), 420)),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.55")),
            max_rounds=max_rounds,
        )
        if ultima_resposta.modelo_usado:
            modelo_usado = ultima_resposta.modelo_usado

        if not ultima_resposta.sucesso:
            logger.debug("Nik agent loop: modelo falhou na rodada %s: %s", _round + 1, ultima_resposta.erro)
            break

        if not ultima_resposta.tool_calls:
            break

        messages.append(_mensagem_assistente_com_tools(ultima_resposta))
        plano = _tool_calls_para_plano(ultima_resposta.tool_calls)
        ctx_round, trace_round = svc._executar_plano_ferramentas(db, plano, usuario_id=usuario_id)
        for k, v in ctx_round.items():
            contexto_exec[k] = v
        for tr in trace_round:
            tr = dict(tr)
            tr["round"] = _round + 1
            tr["agent_loop"] = True
            tool_trace.append(tr)

        resultados_por_id: dict[str, str] = {}
        for tc in ultima_resposta.tool_calls:
            nome = tc.name
            saida = contexto_exec.get(nome)
            if nome == "snapshot_operacional" and not isinstance(saida, dict):
                for val_ctx in contexto_exec.values():
                    if isinstance(val_ctx, dict) and "alertas" in val_ctx:
                        saida = val_ctx
                        break
            payload = saida if saida is not None else {"status": "sem_saida", "tool": nome}
            resultados_por_id[tc.id] = _serializar_resultado_ferramenta(payload)

        for tc in ultima_resposta.tool_calls:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": resultados_por_id.get(tc.id, "{}"),
                }
            )

    fallback = (
        "Ainda não consegui interpretar essa pergunta com confiança. "
        "Se quiser, pergunte sobre operação do dia, alertas, coletores ou o impacto geral da Tronik."
    )
    texto_bruto = (ultima_resposta.texto if ultima_resposta and ultima_resposta.sucesso else "") or ""
    sucesso_modelo = bool(ultima_resposta and ultima_resposta.sucesso and texto_bruto.strip())
    texto = val.validar_resposta_ops(
        texto_bruto if sucesso_modelo else "",
        fallback,
        max_chars=_ttl("NIK_MAX_CHARS_CONVERSA", 3200),
    )

    used_tools = [t["tool"] for t in tool_trace if t.get("status") == "ok"]
    contexto_citacoes = {
        "used_tools": used_tools,
        **dict(contexto_exec.items()),
    }
    citacoes = svc._gerar_citacoes_por_bloco(texto, contexto_citacoes)

    return {
        "texto": texto,
        "fonte": "modelo" if sucesso_modelo and texto != fallback else "fallback",
        "modelo": modelo_usado if sucesso_modelo else None,
        "routing_mode": "agent_loop",
        "routing_model": modelo_usado or modelo,
        "modo_contexto": "real",
        "used_tools": used_tools,
        "data_sources": used_tools,
        "tool_trace": tool_trace,
        "citacoes": citacoes,
        "fontes_web": [],
        "thread_id": thread,
        "web_status": "n/a",
        "planner_mode": "agent_loop",
        "agent_loop": True,
        "agent_rounds": len({t.get("round") for t in tool_trace if t.get("round")}) or (1 if sucesso_modelo else 0),
    }
