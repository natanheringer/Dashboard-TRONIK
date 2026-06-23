"""Testes das ferramentas read-only operacionais da Nik."""

from datetime import datetime, timedelta

from banco_dados.modelos import Coleta, Parceiro, Sensor, TipoSensor, TronikScore
from banco_dados.services import nik_service, nik_tools
from banco_dados.utils import utc_now_naive


def _seed_operacional(db_session, create_lixeira):
    parceiro = Parceiro(nome="Parceiro Ops Nik")
    db_session.add(parceiro)
    db_session.flush()

    coletor_recente = create_lixeira(
        localizacao="Coletor Recente",
        parceiro_id=parceiro.id,
    )
    coletor_parado = create_lixeira(
        localizacao="Coletor Parado",
        parceiro_id=parceiro.id,
    )
    coletor_parado.ultima_coleta = utc_now_naive() - timedelta(days=20)
    db_session.add(coletor_parado)

    tipo = db_session.query(TipoSensor).first()
    if not tipo:
        tipo = TipoSensor(nome="Ultrassom Teste")
        db_session.add(tipo)
        db_session.flush()

    sensor = Sensor(
        coletor_id=coletor_recente.id,
        tipo_sensor_id=tipo.id,
        bateria=15.0,
        ultimo_ping=utc_now_naive(),
        api_token="secret-token-never-expose",
    )
    db_session.add(sensor)

    coleta = Coleta(
        coletor_id=coletor_recente.id,
        parceiro_id=parceiro.id,
        data_hora=datetime(2026, 2, 10, 12, 0, 0),
        volume_estimado=120.0,
        km_percorrido=8.5,
        tipo_operacao="Avulsa",
    )
    db_session.add(coleta)
    db_session.commit()
    db_session.refresh(coletor_recente)
    db_session.refresh(coletor_parado)
    db_session.refresh(sensor)
    db_session.refresh(coleta)
    return {
        "parceiro": parceiro,
        "coletor_recente": coletor_recente,
        "coletor_parado": coletor_parado,
        "sensor": sensor,
        "coleta": coleta,
    }


def test_listar_coletores_encontra_seed(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_coletores(db_session, limite=50)
    ids = {c["id"] for c in out["coletores"]}
    assert seed["coletor_recente"].id in ids
    assert seed["coletor_parado"].id in ids
    assert out["total"] >= 2
    assert "resumo" in out


def test_listar_coletores_filtro_sem_coleta_dias(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_coletores(db_session, sem_coleta_dias=14, limite=50)
    ids = {c["id"] for c in out["coletores"]}
    assert seed["coletor_parado"].id in ids
    assert seed["coletor_recente"].id not in ids
    assert out["coletores"][0]["dias_sem_coleta"] >= 14


def test_status_sensores_sem_api_token(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    out = nik_tools.ferramenta_status_sensores(db_session, coletor_id=seed["coletor_recente"].id)
    assert out["total"] == 1
    sensor = out["sensores"][0]
    assert "api_token" not in sensor
    assert sensor["bateria"] == 15.0
    assert sensor["coletor"]["id"] == seed["coletor_recente"].id


def test_status_sensores_filtro_bateria(db_session, create_lixeira):
    _seed_operacional(db_session, create_lixeira)
    out = nik_tools.ferramenta_status_sensores(db_session, bateria_max=20)
    assert out["total"] >= 1
    assert all(s["bateria"] <= 20 for s in out["sensores"])


def test_historico_coletas_paginacao(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    out = nik_tools.ferramenta_historico_coletas(
        db_session,
        parceiro_id=seed["parceiro"].id,
        pagina=1,
        por_pagina=20,
    )
    assert out["total"] >= 1
    assert out["pagina"] == 1
    assert out["total_paginas"] >= 1
    linha = out["coletas"][0]
    assert linha["volume_kg"] == 120.0
    assert linha["km"] == 8.5
    assert linha["tipo_operacao"] == "Avulsa"
    assert linha["parceiro_nome"] == seed["parceiro"].nome


def test_ml_coletor_indisponivel_sem_dados(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    out = nik_tools.ferramenta_ml_coletor(db_session, coletor_id=seed["coletor_recente"].id)
    assert out["status"] in {"indisponivel", "ok"}
    assert out["coletor_id"] == seed["coletor_recente"].id
    assert "resumo" in out


def test_ml_coletor_com_score(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    db_session.add(
        TronikScore(
            coletor_id=seed["coletor_recente"].id,
            score=88.5,
            modelo_usado="heuristica",
            calculado_em=utc_now_naive(),
        )
    )
    db_session.commit()
    out = nik_tools.ferramenta_ml_coletor(db_session, coletor_id=seed["coletor_recente"].id)
    assert out["status"] == "ok"
    assert out["tronik_score"]["score"] == 88.5


def test_ranking_ml_vazio(db_session):
    out = nik_tools.ferramenta_ranking_ml(db_session, limite=5)
    assert out["status"] == "indisponivel"
    assert out["ranking"] == []


def test_ranking_ml_com_scores(db_session, create_lixeira):
    seed = _seed_operacional(db_session, create_lixeira)
    db_session.add(
        TronikScore(
            coletor_id=seed["coletor_recente"].id,
            score=91.0,
            modelo_usado="heuristica",
            calculado_em=utc_now_naive(),
        )
    )
    db_session.commit()
    out = nik_tools.ferramenta_ranking_ml(db_session, limite=5)
    assert out["status"] == "ok"
    assert out["total"] >= 1
    assert out["ranking"][0]["coletor_id"] == seed["coletor_recente"].id


def test_planner_listar_coletores_sem_coleta():
    plano = nik_service._planejar_ferramentas("liste os coletores sem coleta há 14 dias")
    nomes = [p["nome"] for p in plano]
    assert "listar_coletores" in nomes
    item = next(p for p in plano if p["nome"] == "listar_coletores")
    assert item["kwargs"].get("sem_coleta_dias") == 14


def test_planner_status_sensores():
    plano = nik_service._planejar_ferramentas("qual a bateria dos sensores")
    assert "status_sensores" in [p["nome"] for p in plano]


def test_planner_historico_coletas():
    plano = nik_service._planejar_ferramentas("histórico de coletas do parceiro X")
    assert "historico_coletas" in [p["nome"] for p in plano]
