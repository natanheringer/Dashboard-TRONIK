"""Testes do provider Nik (streaming)."""

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


def _chunk(delta: str):
    choice = MagicMock()
    choice.delta.content = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _stream_factory(chunks):
    def create(**kwargs):
        assert kwargs.get("stream") is True
        return iter(chunks)

    return create


def test_chamar_modelo_stream_emite_tokens_e_done(monkeypatch):
    import banco_dados.services.nik_provider as np

    monkeypatch.setenv("NVIDIA_API_KEY", "gsk_test_primary")
    monkeypatch.setenv("NIK_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("NIK_MODELO_OPS", "llama-main")

    def openai_factory(**kwargs):
        client = MagicMock()
        client.chat.completions.create = _stream_factory(
            [_chunk("Ol"), _chunk("á"), _chunk("!")]
        )
        return client

    with patch.object(np, "OpenAI", side_effect=openai_factory):
        events = list(np.chamar_modelo_stream("system", "user", modelo="llama-main"))

    kinds = [e.kind for e in events]
    assert kinds == ["token", "token", "token", "done"]
    assert events[-1].texto == "Olá!"
    assert events[-1].modelo_usado == "llama-main"


def test_chamar_modelo_stream_fallback_antes_do_primeiro_token(monkeypatch):
    import banco_dados.services.nik_provider as np

    monkeypatch.setenv("NVIDIA_API_KEY", "gsk_test_primary")
    monkeypatch.setenv("NIK_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("NIK_API_FALLBACK_KEY", "nvapi_test_fallback")
    monkeypatch.setenv("NIK_API_FALLBACK_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NIK_PROVIDER_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("NIK_MODELO_OPS", "llama-main")
    monkeypatch.setenv("NIK_MODELO_FALLBACK", "llama-fallback-groq")
    monkeypatch.setenv("NIK_NVIDIA_MODELO_DEFAULT", "meta/nvidia-test-model")

    calls: list[str] = []

    def openai_factory(**kwargs):
        base = str(kwargs.get("base_url") or "")
        client = MagicMock()

        def create(**kw):
            model = str(kw.get("model") or "")
            calls.append(f"{base}|{model}")
            if "groq.com" in base:
                raise RuntimeError("Error code: 429 - rate_limit_exceeded")
            return iter([_chunk("Resposta "), _chunk("NVIDIA.")])

        client.chat.completions.create = create
        return client

    with patch.object(np, "OpenAI", side_effect=openai_factory):
        events = list(np.chamar_modelo_stream("system", "user", modelo="llama-main"))

    assert [e.kind for e in events] == ["token", "token", "done"]
    assert events[-1].texto == "Resposta NVIDIA."
    assert any("groq.com" in c for c in calls)
    assert any("integrate.api.nvidia.com" in c for c in calls)


def test_chamar_modelo_stream_nao_troca_provedor_apos_primeiro_token(monkeypatch):
    import banco_dados.services.nik_provider as np

    monkeypatch.setenv("NVIDIA_API_KEY", "gsk_test_primary")
    monkeypatch.setenv("NIK_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("NIK_MODELO_OPS", "llama-main")
    monkeypatch.setenv("NIK_MODELO_FALLBACK", "llama-fallback-groq")

    calls: list[int] = []

    def openai_factory(**kwargs):
        client = MagicMock()

        def create(**kw):
            calls.append(1)
            if len(calls) == 1:

                class BrokenStream:
                    def __iter__(self):
                        yield _chunk("Par")
                        raise RuntimeError("mid stream fail")

                return BrokenStream()
            raise AssertionError("nao deve tentar outro provedor apos token")

        client.chat.completions.create = create
        return client

    with patch.object(np, "OpenAI", side_effect=openai_factory):
        events = list(np.chamar_modelo_stream("system", "user", modelo="llama-main"))

    assert [e.kind for e in events] == ["token", "error"]
    assert len(calls) == 1
