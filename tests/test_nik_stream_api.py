"""Testes da API SSE de conversa ops da Nik."""

from __future__ import annotations

from banco_dados.services import nik_service


def test_ops_conversa_stream_sse(admin_client, monkeypatch):
    payload_final = {"texto": "Resposta stream teste", "fonte": "modelo", "modelo": "llama-test"}

    def fake_stream(db, mensagem, thread_id=None, usuario_id=None):
        yield {"event": "token", "data": {"delta": "Resposta "}}
        yield {"event": "token", "data": {"delta": "stream teste"}}
        yield {"event": "done", "data": payload_final}

    monkeypatch.setattr(nik_service, "conversar_ops_thread_stream", fake_stream)

    resp = admin_client.post(
        "/api/nik/ops/conversa",
        json={"mensagem": "Como estao os coletores?", "stream": True},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"

    body = resp.get_data(as_text=True)
    assert "event: token" in body
    assert "event: done" in body
    assert "historico_id" in body
    assert "Resposta stream teste" in body
