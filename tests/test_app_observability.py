"""
Testes de observabilidade (Sentry opcional) e rate limiter.
"""

import importlib

import pytest


def test_app_loads_without_sentry_dsn(monkeypatch):
    """App inicia normalmente quando SENTRY_DSN nao esta definido."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    import app as app_module

    importlib.reload(app_module)
    assert app_module.app is not None


def test_init_sentry_noop_without_dsn(monkeypatch):
    """_init_sentry nao falha nem importa sentry_sdk sem DSN."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    import app as app_module

    app_module._init_sentry()


def test_init_sentry_warns_when_sdk_missing(monkeypatch):
    """Com DSN mas sem pacote instalado, apenas registra aviso."""
    monkeypatch.setenv("SENTRY_DSN", "https://example@o0.ingest.sentry.io/0")
    import sys

    import app as app_module

    saved = sys.modules.pop("sentry_sdk", None)
    try:
        app_module._init_sentry()
    finally:
        if saved is not None:
            sys.modules["sentry_sdk"] = saved


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        ("true", True),
        ("false", False),
        ("TRUE", True),
        ("FALSE", False),
    ],
)
def test_rate_limiting_enabled_flag(monkeypatch, env_value, expected):
    from rotas.api import _limiter

    monkeypatch.setenv("RATELIMIT_ENABLED", env_value)
    assert _limiter._rate_limiting_enabled() is expected


def test_limiter_singleton_respects_enabled_env(monkeypatch):
    """O singleton reflete RATELIMIT_ENABLED no momento da criacao do modulo."""
    monkeypatch.setenv("RATELIMIT_ENABLED", "false")
    import rotas.api._limiter as limiter_mod

    importlib.reload(limiter_mod)
    assert limiter_mod.limiter.enabled is False

    monkeypatch.setenv("RATELIMIT_ENABLED", "true")
    importlib.reload(limiter_mod)
    assert limiter_mod.limiter.enabled is True
