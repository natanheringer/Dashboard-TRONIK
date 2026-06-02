"""Testes do loop nativo de tool-calling da Nik Ops."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from banco_dados.services import nik_agent_loop, nik_service, nik_tools
from banco_dados.services.nik_provider import NikResposta, NikToolCall


def _resposta_com_tools(tool_calls: list[NikToolCall], texto: str = "") -> NikResposta:
    return NikResposta(
        texto=texto,
        modelo_usado="test-agent-model",
        tokens_prompt=12,
        tokens_resposta=8,
        latencia_ms=3,
        sucesso=True,
        tool_calls=tool_calls,
    )


def _resposta_texto(texto: str) -> NikResposta:
    return NikResposta(
        texto=texto,
        modelo_usado="test-agent-model",
        tokens_prompt=10,
        tokens_resposta=20,
        latencia_ms=2,
        sucesso=True,
    )


def test_ferramentas_openai_schema_inclui_catalogo():
    nomes_cat = {f["nome"] for f in nik_tools.catalogo_ferramentas()}
    nomes_schema = {t["function"]["name"] for t in nik_tools.ferramentas_openai_schema()}
    assert nomes_cat == nomes_schema
    busca = next(t for t in nik_tools.ferramentas_openai_schema() if t["function"]["name"] == "busca_unificada")
    assert "consulta" in busca["function"]["parameters"]["properties"]


def test_executar_loop_agente_executa_ferramenta_e_responde(monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "true")
    db = MagicMock()

    chamadas: list[list] = []

    def fake_provider(*_args, **kwargs):
        messages = kwargs.get("messages") if "messages" in kwargs else _args[1]
        chamadas.append(list(messages))
        if len(chamadas) == 1:
            return _resposta_com_tools(
                [
                    NikToolCall(
                        id="call_1",
                        name="snapshot_operacional",
                        arguments="{}",
                    )
                ]
            )
        return _resposta_texto("Operação estável: 2 alertas em atenção.")

    snapshot = {"alertas": [{"nivel": "atencao"}], "coletores_ativos": 4}

    with (
        patch(
            "banco_dados.services.nik_agent_loop.provider.chamar_modelo_com_ferramentas",
            side_effect=fake_provider,
        ),
        patch.object(nik_service, "_historico_thread", return_value=[]),
        patch.object(
            nik_service,
            "_executar_plano_ferramentas",
            return_value=({"snapshot_operacional": snapshot}, [{"tool": "snapshot_operacional", "status": "ok", "kwargs": {}}]),
        ),
    ):
        out = nik_agent_loop.executar_loop_agente(db, "como está a operação?", usuario_id=1, thread_id="main")

    assert out["agent_loop"] is True
    assert out["fonte"] == "modelo"
    assert "alertas" in out["texto"].lower() or "estável" in out["texto"].lower() or "Operação" in out["texto"]
    assert "snapshot_operacional" in out["used_tools"]
    assert any(t.get("tool") == "snapshot_operacional" and t.get("status") == "ok" for t in out["tool_trace"])
    assert len(chamadas) == 2
    assert any(m.get("role") == "tool" for m in chamadas[1])


def test_conversar_ops_thread_delega_para_agent_loop(monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "true")
    db = MagicMock()
    payload = {
        "texto": "Resposta via loop.",
        "fonte": "modelo",
        "modelo": "test-agent-model",
        "agent_loop": True,
        "used_tools": [],
        "tool_trace": [],
    }
    with patch(
        "banco_dados.services.nik_agent_loop.executar_loop_agente",
        return_value=payload,
    ) as mock_loop:
        out = nik_service.conversar_ops_thread(db, "status do dia", usuario_id=2, thread_id="t1")

    mock_loop.assert_called_once_with(db, "status do dia", 2, "t1")
    assert out["agent_loop"] is True
    assert out["texto"] == "Resposta via loop."


def test_conversar_ops_thread_sem_flag_mantem_caminho_classico(monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "false")
    db = MagicMock()
    with (
        patch(
            "banco_dados.services.nik_agent_loop.executar_loop_agente",
            side_effect=AssertionError("loop não deveria rodar"),
        ),
        patch.object(nik_service, "_montar_contexto_conversa_integrada", return_value={"modo": "real", "used_tools": [], "data_sources": [], "tool_trace": [], "planner_mode": "heuristic"}),
        patch(
            "banco_dados.services.nik_service.provider.chamar_modelo",
            return_value=_resposta_texto("Resposta pelo caminho clássico da Nik Ops."),
        ),
    ):
        out = nik_service.conversar_ops_thread(db, "oi", usuario_id=None, thread_id="main")

    assert out.get("agent_loop") is not True
    assert "caminho clássico" in out["texto"]
