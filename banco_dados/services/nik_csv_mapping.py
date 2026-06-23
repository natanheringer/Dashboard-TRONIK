"""
Mapeamento de colunas CSV para importação de coletas — determinístico + IA.

Camada aplicada ANTES do motor de importação existente; não altera validação/INSERT.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import unicodedata
from typing import Any

from banco_dados.services import nik_provider as provider

logger = logging.getLogger(__name__)

CANONICAL_FIELDS: frozenset[str] = frozenset(
    {
        "coletor_id",
        "parceiro_id",
        "data_hora",
        "volume_kg",
        "km_percorrido_km",
        "preco_combustivel",
        "tipo_operacao",
    }
)

OBRIGATORIOS: tuple[str, ...] = ("coletor_id", "data_hora")

_ALIASES: dict[str, list[str]] = {
    "coletor_id": [
        "coletor",
        "coletor_id",
        "id_coletor",
        "id do coletor",
        "coletor id",
        "equipamento",
        "id coletor",
    ],
    "parceiro_id": [
        "parceiro",
        "parceiro_id",
        "id_parceiro",
        "id do parceiro",
        "cliente",
        "id parceiro",
    ],
    "data_hora": [
        "data",
        "data_hora",
        "data da coleta",
        "data/hora",
        "datahora",
        "date",
        "dia",
        "data coleta",
        "datetime",
    ],
    "volume_kg": [
        "volume",
        "volume_kg",
        "peso",
        "peso (kg)",
        "peso_kg",
        "kg",
        "quantidade",
        "volume kg",
        "peso kg",
    ],
    "km_percorrido_km": [
        "km",
        "km_percorrido",
        "km_percorrido_km",
        "quilometragem",
        "distancia",
        "distância",
        "km percorrido",
        "quilometros",
        "quilômetros",
    ],
    "preco_combustivel": [
        "preco_combustivel",
        "preço combustível",
        "preco",
        "preço",
        "combustivel",
        "combustível",
        "valor combustivel",
        "valor combustível",
        "preco combustivel",
    ],
    "tipo_operacao": [
        "tipo",
        "tipo_operacao",
        "tipo de operacao",
        "tipo de operação",
        "operacao",
        "operação",
        "tipo operacao",
    ],
}

_SYSTEM_MAPEAMENTO = """\
Você mapeia cabeçalhos de CSV para campos canônicos de importação de coletas.
Responda SOMENTE com um objeto JSON válido, sem markdown nem texto extra.
Formato: {"<cabeçalho_original>": "<campo_canonico_ou_null>"}
Campos canônicos permitidos: coletor_id, parceiro_id, data_hora, volume_kg, \
km_percorrido_km, preco_combustivel, tipo_operacao.
Use null quando não houver correspondência clara.\
"""


def _normalizar_header(h: str) -> str:
    texto = (h or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    colapsado = re.sub(r"[^a-z0-9]+", "_", sem_acento)
    return colapsado.strip("_")


def _indice_aliases() -> dict[str, str]:
    indice: dict[str, str] = {}
    for canonico, aliases in _ALIASES.items():
        for alias in aliases:
            chave = _normalizar_header(alias)
            if chave not in indice:
                indice[chave] = canonico
    return indice


_ALIASES_NORM = _indice_aliases()


def ja_canonico(headers: list[str]) -> bool:
    """True se todos os cabeçalhos já são nomes canônicos (pula mapeamento)."""
    if not headers:
        return True
    return all(h in CANONICAL_FIELDS for h in headers if h)


def mapear_colunas_deterministico(headers: list[str]) -> dict[str, str]:
    """Retorna {cabeçalho_original: campo_canonico} via aliases; primeiro ganha."""
    resultado: dict[str, str] = {}
    canonico_usados: set[str] = set()

    for header in headers:
        norm = _normalizar_header(header)
        if norm in CANONICAL_FIELDS:
            alvo = norm
        elif norm in _ALIASES_NORM:
            alvo = _ALIASES_NORM[norm]
        else:
            continue
        if alvo not in canonico_usados:
            resultado[header] = alvo
            canonico_usados.add(alvo)

    return resultado


def _extrair_json_objeto(texto: str) -> dict[str, Any] | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    # Tenta parse direto
    with contextlib.suppress(json.JSONDecodeError):
        obj = json.loads(texto)
        if isinstance(obj, dict):
            return obj
    # Extrai primeiro bloco {...}
    match = re.search(r"\{[^{}]*\}", texto, re.DOTALL)
    if not match:
        return None
    with contextlib.suppress(json.JSONDecodeError):
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj
    return None


def mapear_colunas_ia(
    headers: list[str],
    mapeados_det: dict[str, str],
    amostra_linhas: list[dict[str, str]],
    *,
    max_linhas: int = 3,
) -> dict[str, str]:
    """Mapeia cabeçalhos restantes via IA; falha silenciosa retorna {}."""
    if os.getenv("NIK_CSV_IA_MAPPING", "true").lower() not in ("1", "true", "yes", "on"):
        return {}

    headers_restantes = [h for h in headers if h not in mapeados_det]
    if not headers_restantes:
        return {}

    canonico_usados = set(mapeados_det.values())
    amostra = amostra_linhas[:max_linhas]
    linhas_txt = json.dumps(amostra, ensure_ascii=False, indent=2)
    headers_txt = json.dumps(headers_restantes, ensure_ascii=False)

    user_prompt = (
        f"Cabeçalhos não mapeados: {headers_txt}\n"
        f"Campos canônicos já ocupados: {json.dumps(sorted(canonico_usados))}\n"
        f"Amostra de linhas:\n{linhas_txt}\n"
        "Retorne o JSON de mapeamento."
    )

    try:
        resposta = provider.chamar_modelo(
            _SYSTEM_MAPEAMENTO,
            user_prompt,
            modelo=os.getenv("NIK_MODELO_OPS", "llama-3.1-8b-instant"),
            max_tokens=256,
            temperature=0.0,
        )
        if not resposta.sucesso:
            logger.warning("IA mapeamento CSV: provider falhou — %s", resposta.erro)
            return {}

        bruto = _extrair_json_objeto(resposta.texto)
        if not bruto:
            logger.warning("IA mapeamento CSV: JSON inválido — %r", resposta.texto[:200])
            return {}

        resultado: dict[str, str] = {}
        for chave, valor in bruto.items():
            if chave not in headers_restantes:
                continue
            if valor is None or valor == "null":
                continue
            if not isinstance(valor, str) or valor not in CANONICAL_FIELDS:
                continue
            if valor in canonico_usados:
                continue
            resultado[chave] = valor
            canonico_usados.add(valor)

        return resultado
    except Exception:  # noqa: BLE001
        logger.warning("IA mapeamento CSV: exceção inesperada", exc_info=True)
        return {}


def resolver_mapeamento(
    headers: list[str],
    amostra_linhas: list[dict[str, str]],
) -> dict[str, Any]:
    """Orquestra mapeamento determinístico + IA."""
    mapa_det = mapear_colunas_deterministico(headers)
    mapa_ia = mapear_colunas_ia(headers, mapa_det, amostra_linhas)
    mapa = {**mapa_det, **mapa_ia}
    mapeados_canonicos = set(mapa.values())
    nao_mapeados = [h for h in headers if h not in mapa]
    faltando = [f for f in OBRIGATORIOS if f not in mapeados_canonicos]
    return {
        "mapa": mapa,
        "ia_usada": bool(mapa_ia),
        "nao_mapeados": nao_mapeados,
        "faltando_obrigatorios": faltando,
    }


def aplicar_mapeamento(
    linhas: list[dict[str, str]],
    mapa: dict[str, str],
) -> list[dict[str, str]]:
    """Re-chaveia linhas para nomes canônicos."""
    novas: list[dict[str, str]] = []
    for row in linhas:
        nova: dict[str, str] = {}
        for origem, canonico in mapa.items():
            if origem in row:
                nova[canonico] = row[origem]
        novas.append(nova)
    return novas


def resumo_mapeamento(resultado: dict[str, Any]) -> list[str]:
    """Linhas legíveis em pt-BR sobre o mapeamento aplicado."""
    linhas: list[str] = []
    mapa = resultado.get("mapa") or {}
    for origem, canonico in sorted(mapa.items(), key=lambda x: x[1]):
        linhas.append(f"{origem} → {canonico}")
    if resultado.get("ia_usada"):
        linhas.append("(Mapeamento assistido por IA)")
    faltando = resultado.get("faltando_obrigatorios") or []
    if faltando:
        linhas.append(
            f"Atenção: campos obrigatórios não identificados: {', '.join(faltando)}"
        )
    nao = resultado.get("nao_mapeados") or []
    if nao:
        linhas.append(f"Colunas ignoradas: {', '.join(nao)}")
    return linhas
