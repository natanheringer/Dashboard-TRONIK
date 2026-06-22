"""Testes do fluxo transacional de cadastro de coleta via chat."""

from banco_dados.modelos import Coletor, Parceiro, TipoMaterial
from banco_dados.services import nik_coleta_chat


def _seed_coletor(db_session, nome_parceiro="Parceiro Chat Coleta"):
    tipo_material = db_session.query(TipoMaterial).first()
    parceiro = Parceiro(nome=nome_parceiro, ativo=True)
    db_session.add(parceiro)
    db_session.flush()
    coletor = Coletor(
        localizacao="Unidade Teste Chat",
        parceiro_id=parceiro.id,
        tipo_material_id=tipo_material.id if tipo_material else None,
    )
    db_session.add(coletor)
    db_session.commit()
    return parceiro, coletor


def test_detecta_intent_cadastrar_coleta():
    assert nik_coleta_chat.mensagem_pede_cadastrar_coleta(
        "Cadastra coleta do Instituto Arapoti hoje, 120 kg, 15 km"
    )


def test_fluxo_extrai_confirma_executa(db_session):
    parceiro, coletor = _seed_coletor(db_session)
    thread = "test-coleta"

    prep = nik_coleta_chat.preparar_cadastro_coleta(
        db_session,
        f"Registrar coleta para {parceiro.nome} hoje com 120 kg e 20 km no coletor L{coletor.id:03d}",
        usuario_id=1,
        thread_id=thread,
    )
    assert prep["status"] == "aguardando_confirmacao"
    assert prep["pendente"] is True
    assert "120" in prep["texto"]
    assert "CONFIRMAR" in prep["texto"]

    exec_result = nik_coleta_chat.processar_mensagem_coleta(db_session, "confirmar", 1, thread)
    assert exec_result is not None
    assert exec_result["status"] == "ok"
    assert exec_result.get("coleta_id")

    cancel = nik_coleta_chat.processar_mensagem_coleta(
        db_session,
        "Cadastra coleta 50 kg 10 km",
        1,
        "outra-thread",
    )
    assert cancel is None or cancel.get("status") != "ok"


def test_cancelar_coleta_pendente(db_session):
    parceiro, coletor = _seed_coletor(db_session, "Parceiro Cancel")
    thread = "cancel-thread"
    nik_coleta_chat.preparar_cadastro_coleta(
        db_session,
        f"Adiciona coleta {parceiro.nome} 80 kg 12 km coletor L{coletor.id:03d}",
        None,
        thread,
    )
    out = nik_coleta_chat.processar_mensagem_coleta(db_session, "cancelar", None, thread)
    assert out is not None
    assert out["status"] == "cancelado"


def test_conversar_ops_cadastro_coleta(db_session, monkeypatch):
    from banco_dados.services import nik_service

    parceiro, coletor = _seed_coletor(db_session, "Parceiro Ops Flow")
    msg = f"Cadastrar coleta {parceiro.nome} hoje 55 kg 8 km L{coletor.id:03d}"

    r1 = nik_service.conversar_ops_thread(db_session, msg, thread_id="ops-coleta", usuario_id=None)
    assert r1["routing_mode"] == "cadastro_coleta"
    assert r1["coleta_pendente"] is True

    r2 = nik_service.conversar_ops_thread(db_session, "CONFIRMAR", thread_id="ops-coleta", usuario_id=None)
    assert r2["routing_mode"] == "cadastro_coleta"
    assert r2.get("coleta_id")
