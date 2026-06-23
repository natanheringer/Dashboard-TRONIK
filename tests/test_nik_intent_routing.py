"""Testes de roteamento por intenção — gate de coleta e loop agente."""

from __future__ import annotations

import json
from unittest.mock import patch

from banco_dados.modelos import Coletor, Parceiro, TipoMaterial
from banco_dados.services import nik_agent_loop, nik_coleta_chat
from banco_dados.services.nik_provider import NikResposta, NikToolCall


def _seed_coletor(db_session, nome_parceiro="Parceiro Intent Routing"):
    tipo_material = db_session.query(TipoMaterial).first()
    parceiro = Parceiro(nome=nome_parceiro, ativo=True)
    db_session.add(parceiro)
    db_session.flush()
    coletor = Coletor(
        localizacao="Unidade Intent",
        parceiro_id=parceiro.id,
        tipo_material_id=tipo_material.id if tipo_material else None,
    )
    db_session.add(coletor)
    db_session.commit()
    return parceiro, coletor


def test_mensagem_pede_cadastrar_coleta_rejeita_falsos_positivos():
    assert not nik_coleta_chat.mensagem_pede_cadastrar_coleta(
        "me gere um relatório sobre todas as empresas cadastradas no sistema, com detalhes"
    )
    assert not nik_coleta_chat.mensagem_pede_cadastrar_coleta("liste as empresas cadastradas")
    assert not nik_coleta_chat.mensagem_pede_cadastrar_coleta("relatório de coletas do mês")


def test_mensagem_pede_cadastrar_coleta_aceita_intencao_real():
    assert nik_coleta_chat.mensagem_pede_cadastrar_coleta(
        "cadastra uma coleta de 450 kg, 28 km, parceiro Instituto X, coletor L037"
    )
    assert nik_coleta_chat.mensagem_pede_cadastrar_coleta("registrar coleta hoje")


def test_processar_mensagem_coleta_loop_ativo_nao_inicia_legacy(db_session, monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "true")
    out = nik_coleta_chat.processar_mensagem_coleta(
        db_session,
        "cadastra uma coleta de 450 kg",
        usuario_id=1,
        thread_id="intent-loop-on",
    )
    assert out is None


def test_processar_mensagem_coleta_loop_desligado_inicia_legacy(db_session, monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "false")
    out = nik_coleta_chat.processar_mensagem_coleta(
        db_session,
        "cadastra uma coleta de 450 kg",
        usuario_id=1,
        thread_id="intent-loop-off",
    )
    assert out is not None
    assert isinstance(out, dict)
    assert out["status"] in {"erro_extracao", "aguardando_confirmacao"}


def test_pending_intercept_independente_do_agent_loop(db_session, monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "true")
    parceiro, coletor = _seed_coletor(db_session, "Parceiro Pending Intent")
    thread = "pending-intent-thread"
    dados = {
        "parceiro_id": parceiro.id,
        "parceiro_nome": parceiro.nome,
        "coletor_id": coletor.id,
        "coletor_nome": coletor.localizacao,
        "volume_kg": 90.0,
        "km_percorrido_km": 11.0,
        "data_coleta": "2024-06-01",
        "preco_combustivel": 5.5,
        "tipo_operacao": "Avulsa",
    }
    nik_coleta_chat._armazenar_pending(None, thread, dados)

    cancel = nik_coleta_chat.processar_mensagem_coleta(db_session, "CANCELAR", None, thread)
    assert cancel is not None
    assert cancel["status"] == "cancelado"

    nik_coleta_chat._armazenar_pending(None, thread, dados)
    confirm = nik_coleta_chat.processar_mensagem_coleta(db_session, "CONFIRMAR", None, thread)
    assert confirm is not None
    assert confirm["status"] == "ok"
    assert confirm.get("coleta_id")


def test_preparar_cadastro_coleta_args_valido(db_session):
    parceiro, coletor = _seed_coletor(db_session, "Parceiro Args Tool")
    thread = "args-tool-thread"
    out = nik_coleta_chat.preparar_cadastro_coleta_args(
        db_session,
        usuario_id=None,
        thread_id=thread,
        parceiro_nome=parceiro.nome,
        volume_kg=450,
        km_percorrido_km=28,
        coletor_ref=f"L{coletor.id:03d}",
        data_coleta="hoje",
    )
    assert out["status"] == "aguardando_confirmacao"
    assert out["pendente"] is True
    assert nik_coleta_chat._obter_pending(None, thread) is not None

    exec_out = nik_coleta_chat.processar_mensagem_coleta(db_session, "CONFIRMAR", None, thread)
    assert exec_out is not None
    assert exec_out["status"] == "ok"


def test_preparar_cadastro_coleta_args_sem_parceiro(db_session):
    out = nik_coleta_chat.preparar_cadastro_coleta_args(
        db_session,
        usuario_id=None,
        thread_id="args-erro-thread",
        volume_kg=100,
        km_percorrido_km=10,
    )
    assert out["status"] == "erro_extracao"
    assert out["pendente"] is False


def test_agent_loop_short_circuit_cadastrar_coleta(db_session, monkeypatch):
    monkeypatch.setenv("NIK_AGENT_LOOP", "true")
    parceiro, coletor = _seed_coletor(db_session, "Parceiro Agent Short")
    thread = "agent-short-thread"
    tool_args = {
        "parceiro_nome": parceiro.nome,
        "volume_kg": 55,
        "km_percorrido_km": 8,
        "coletor_ref": f"L{coletor.id:03d}",
        "data_coleta": "hoje",
    }

    def fake_provider(*_args, **_kwargs):
        return NikResposta(
            texto="",
            modelo_usado="test-agent-model",
            tokens_prompt=5,
            tokens_resposta=3,
            latencia_ms=1,
            sucesso=True,
            tool_calls=[
                NikToolCall(
                    id="c1",
                    name="cadastrar_coleta",
                    arguments=json.dumps(tool_args),
                )
            ],
        )

    with (
        patch(
            "banco_dados.services.nik_agent_loop.provider.chamar_modelo_com_ferramentas",
            side_effect=fake_provider,
        ),
        patch("banco_dados.services.nik_service._historico_thread", return_value=[]),
    ):
        out = nik_agent_loop.executar_loop_agente(
            db_session,
            "cadastra coleta hoje",
            usuario_id=None,
            thread_id=thread,
        )

    assert out["coleta_pendente"] is True
    assert out["planner_mode"] == "coleta_transacional"
    assert out["routing_mode"] == "cadastro_coleta"
    assert nik_coleta_chat._obter_pending(None, thread) is not None
