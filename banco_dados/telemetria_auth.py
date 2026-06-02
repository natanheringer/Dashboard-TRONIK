"""
Autenticação do endpoint POST /api/sensor/telemetria.

Ordem de verificação:
1. ``TELEMETRY_SHARED_SECRET`` (env): se definido, o campo ``api_key`` do JSON
   deve coincidir (útil na migração antes de tokens por sensor).
2. ``Sensor.api_token`` no banco: comparação em tempo constante com ``api_key``.
3. Modo relaxado só em desenvolvimento: ``TELEMETRIA_ALLOW_NO_TOKEN=true`` e
   sensor sem token configurado (não aplicável em produção).
"""

from __future__ import annotations

import os
import secrets

from banco_dados.modelos import Sensor
from banco_dados.utils.erros import ErroNaoAutorizado


def _ambiente_producao() -> bool:
    return os.getenv("FLASK_ENV", "development").strip().lower() == "production"


def _shared_secret() -> str | None:
    raw = os.getenv("TELEMETRY_SHARED_SECRET", "").strip()
    return raw or None


def _allow_no_token_dev() -> bool:
    return os.getenv("TELEMETRIA_ALLOW_NO_TOKEN", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def validar_telemetria(sensor: Sensor, api_key_payload: str | None) -> None:
    """
    Garante que a requisição pode atuar como o sensor indicado.

    Raises:
        ErroNaoAutorizado: se a autenticação falhar.
    """
    shared = _shared_secret()
    if shared is not None:
        if not api_key_payload:
            raise ErroNaoAutorizado(
                "api_key obrigatoria (TELEMETRY_SHARED_SECRET configurado no servidor)."
            )
        if not _compare_token(api_key_payload, shared):
            raise ErroNaoAutorizado("api_key invalida.")
        return

    if sensor.api_token:
        if not api_key_payload:
            raise ErroNaoAutorizado(
                "api_key obrigatoria para este sensor. Configure no firmware."
            )
        if not _compare_token(api_key_payload, sensor.api_token):
            raise ErroNaoAutorizado("api_key invalida para este sensor.")
        return

    # Sensor sem token no banco
    if _ambiente_producao():
        raise ErroNaoAutorizado(
            "Sensor sem api_token configurado. Defina token no painel ou use "
            "TELEMETRY_SHARED_SECRET durante a migracao."
        )

    if _allow_no_token_dev():
        return

    raise ErroNaoAutorizado(
        "Defina TELEMETRIA_ALLOW_NO_TOKEN=true em desenvolvimento ou configure "
        "api_token no sensor / TELEMETRY_SHARED_SECRET."
    )


def _compare_token(provided: str, stored: str) -> bool:
    """Comparação resistente a timing (exige mesmo comprimento)."""
    if not provided or not stored:
        return False
    try:
        a = provided.encode("utf-8")
        b = stored.encode("utf-8")
    except Exception:
        return False
    if len(a) != len(b):
        return False
    return secrets.compare_digest(a, b)
