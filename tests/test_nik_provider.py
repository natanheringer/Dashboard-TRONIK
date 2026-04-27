"""Testes do provider Nik (fallback de provedor)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_provider_globals():
    import banco_dados.services.nik_provider as np

    np._RATE_LIMIT_UNTIL_TS_PRIMARY = 0.0
    with np._client_lock:
        np._openai_clients.clear()
    yield
    np._RATE_LIMIT_UNTIL_TS_PRIMARY = 0.0
    with np._client_lock:
        np._openai_clients.clear()


def test_chamar_modelo_usa_nvidia_quando_groq_falha(monkeypatch):
    import banco_dados.services.nik_provider as np

    monkeypatch.setenv("NVIDIA_API_KEY", "gsk_test_primary")
    monkeypatch.setenv("NIK_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("NIK_API_FALLBACK_KEY", "nvapi_test_fallback")
    monkeypatch.setenv("NIK_API_FALLBACK_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NIK_PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("NIK_MODELO_OPS", "llama-main")
    monkeypatch.setenv("NIK_MODELO_FALLBACK", "llama-fallback-groq")
    monkeypatch.setenv("NIK_NVIDIA_MODELO_DEFAULT", "meta/nvidia-test-model")

    calls: list[tuple[str, str, str]] = []

    def openai_factory(**kwargs):
        base = str(kwargs.get("base_url") or "")
        api_key = str(kwargs.get("api_key") or "")
        client = MagicMock()

        def create(**kw):
            model = str(kw.get("model") or "")
            calls.append((base, api_key[:12], model))
            if "groq.com" in base:
                raise RuntimeError("Error code: 429 - rate_limit_exceeded")
            msg = MagicMock()
            msg.content = "Resposta via NVIDIA."
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            resp.usage = MagicMock(prompt_tokens=3, completion_tokens=2)
            return resp

        client.chat.completions.create = create
        return client

    with patch.object(np, "OpenAI", side_effect=openai_factory):
        r = np.chamar_modelo("system", "user", modelo="llama-main", max_tokens=64, temperature=0.2)

    assert r.sucesso
    assert "NVIDIA" in r.texto
    assert r.modelo_usado == "meta/nvidia-test-model"
    assert any("groq.com" in c[0] for c in calls)
    assert any("integrate.api.nvidia.com" in c[0] for c in calls)


def test_is_transient_network_error():
    import banco_dados.services.nik_provider as np

    assert np._is_transient_network_error("ReadTimeout: HTTPSConnectionPool")
    assert np._is_transient_network_error("Connection reset by peer")
    assert not np._is_transient_network_error("Error code: 429 - rate_limit_exceeded")


def test_chamar_modelo_nemotron_integrate_antes_do_groq(monkeypatch):
    """Com prefer_nvidia_integrate_first, tenta integrate primeiro; Groq só no fallback."""
    import banco_dados.services.nik_provider as np

    monkeypatch.setenv("NVIDIA_API_KEY", "gsk_test_primary")
    monkeypatch.setenv("NIK_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("NIK_NVAPI_KEY", "nvapi_test_integrate")
    monkeypatch.setenv("NIK_NVIDIA_INTEGRATE_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NIK_MODELO_OPS", "llama-groq")
    monkeypatch.setenv("NIK_MODELO_FALLBACK", "llama-fallback-groq")

    calls: list[tuple[str, str]] = []

    def openai_factory(**kwargs):
        base = str(kwargs.get("base_url") or "")
        api_key = str(kwargs.get("api_key") or "")
        client = MagicMock()

        def create(**kw):
            model = str(kw.get("model") or "")
            calls.append((base, model))
            if "integrate.api.nvidia.com" in base and "nemotron" in model:
                msg = MagicMock()
                msg.content = "Resposta Nemotron."
                choice = MagicMock()
                choice.message = msg
                resp = MagicMock()
                resp.choices = [choice]
                resp.usage = MagicMock(prompt_tokens=2, completion_tokens=3)
                return resp
            raise RuntimeError("groq should not run when Nemotron succeeds")

        client.chat.completions.create = create
        return client

    with patch.object(np, "OpenAI", side_effect=openai_factory):
        r = np.chamar_modelo(
            "system",
            "user",
            modelo="nvidia/nemotron-3-super-120b-a12b",
            max_tokens=64,
            temperature=0.2,
            prefer_nvidia_integrate_first=True,
            modelo_primario_se_sem_nv="llama-groq",
        )

    assert r.sucesso
    assert "Nemotron" in r.texto
    assert r.modelo_usado == "nvidia/nemotron-3-super-120b-a12b"
    assert len(calls) == 1
    assert "integrate.api.nvidia.com" in calls[0][0]


def test_nvidia_integrate_aceita_somente_nvidia_api_key_nvapi(monkeypatch):
    import banco_dados.services.nik_provider as np

    monkeypatch.delenv("NIK_NVAPI_KEY", raising=False)
    monkeypatch.delenv("NIK_NVIDIA_INTEGRATE_API_KEY", raising=False)
    monkeypatch.delenv("NIK_API_FALLBACK_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-for-integrate")
    monkeypatch.setenv("NIK_NVIDIA_INTEGRATE_BASE_URL", "https://integrate.api.nvidia.com/v1")

    assert np._nvidia_integrate_ok()
    assert np._nvidia_integrate_api_key() == "nvapi-test-key-for-integrate"


def test_fallback_provedor_desligado_nao_chama_nvidia(monkeypatch):
    import banco_dados.services.nik_provider as np

    monkeypatch.setenv("NVIDIA_API_KEY", "gsk_test_primary")
    monkeypatch.setenv("NIK_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("NIK_API_FALLBACK_KEY", "nvapi_test_fallback")
    monkeypatch.setenv("NIK_API_FALLBACK_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NIK_PROVIDER_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("NIK_MODELO_OPS", "llama-main")
    monkeypatch.setenv("NIK_MODELO_FALLBACK", "llama-fallback-groq")

    calls: list[str] = []

    def openai_factory(**kwargs):
        base = str(kwargs.get("base_url") or "")
        client = MagicMock()

        def create(**kw):
            calls.append(base)
            raise RuntimeError("Error code: 429 - rate_limit_exceeded")

        client.chat.completions.create = create
        return client

    with patch.object(np, "OpenAI", side_effect=openai_factory):
        r = np.chamar_modelo("system", "user", modelo="llama-main")

    assert not r.sucesso
    assert all("groq.com" in b for b in calls)
    assert not any("nvidia" in b for b in calls)
