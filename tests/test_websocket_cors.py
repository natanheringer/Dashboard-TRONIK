"""Regressoes de CORS do Socket.IO."""

from rotas.websocket import _origens_socket_io


def test_socketio_padrao_aceita_mesma_origem(monkeypatch):
    monkeypatch.delenv("SOCKETIO_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://dominio-legado.example")

    assert _origens_socket_io() is None


def test_socketio_cross_origin_explicito(monkeypatch):
    monkeypatch.setenv(
        "SOCKETIO_CORS_ORIGINS",
        "https://app.example, https://admin.example",
    )

    assert _origens_socket_io() == [
        "https://app.example",
        "https://admin.example",
    ]
