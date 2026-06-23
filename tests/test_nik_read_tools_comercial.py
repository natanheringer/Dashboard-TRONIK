"""Testes das ferramentas read-only comerciais/CRM/inbox da Nik."""

from datetime import timedelta

from banco_dados.modelos import (
    Interacao,
    MetaComercial,
    Notificacao,
    Pipeline,
    SolicitacaoColetor,
    Tarefa,
    Usuario,
)
from banco_dados.services import nik_service, nik_tools
from banco_dados.utils import utc_now_naive

SENSITIVE_KEYS = {"senha_hash", "api_token"}


def _assert_no_sensitive_keys(obj, path=""):
    if isinstance(obj, dict):
        for key, val in obj.items():
            assert key not in SENSITIVE_KEYS, f"chave sensível vazou em {path}.{key}"
            _assert_no_sensitive_keys(val, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_sensitive_keys(item, f"{path}[{i}]")


def _seed_comercial(db_session, create_lixeira):
    usuario = Usuario(
        username="crm_nik_test",
        email="crm_nik_test@test.local",
        nome_completo="Comercial Nik Test",
        ativo=True,
        admin=True,
    )
    usuario.set_senha("CrmNik123!")
    db_session.add(usuario)
    db_session.flush()

    coletor = create_lixeira(localizacao="Empresa Pipeline Teste")
    pipeline = Pipeline(
        coletor_id=coletor.id,
        status="negociacao",
        valor_estimado=15000.0,
        probabilidade=75,
        proxima_acao="Enviar proposta revisada",
        responsavel_id=usuario.id,
    )
    db_session.add(pipeline)
    db_session.flush()

    tarefa_aberta = Tarefa(
        titulo="Follow-up proposta",
        pipeline_id=pipeline.id,
        usuario_id=usuario.id,
        status="pendente",
        data_vencimento=utc_now_naive() + timedelta(days=3),
    )
    tarefa_fechada = Tarefa(
        titulo="Tarefa concluída antiga",
        pipeline_id=pipeline.id,
        usuario_id=usuario.id,
        status="concluida",
        data_vencimento=utc_now_naive() - timedelta(days=10),
    )
    db_session.add_all([tarefa_aberta, tarefa_fechada])

    interacao = Interacao(
        pipeline_id=pipeline.id,
        tipo="ligacao",
        descricao="Cliente pediu revisão de valores",
        usuario_id=usuario.id,
        data=utc_now_naive(),
    )
    db_session.add(interacao)

    notif_lida = Notificacao(
        tipo="lixeira_cheia",
        titulo="Coletor cheio",
        mensagem="Nível acima de 90%",
        coletor_id=coletor.id,
        lida=True,
        criada_em=utc_now_naive(),
    )
    notif_nao_lida = Notificacao(
        tipo="bateria_baixa",
        titulo="Bateria baixa",
        mensagem="Sensor abaixo de 20%",
        coletor_id=coletor.id,
        lida=False,
        criada_em=utc_now_naive(),
    )
    db_session.add_all([notif_lida, notif_nao_lida])

    solicitacao = SolicitacaoColetor(
        nome="Lead Landing",
        email="lead@example.com",
        localizacao="Brasília",
        status="pendente",
        criado_em=utc_now_naive(),
    )
    db_session.add(solicitacao)

    meta = MetaComercial(
        mes=6,
        ano=2026,
        valor_meta=12000.0,
        valor_realizado=3000.0,
        percentual_atingido=25.0,
        status="em_andamento",
    )
    db_session.add(meta)
    db_session.commit()

    return {
        "usuario": usuario,
        "coletor": coletor,
        "pipeline": pipeline,
        "tarefa_aberta": tarefa_aberta,
        "tarefa_fechada": tarefa_fechada,
        "interacao": interacao,
        "notif_lida": notif_lida,
        "notif_nao_lida": notif_nao_lida,
        "solicitacao": solicitacao,
        "meta": meta,
    }


def test_listar_pipeline_retorna_deal_seed(db_session, create_lixeira):
    seed = _seed_comercial(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_pipeline(db_session, status="negociacao", limite=20)
    ids = {d["id"] for d in out["deals"]}
    assert seed["pipeline"].id in ids
    deal = next(d for d in out["deals"] if d["id"] == seed["pipeline"].id)
    assert deal["empresa"] == seed["coletor"].localizacao
    assert deal["status"] == "negociacao"
    assert deal["valor_estimado"] == 15000.0
    assert deal["probabilidade"] == 75
    assert deal["proxima_acao"] == "Enviar proposta revisada"
    assert deal["responsavel"] == seed["usuario"].nome_completo
    assert "resumo" in out
    _assert_no_sensitive_keys(out)


def test_listar_tarefas_comerciais_default_abertas(db_session, create_lixeira):
    seed = _seed_comercial(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_tarefas_comerciais(db_session, limite=20)
    ids = {t["id"] for t in out["tarefas"]}
    assert seed["tarefa_aberta"].id in ids
    assert seed["tarefa_fechada"].id not in ids
    tarefa = next(t for t in out["tarefas"] if t["id"] == seed["tarefa_aberta"].id)
    assert tarefa["titulo"] == "Follow-up proposta"
    assert tarefa["status"] == "pendente"
    assert tarefa["pipeline_id"] == seed["pipeline"].id
    assert tarefa["empresa"] == seed["coletor"].localizacao
    _assert_no_sensitive_keys(out)


def test_interacoes_pipeline_timeline(db_session, create_lixeira):
    seed = _seed_comercial(db_session, create_lixeira)
    out = nik_tools.ferramenta_interacoes_pipeline(
        db_session,
        pipeline_id=seed["pipeline"].id,
        limite=20,
    )
    assert out["encontrado"] is True
    assert out["pipeline_id"] == seed["pipeline"].id
    assert out["total"] >= 1
    item = out["interacoes"][0]
    assert item["tipo"] == "ligacao"
    assert "revisão" in item["descricao"]
    assert item["autor"] == seed["usuario"].nome_completo
    assert "data" in item
    _assert_no_sensitive_keys(out)


def test_interacoes_pipeline_sem_id(db_session):
    out = nik_tools.ferramenta_interacoes_pipeline(db_session)
    assert out["encontrado"] is False


def test_listar_notificacoes_e_filtro_nao_lidas(db_session, create_lixeira):
    seed = _seed_comercial(db_session, create_lixeira)
    todas = nik_tools.ferramenta_listar_notificacoes(db_session, limite=20)
    assert todas["total"] >= 2
    assert all("titulo" in n for n in todas["notificacoes"])
    assert all("lida" in n for n in todas["notificacoes"])

    nao_lidas = nik_tools.ferramenta_listar_notificacoes(db_session, lida=False, limite=20)
    ids = {n["id"] for n in nao_lidas["notificacoes"]}
    assert seed["notif_nao_lida"].id in ids
    assert seed["notif_lida"].id not in ids
    assert all(n["lida"] is False for n in nao_lidas["notificacoes"])
    _assert_no_sensitive_keys(todas)
    _assert_no_sensitive_keys(nao_lidas)


def test_listar_solicitacoes_com_email(db_session, create_lixeira):
    seed = _seed_comercial(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_solicitacoes(db_session, status="pendente", limite=20)
    row = next(s for s in out["solicitacoes"] if s["id"] == seed["solicitacao"].id)
    assert row["nome"] == "Lead Landing"
    assert row["email"] == "lead@example.com"
    assert row["status"] == "pendente"
    assert row["criado_em"] is not None
    _assert_no_sensitive_keys(out)


def test_meta_comercial_com_meta_configurada(db_session, create_lixeira):
    _seed_comercial(db_session, create_lixeira)
    out = nik_tools.ferramenta_meta_comercial(db_session, mes="2026-06")
    assert out["status"] == "ok"
    assert out["mes"] == "2026-06"
    assert out["valor_meta"] == 12000.0
    assert out["valor_realizado"] == 3000.0
    assert out["percentual_atingido"] == 25.0
    assert out["falta_para_meta"] == 9000.0
    _assert_no_sensitive_keys(out)


def test_meta_comercial_indisponivel_sem_meta(db_session):
    out = nik_tools.ferramenta_meta_comercial(db_session, mes="1999-01")
    assert out["status"] == "indisponivel"
    assert out["mes"] == "1999-01"


def test_planner_pipeline_negociacao():
    plano = nik_service._planejar_ferramentas("mostre o pipeline de negociação")
    assert "listar_pipeline" in [p["nome"] for p in plano]


def test_planner_notificacoes_nao_lidas():
    plano = nik_service._planejar_ferramentas("quais notificações não lidas")
    item = next(p for p in plano if p["nome"] == "listar_notificacoes")
    assert item["kwargs"].get("lida") is False


def test_planner_meta_comercial():
    plano = nik_service._planejar_ferramentas("quanto falta pra meta do mês")
    assert "meta_comercial" in [p["nome"] for p in plano]


def test_planner_solicitacoes_coletor():
    plano = nik_service._planejar_ferramentas("liste as solicitações de coletor")
    assert "listar_solicitacoes" in [p["nome"] for p in plano]
