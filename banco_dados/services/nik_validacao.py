"""
Validacao e sanitizacao do output da Nik.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def sanitizar_texto(texto: str, max_chars: int = 2000) -> str:
    limpo = re.sub(r"<[^>]+>", "", texto or "")
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) > max_chars:
        limpo = limpo[:max_chars].rsplit(" ", 1)[0].rstrip() + "..."
    return limpo


def extrair_json_do_output(texto: str) -> Optional[dict[str, Any]]:
    bruto = (texto or "").strip()
    if not bruto:
        return None
    if bruto.startswith("```"):
        bruto = re.sub(r"^```(?:json)?\s*", "", bruto)
        bruto = re.sub(r"\s*```$", "", bruto)
    try:
        parsed = json.loads(bruto)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", bruto, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def validar_resposta_ops(texto: str, fallback: str, max_chars: int = 3200) -> str:
    limpo = sanitizar_texto(texto, max_chars=max_chars)
    return limpo if len(limpo) >= 20 else fallback


def validar_resposta_landing(texto: str, tipo_bloco: str) -> Optional[dict[str, Any]]:
    parsed = extrair_json_do_output(texto)
    if not parsed:
        return None

    obrigatorios = {
        "fala_nik": ("titulo", "corpo"),
        "fato_reciclagem": ("fato",),
        "impacto_tronik": ("titulo", "metrica"),
        "pergunta_guiada": ("pergunta", "resposta_curta"),
        "nik_explica": ("titulo", "corpo"),
    }.get(tipo_bloco, ())

    for campo in obrigatorios:
        if not parsed.get(campo):
            return None

    for chave, valor in list(parsed.items()):
        if isinstance(valor, str):
            parsed[chave] = sanitizar_texto(valor, max_chars=400)
    return parsed


def validar_relatorio_maiara(texto: str) -> Optional[dict[str, Any]]:
    parsed = extrair_json_do_output(texto)
    if not parsed:
        return None

    obrigatorios = [
        "titulo",
        "visao",
        "resumo_executivo",
        "riscos",
        "oportunidades",
        "recomendacoes",
        "metricas_chave",
    ]
    for campo in obrigatorios:
        if campo not in parsed:
            return None

    for chave in ("titulo", "visao", "resumo_executivo"):
        if not isinstance(parsed.get(chave), str) or not parsed.get(chave).strip():
            return None
        parsed[chave] = sanitizar_texto(parsed[chave], max_chars=1200)

    for chave in ("riscos", "oportunidades", "recomendacoes"):
        itens = parsed.get(chave)
        if not isinstance(itens, list) or not itens:
            return None
        parsed[chave] = [sanitizar_texto(str(item), max_chars=300) for item in itens[:4]]

    metricas = parsed.get("metricas_chave")
    if not isinstance(metricas, list) or not metricas:
        return None
    metricas_sanitizadas = []
    for item in metricas[:6]:
        if not isinstance(item, dict):
            continue
        nome = sanitizar_texto(str(item.get("nome", "")), max_chars=120)
        valor = sanitizar_texto(str(item.get("valor", "")), max_chars=120)
        insight = sanitizar_texto(str(item.get("insight", "")), max_chars=240)
        if nome and valor:
            metricas_sanitizadas.append({"nome": nome, "valor": valor, "insight": insight})
    if not metricas_sanitizadas:
        return None
    parsed["metricas_chave"] = metricas_sanitizadas
    return parsed


def validar_documento_chat(texto: str) -> Optional[dict[str, Any]]:
    parsed = extrair_json_do_output(texto)
    if not parsed:
        return None
    obrigatorios = ["titulo", "sumario", "secoes", "conclusao", "proximos_passos"]
    for campo in obrigatorios:
        if campo not in parsed:
            return None
    if not isinstance(parsed.get("titulo"), str) or not parsed["titulo"].strip():
        return None
    if not isinstance(parsed.get("sumario"), list) or not parsed["sumario"]:
        return None
    if not isinstance(parsed.get("secoes"), list) or not parsed["secoes"]:
        return None
    if not isinstance(parsed.get("conclusao"), str):
        return None
    if not isinstance(parsed.get("proximos_passos"), list):
        return None

    titulo = sanitizar_texto(parsed["titulo"], max_chars=180)
    sumario = [sanitizar_texto(str(s), max_chars=120) for s in parsed["sumario"][:8] if str(s).strip()]
    secoes_sanitizadas: list[dict[str, str]] = []
    for sec in parsed["secoes"][:8]:
        if not isinstance(sec, dict):
            continue
        st = sanitizar_texto(str(sec.get("titulo", "")), max_chars=140)
        sc = sanitizar_texto(str(sec.get("conteudo", "")), max_chars=2200)
        if st and sc:
            secoes_sanitizadas.append({"titulo": st, "conteudo": sc})
    if not secoes_sanitizadas:
        return None
    conclusao = sanitizar_texto(parsed["conclusao"], max_chars=1200)
    proximos = [sanitizar_texto(str(p), max_chars=240) for p in parsed["proximos_passos"][:6] if str(p).strip()]
    if not proximos:
        proximos = ["Consolidar dados críticos e revisar plano de ação da semana."]
    return {
        "titulo": titulo,
        "sumario": sumario,
        "secoes": secoes_sanitizadas,
        "conclusao": conclusao,
        "proximos_passos": proximos,
    }
