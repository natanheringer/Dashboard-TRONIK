"""Testes do planejador LLM de ferramentas da Nik."""

from __future__ import annotations

import json
from unittest.mock import patch

from banco_dados.services import nik_agent_planner, nik_service
from banco_dados.services.nik_provider import NikResposta


def _resposta_json(plano: list[dict]) -> NikResposta:
    return NikResposta(
        texto=json.dumps({"plano": plano}),
        modelo_usado="test-model",
        tokens_prompt=10,
        tokens_resposta=20,
        latencia_ms=5,
        sucesso=True,
    )


def test_planejar_ferramentas_llm_retorna_plano_valido():
    plano_llm = [
        {"nome": "snapshot_operacional", "kwargs": {}},
        {"nome": "busca_unificada", "kwargs": {"consulta": "contratos taguatinga"}},
    ]
    with patch(
        "banco_dados.services.nik_agent_planner.provider.chamar_modelo",
        return_value=_resposta_json(plano_llm),
    ):
        out = nik_agent_planner.planejar_ferramentas_llm("quais contratos em taguatinga")
    assert out is not None
    assert [p["nome"] for p in out] == ["snapshot_operacional", "busca_unificada"]
    assert out[1]["kwargs"]["consulta"] == "contratos taguatinga"


def test_planejar_ferramentas_llm_remove_ferramentas_desconhecidas():
    plano_llm = [
        {"nome": "snapshot_operacional", "kwargs": {}},
        {"nome": "ferramenta_inexistente", "kwargs": {}},
        {"nome": "busca_unificada", "kwargs": {"consulta": "x"}},
    ]
    with patch(
        "banco_dados.services.nik_agent_planner.provider.chamar_modelo",
        return_value=_resposta_json(plano_llm),
    ):
        out = nik_agent_planner.planejar_ferramentas_llm("busque no sistema")
    assert out is not None
    nomes = [p["nome"] for p in out]
    assert "ferramenta_inexistente" not in nomes
    assert nomes == ["snapshot_operacional", "busca_unificada"]


def test_planejar_ferramentas_llm_json_invalido_retorna_none():
    resposta = NikResposta(
        texto="não é json",
        modelo_usado="test",
        tokens_prompt=1,
        tokens_resposta=1,
        latencia_ms=1,
        sucesso=True,
    )
    with patch(
        "banco_dados.services.nik_agent_planner.provider.chamar_modelo",
        return_value=resposta,
    ):
        assert nik_agent_planner.planejar_ferramentas_llm("oi") is None


def test_planejar_completo_auto_fallback_heuristic(monkeypatch):
    monkeypatch.setenv("NIK_AGENT_PLANNER", "auto")
    with patch(
        "banco_dados.services.nik_agent_planner.planejar_ferramentas_llm",
        return_value=None,
    ):
        plano, mode = nik_service._planejar_ferramentas_completo("procure contratos ativos da ceilandia")
    nomes = [p["nome"] for p in plano]
    assert "busca_unificada" in nomes
    assert mode == "auto_heuristic"


def test_planejar_completo_llm_usa_resposta_modelo(monkeypatch):
    monkeypatch.setenv("NIK_AGENT_PLANNER", "llm")
    plano_llm = [{"nome": "status_modelo_prospeccao", "kwargs": {}}]
    with patch(
        "banco_dados.services.nik_agent_planner.planejar_ferramentas_llm",
        return_value=plano_llm,
    ):
        plano, mode = nik_service._planejar_ferramentas_completo("versão do modelo de prospecção")
    assert plano == plano_llm
    assert mode == "llm"


def test_planejar_completo_heuristic_ignora_llm(monkeypatch):
    monkeypatch.setenv("NIK_AGENT_PLANNER", "heuristic")
    with patch(
        "banco_dados.services.nik_agent_planner.planejar_ferramentas_llm",
        side_effect=AssertionError("LLM não deveria ser chamado"),
    ):
        plano, mode = nik_service._planejar_ferramentas_completo("liste candidatos de prospecção")
    assert "listar_candidatos_prospeccao" in [p["nome"] for p in plano]
    assert mode == "heuristic"
