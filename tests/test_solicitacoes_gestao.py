"""Testes da API de solicitações de coletor (gestão v2)."""

from banco_dados.modelos import SolicitacaoColetor, Usuario


def _login_admin(client, db_session):
    admin = Usuario(
        username="admin_solicitacoes",
        email="admin_solicitacoes@test.local",
        admin=True,
        ativo=True,
    )
    admin.set_senha("AdminSol123!")
    db_session.add(admin)
    db_session.commit()
    r = client.post(
        "/auth/login",
        json={"username": "admin_solicitacoes", "senha": "AdminSol123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


def test_listar_solicitacoes_vazio(auth_client, db_session):
    resp = auth_client.get("/api/solicitacoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data == []


def test_listar_solicitacoes_com_dados(auth_client, db_session):
    sol = SolicitacaoColetor(
        nome="Maria Silva",
        email="maria@empresa.com",
        empresa="Eco Ltda",
        localizacao="Asa Norte",
        mensagem="Interesse em 2 coletores",
        status="pendente",
    )
    db_session.add(sol)
    db_session.commit()

    resp = auth_client.get("/api/solicitacoes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["nome"] == "Maria Silva"
    assert data[0]["email"] == "maria@empresa.com"
    assert data[0]["status"] == "pendente"


def test_atualizar_status_solicitacao(auth_client, db_session, client):
    sol = SolicitacaoColetor(
        nome="João Teste",
        email="joao@test.local",
        localizacao="Taguatinga",
        status="pendente",
    )
    db_session.add(sol)
    db_session.commit()
    sol_id = sol.id

    admin_client = _login_admin(client, db_session)
    resp = admin_client.post(
        f"/api/solicitacoes/{sol_id}/status",
        json={"status": "aprovado"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["solicitacao"]["status"] == "aprovado"
    assert "aprovado" in body["mensagem"].lower()

    list_resp = auth_client.get("/api/solicitacoes")
    assert list_resp.status_code == 200
    items = list_resp.get_json()
    assert any(i["id"] == sol_id and i["status"] == "aprovado" for i in items)


def test_atualizar_status_invalido(auth_client, db_session, client):
    sol = SolicitacaoColetor(
        nome="Ana",
        email="ana@test.local",
        localizacao="Sudoeste",
    )
    db_session.add(sol)
    db_session.commit()
    sol_id = sol.id

    admin_client = _login_admin(client, db_session)
    resp = admin_client.post(
        f"/api/solicitacoes/{sol_id}/status",
        json={"status": "inexistente"},
    )
    assert resp.status_code == 400
    assert "inválido" in resp.get_json()["erro"].lower()


def test_atualizar_status_requer_admin(auth_client, db_session):
    sol = SolicitacaoColetor(
        nome="Carlos",
        email="carlos@test.local",
        localizacao="Ceilândia",
    )
    db_session.add(sol)
    db_session.commit()
    sol_id = sol.id

    resp = auth_client.post(
        f"/api/solicitacoes/{sol_id}/status",
        json={"status": "recusado"},
    )
    assert resp.status_code == 403
