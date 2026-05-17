"""RBAC: usuário parceiro não acessa rotas admin e vê só seus coletores."""

import pytest

from banco_dados.modelos import Coletor, Parceiro, TipoMaterial, Usuario


@pytest.fixture
def parceiro_client(client, db_session):
    """Cliente autenticado como usuário parceiro (não-admin)."""
    p1 = Parceiro(nome="Parceiro A")
    p2 = Parceiro(nome="Parceiro B")
    db_session.add_all([p1, p2])
    db_session.flush()

    u = Usuario(
        username="parceiro_user",
        email="parceiro@test.local",
        ativo=True,
        admin=False,
        parceiro_id=p1.id,
    )
    u.set_senha("Parceiro123!")
    db_session.add(u)
    db_session.commit()

    r = client.post(
        "/auth/login",
        json={"username": "parceiro_user", "senha": "Parceiro123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


def _criar_coletor(db_session, localizacao, parceiro_id):
    tipo = db_session.query(TipoMaterial).first()
    c = Coletor(
        localizacao=localizacao,
        nivel_preenchimento=50.0,
        status="OK",
        parceiro_id=parceiro_id,
        tipo_material_id=tipo.id,
    )
    db_session.add(c)
    db_session.commit()
    return c


def test_parceiro_preview_gestao_403(parceiro_client):
    resp = parceiro_client.get("/preview/gestao")
    assert resp.status_code == 403


def test_parceiro_preview_parceiro_ok(parceiro_client):
    resp = parceiro_client.get("/preview/parceiro")
    assert resp.status_code == 200


def test_parceiro_api_coletores_escopo(parceiro_client, db_session):
    p1_id = db_session.query(Parceiro.id).filter_by(nome="Parceiro A").scalar()
    p2_id = db_session.query(Parceiro.id).filter_by(nome="Parceiro B").scalar()

    _criar_coletor(db_session, "Coletor A1", p1_id)
    _criar_coletor(db_session, "Coletor A2", p1_id)
    _criar_coletor(db_session, "Coletor B1", p2_id)

    resp = parceiro_client.get("/api/coletores")
    assert resp.status_code == 200
    data = resp.get_json()
    locais = {item["localizacao"] for item in data["dados"]}
    assert locais == {"Coletor A1", "Coletor A2"}
    assert data["paginacao"]["total"] == 2

    # parceiro_id na query não deve ampliar o escopo
    resp_outro = parceiro_client.get(f"/api/coletores?parceiro_id={p2_id}")
    assert resp_outro.status_code == 200
    assert resp_outro.get_json()["paginacao"]["total"] == 2


def test_parceiro_api_estatisticas_escopo(parceiro_client, db_session):
    p1_id = db_session.query(Parceiro.id).filter_by(nome="Parceiro A").scalar()

    _criar_coletor(db_session, "Stat A", p1_id)
    p2_id = db_session.query(Parceiro.id).filter_by(nome="Parceiro B").scalar()
    _criar_coletor(db_session, "Stat B1", p2_id)
    _criar_coletor(db_session, "Stat B2", p2_id)

    from banco_dados.utils.cache import obter_cache

    obter_cache().invalidar(f"estatisticas:{p1_id}")
    obter_cache().invalidar("estatisticas")

    resp = parceiro_client.get("/api/estatisticas")
    assert resp.status_code == 200
    assert resp.get_json()["total_coletores"] == 1
