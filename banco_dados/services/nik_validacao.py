"""
Validacao e sanitizacao do output da Nik.
"""

from __future__ import annotations

import json
import re
from typing import Any

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)
_NUMERO_TEXTO_RE = re.compile(r"\b\d{1,3}(?:[.,]\d+)?\b")
_ANOS_PERMITIDOS = {str(y) for y in range(2020, 2036)}


def remover_emojis(texto: str) -> str:
    return _EMOJI_RE.sub("", texto or "").strip()


def sanitizar_texto(texto: str, max_chars: int = 2000, *, remover_emoji: bool = False) -> str:
    limpo = re.sub(r"<[^>]+>", "", texto or "")
    if remover_emoji:
        limpo = remover_emojis(limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) > max_chars:
        limpo = limpo[:max_chars].rsplit(" ", 1)[0].rstrip() + "..."
    return limpo


def sanitizar_texto_paragrafos(texto: str, max_chars: int = 8000) -> str:
    """Preserva quebras de linha entre blocos (relatórios web com rótulos em maiúsculas)."""
    bruto = texto or ""
    limpo = re.sub(r"<[^>]+>", "", bruto)
    blocos: list[str] = []
    for raw in limpo.replace("\r\n", "\n").split("\n"):
        linha = re.sub(r"[ \t]+", " ", raw).strip()
        if linha:
            blocos.append(linha)
    out = "\n\n".join(blocos)
    if len(out) > max_chars:
        cortado = out[:max_chars]
        ultimo = cortado.rsplit("\n\n", 1)[0].rstrip()
        out = ultimo + "\n\n…"
    return out.strip()


def extrair_json_do_output(texto: str) -> dict[str, Any] | None:
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


def _normalizar_numero(valor: Any) -> set[str]:
    out: set[str] = set()
    if valor is None:
        return out
    if isinstance(valor, bool):
        return out
    if isinstance(valor, int):
        out.add(str(valor))
        out.add(f"{valor:.1f}")
        return out
    if isinstance(valor, float):
        if valor != valor or abs(valor) == float("inf"):
            return out
        out.add(str(int(valor)) if valor == int(valor) else str(valor))
        out.add(f"{valor:.1f}".rstrip("0").rstrip("."))
        out.add(f"{valor:.2f}".rstrip("0").rstrip("."))
        return out
    if isinstance(valor, str):
        bruto = valor.strip().replace(",", ".")
        if bruto:
            out.add(bruto)
            try:
                f = float(bruto)
                out |= _normalizar_numero(f)
            except ValueError:
                pass
        return out
    return out


def extrair_numeros_contexto(contexto: Any) -> set[str]:
    """Coleta todos os números presentes no contexto JSON."""
    nums: set[str] = set()
    if isinstance(contexto, dict):
        for v in contexto.values():
            nums |= extrair_numeros_contexto(v)
    elif isinstance(contexto, list):
        for item in contexto:
            nums |= extrair_numeros_contexto(item)
    elif isinstance(contexto, (int, float, str)):
        nums |= _normalizar_numero(contexto)
    return nums


def _numero_permitido_sem_contexto(token: str) -> bool:
    if token in _ANOS_PERMITIDOS:
        return True
    try:
        n = float(token.replace(",", "."))
    except ValueError:
        return False
    return bool(n == int(n) and 0 <= int(n) <= 31)


def _numeros_por_sufixo_contexto(contexto: Any, sufixos_chave: tuple[str, ...]) -> set[str]:
    nums: set[str] = set()
    if isinstance(contexto, dict):
        for k, v in contexto.items():
            kl = str(k).lower()
            if any(s in kl for s in sufixos_chave):
                nums |= extrair_numeros_contexto(v)
            else:
                nums |= _numeros_por_sufixo_contexto(v, sufixos_chave)
    elif isinstance(contexto, list):
        for item in contexto:
            nums |= _numeros_por_sufixo_contexto(item, sufixos_chave)
    return nums


def validar_unidades_resposta(texto: str, contexto: dict[str, Any] | None) -> bool:
    """Bloqueia uso de km para valores que só existem como kg (e vice-versa)."""
    if not texto or not contexto:
        return True
    nums_kg = _numeros_por_sufixo_contexto(contexto, ("volume", "kg", "peso"))
    nums_km = _numeros_por_sufixo_contexto(contexto, ("km", "quilometr", "distanc", "meta_km"))
    for match in re.finditer(r"\b(\d{1,3}(?:[.,]\d+)?)\s*km\b", texto, flags=re.I):
        token = match.group(1).replace(",", ".")
        if (
            token not in nums_km
            and not any(token in p or p in token for p in nums_km if p)
            and (token in nums_kg or any(token in p or p in token for p in nums_kg if p))
        ):
            return False
    for match in re.finditer(r"\b(\d{1,3}(?:[.,]\d+)?)\s*kg\b", texto, flags=re.I):
        token = match.group(1).replace(",", ".")
        if (
            token not in nums_kg
            and not any(token in p or p in token for p in nums_kg if p)
            and (token in nums_km or any(token in p or p in token for p in nums_km if p))
        ):
                return False
    return True


def validar_grounding_numeros(texto: str, contexto: dict[str, Any] | None) -> bool:
    """
    True se todos os números citados na resposta existem no contexto.
    Ignora anos, dias do mês (0-31) e números de 1 dígito comuns em listas.
    """
    if not texto or not contexto:
        return True
    permitidos = extrair_numeros_contexto(contexto)
    for match in _NUMERO_TEXTO_RE.finditer(texto):
        token = match.group(0).replace(",", ".")
        if token in permitidos:
            continue
        if any(token in p or p in token for p in permitidos if len(p) >= 2):
            continue
        if _numero_permitido_sem_contexto(token):
            continue
        try:
            val = float(token)
            if val == int(val) and 1 <= int(val) <= 9:
                continue
        except ValueError:
            pass
        return False
    return True


def validar_resposta_ops(
    texto: str,
    fallback: str,
    max_chars: int = 3200,
    *,
    preservar_paragrafos: bool = False,
    contexto: dict[str, Any] | None = None,
    grounding_estrito: bool = False,
) -> str:
    if preservar_paragrafos:
        limpo = sanitizar_texto_paragrafos(texto, max_chars=max_chars)
        limpo = remover_emojis(limpo)
    else:
        limpo = sanitizar_texto(texto, max_chars=max_chars, remover_emoji=True)
    if len(limpo) < 20:
        return fallback
    if grounding_estrito and contexto is not None and not validar_unidades_resposta(limpo, contexto):
        return fallback
    if grounding_estrito and contexto is not None and not validar_grounding_numeros(limpo, contexto):
        return fallback
    return limpo


def sanitizar_resposta_usuario(texto: str) -> str:
    """Remove URLs de export internas e blocos de debug que não devem ir ao chat."""
    if not texto:
        return texto
    out = re.sub(r"/api/nik/ops/export/\S+", "", texto)
    out = re.sub(r"\n---+\n.*", "", out, flags=re.DOTALL)
    return out.strip()


def validar_resposta_landing(texto: str, tipo_bloco: str) -> dict[str, Any] | None:
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


def validar_relatorio_maiara(texto: str) -> dict[str, Any] | None:
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


def validar_documento_chat(texto: str) -> dict[str, Any] | None:
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
