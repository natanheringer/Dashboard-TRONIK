"""
Planejador de ferramentas da Nik via LLM (Michael / agent ops).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from banco_dados.services import nik_provider as provider, nik_tools, nik_validacao as val

logger = logging.getLogger(__name__)

_MAX_FERRAMENTAS = 8

_SYSTEM_TEMPLATE = """Você é o planejador operacional da Nik (Tronik).
Dada a mensagem do usuário, escolha quais ferramentas internas executar antes da resposta.
Responda SOMENTE com JSON válido no formato:
{{"plano":[{{"nome":"<ferramenta>","kwargs":{{...}}}}, ...]}}
Use APENAS nomes de ferramentas do catálogo abaixo. Omita ferramentas desnecessárias.
Mantenha kwargs mínimos (consulta, score_id, limite, prioridade, pipeline_id, etc.).
Ordene de forma lógica (snapshot_operacional costuma vir primeiro). Máximo {max_tools} ferramentas.

Catálogo permitido:
{catalogo}
"""


def _catalogo_nomes() -> set[str]:
    return {str(f.get("nome") or "").strip() for f in nik_tools.catalogo_ferramentas() if f.get("nome")}


def _montar_system_prompt() -> str:
    linhas = [
        f"- {f['nome']}: {f.get('descricao', '')}"
        for f in nik_tools.catalogo_ferramentas()
        if f.get("nome")
    ]
    return _SYSTEM_TEMPLATE.format(catalogo="\n".join(linhas), max_tools=_MAX_FERRAMENTAS)


def _normalizar_plano(raw: Any, permitidos: set[str]) -> list[dict[str, Any]] | None:
    if not isinstance(raw, list):
        return None
    out: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("nome") or "").strip()
        if not nome or nome not in permitidos or nome in vistos:
            continue
        kwargs = item.get("kwargs")
        if not isinstance(kwargs, dict):
            kwargs = {}
        vistos.add(nome)
        out.append({"nome": nome, "kwargs": dict(kwargs)})
        if len(out) >= _MAX_FERRAMENTAS:
            break
    return out if out else None


def planejar_ferramentas_llm(mensagem: str) -> list[dict[str, Any]] | None:
    """Planeja ferramentas via LLM. Retorna None em falha de API ou parse."""
    msg = (mensagem or "").strip()
    if not msg:
        return None

    permitidos = _catalogo_nomes()
    try:
        max_tokens = int(os.getenv("NIK_MAX_TOKENS_OPS", "512") or "512")
    except ValueError:
        max_tokens = 512
    try:
        temperature = float(os.getenv("NIK_TEMPERATURE_OPS", "0.2") or "0.2")
    except ValueError:
        temperature = 0.2

    resposta = provider.chamar_modelo(
        _montar_system_prompt(),
        msg,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    if not resposta.sucesso:
        logger.debug("Nik agent planner: chamada ao modelo falhou: %s", resposta.erro)
        return None

    parsed = val.extrair_json_do_output(resposta.texto)
    if not parsed:
        logger.debug("Nik agent planner: JSON inválido na resposta do modelo")
        return None

    plano_raw = parsed.get("plano")
    normalizado = _normalizar_plano(plano_raw, permitidos)
    if normalizado is None:
        logger.debug("Nik agent planner: plano vazio ou sem ferramentas válidas")
    return normalizado
