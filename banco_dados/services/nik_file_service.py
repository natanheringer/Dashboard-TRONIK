"""
Upload e leitura de arquivos no chat Nik.

Dois modos:
  - analyze       : extrai texto de PDF/CSV e pede uma análise à Nik (não grava nada).
  - import_coletas: prepara importação de coletas a partir de CSV (preview + confirmação).

A análise NUNCA grava no banco. A importação usa coleta_service.criar_coleta()
através de nik_coleta_import (fluxo Extrai → Confirma → Executa).
"""

from __future__ import annotations

import csv
import io
import logging
import os
import secrets
from typing import Any

from banco_dados.services import nik_provider as provider
from banco_dados.utils.cache import obter_cache

logger = logging.getLogger(__name__)

NIK_ARQUIVO_MAX_BYTES = int(os.getenv("NIK_ARQUIVO_MAX_BYTES", str(8 * 1024 * 1024)))
NIK_ANALISE_MAX_CHARS = int(os.getenv("NIK_ANALISE_MAX_CHARS", "120000"))
_UPLOAD_TTL = int(os.getenv("NIK_UPLOAD_TTL", "3600"))

_EXT_PERMITIDAS = {".csv", ".pdf"}
_PREFIXOS_INJECAO = ("=", "+", "-", "@", "\t", "\r")

_SYSTEM_ANALISE_ARQUIVO = """\
Você é a Nik, assistente operacional da Tronik. Analise o conteúdo do arquivo enviado pelo operador.
Seja objetiva, em português do Brasil. Destaque números, totais, datas e qualquer inconsistência.
Se o usuário fez uma pergunta específica, responda-a com base no conteúdo. Não invente dados ausentes.\
"""


def _chave_upload(usuario_id: int | None, upload_id: str) -> str:
    uid = usuario_id if usuario_id is not None else 0
    return f"nik:upload:{uid}:{upload_id}"


def armazenar_upload(usuario_id: int | None, upload_id: str, meta: dict[str, Any]) -> None:
    obter_cache().definir(_chave_upload(usuario_id, upload_id), meta)


def obter_upload(usuario_id: int | None, upload_id: str) -> dict[str, Any] | None:
    payload = obter_cache().obter(_chave_upload(usuario_id, upload_id), _UPLOAD_TTL)
    return payload if isinstance(payload, dict) else None


def limpar_upload(usuario_id: int | None, upload_id: str) -> None:
    obter_cache().invalidar(_chave_upload(usuario_id, upload_id))


def detectar_tipo(filename: str, data: bytes) -> str | None:
    """Retorna 'pdf', 'csv' ou None com base em magic bytes + extensão."""
    nome = (filename or "").lower()
    if data[:4] == b"%PDF":
        return "pdf"
    if nome.endswith(".pdf"):
        # extensão diz pdf mas sem magic → rejeita
        return None
    if nome.endswith(".csv") or nome.endswith(".txt"):
        if _parece_texto(data):
            return "csv"
        return None
    # sem extensão reconhecida: tenta texto
    if _parece_texto(data):
        return "csv"
    return None


def _parece_texto(data: bytes) -> bool:
    amostra = data[:4096]
    if not amostra:
        return False
    if b"\x00" in amostra:
        return False
    for codec in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            amostra.decode(codec)
            return True
        except UnicodeDecodeError:
            continue
    return False


def decodificar_texto(data: bytes) -> str:
    for codec in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(codec)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def sanitizar_celula_csv(valor: str) -> str:
    """Neutraliza injeção de fórmula (CSV/Excel) prefixando aspa simples."""
    texto = (valor or "").strip()
    if texto and texto[0] in _PREFIXOS_INJECAO:
        return "'" + texto
    return texto


def extrair_texto_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf indisponível; análise de PDF desabilitada.")
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        partes: list[str] = []
        for pagina in reader.pages:
            with_text = pagina.extract_text() or ""
            if with_text:
                partes.append(with_text)
            if sum(len(p) for p in partes) > NIK_ANALISE_MAX_CHARS:
                break
        return "\n".join(partes)
    except Exception as exc:  # noqa: BLE001 - pypdf lança variados
        logger.warning("Falha ao extrair texto do PDF: %s", exc)
        return ""


def extrair_texto_csv(data: bytes) -> str:
    texto = decodificar_texto(data)
    return texto[:NIK_ANALISE_MAX_CHARS]


def ler_linhas_csv(data: bytes) -> list[dict[str, str]]:
    """Lê o CSV como lista de dicts, detectando delimitador , ou ;."""
    texto = decodificar_texto(data)
    amostra = texto[:2048]
    delim = ";" if amostra.count(";") > amostra.count(",") else ","
    reader = csv.DictReader(io.StringIO(texto), delimiter=delim)
    linhas: list[dict[str, str]] = []
    for row in reader:
        limpo = {
            (k or "").strip().lstrip("\ufeff"): (v or "").strip()
            for k, v in row.items()
            if k is not None
        }
        linhas.append(limpo)
    return linhas


def analisar_arquivo_conversa(
    *,
    texto_extraido: str,
    pergunta: str | None,
    filename: str,
) -> dict[str, Any]:
    """Pede uma análise à Nik sobre o conteúdo extraído (sem gravar nada)."""
    from banco_dados.services import nik_validacao as val

    if not texto_extraido.strip():
        return {
            "texto": (
                "Não consegui extrair texto deste arquivo. "
                "Se for um PDF digitalizado (imagem), envie como foto ou um CSV/PDF com texto."
            ),
            "fonte": "validacao",
            "modelo": None,
        }

    pergunta_txt = (pergunta or "Resuma e analise o conteúdo deste arquivo.").strip()
    user_prompt = (
        f"Arquivo: {filename}\n"
        f"Pergunta do operador: {pergunta_txt}\n\n"
        f"Conteúdo extraído:\n{texto_extraido[:NIK_ANALISE_MAX_CHARS]}"
    )
    resposta = provider.chamar_modelo(
        _SYSTEM_ANALISE_ARQUIVO,
        user_prompt,
        modelo=os.getenv("NIK_MODELO_OPS", "llama-3.1-8b-instant"),
        max_tokens=int(os.getenv("NIK_MAX_TOKENS_ARQUIVO", "900")),
        temperature=0.3,
    )
    fallback = "Não foi possível analisar o arquivo neste momento."
    texto = val.validar_resposta_ops(
        resposta.texto if resposta.sucesso else "",
        fallback,
        max_chars=int(os.getenv("NIK_MAX_CHARS_CONVERSA", "3200")),
    )
    return {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso and texto != fallback else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
        "chars_extraidos": len(texto_extraido),
    }


def novo_upload_id() -> str:
    return secrets.token_urlsafe(12)
