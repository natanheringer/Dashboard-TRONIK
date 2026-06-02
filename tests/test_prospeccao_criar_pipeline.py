"""Tests for creating CRM pipeline from prospection candidate."""

from banco_dados.modelos import EmpresaCandidata, Pipeline, Usuario
from banco_dados.services import prospeccao_crm_bridge


def _login_admin(client, db_session):
    admin = Usuario(
        username="admin_prosp_pipeline",
        email="admin_prosp_pipeline@test.local",
        admin=True,
        ativo=True,
    )
    admin.set_senha("AdminProsp123!")
    db_session.add(admin)
    db_session.commit()
    r = client.post(
        "/auth/login",
        json={"username": "admin_prosp_pipeline", "senha": "AdminProsp123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


def test_criar_pipeline_candidato_exige_login(client):
    resp = client.post("/api/prospeccao/candidatos/1/pipeline", json={})
    assert resp.status_code in {302, 401}


def test_criar_pipeline_candidato_exige_admin(client, db_session, auth_client):
    empresa = EmpresaCandidata(
        cnpj="12345678000195",
        razao_social="Eco Recicla Ltda",
    )
    db_session.add(empresa)
    db_session.commit()

    resp = auth_client.post(
        f"/api/prospeccao/candidatos/{empresa.id}/pipeline",
        json={},
    )
    assert resp.status_code == 403
    assert resp.get_json()["erro"] == "Acesso negado. Apenas administradores."


def test_criar_pipeline_candidato_admin(client, db_session):
    empresa = EmpresaCandidata(
        cnpj="98765432000100",
        razao_social="Metal Verde SA",
        nome_fantasia="Metal Verde",
    )
    db_session.add(empresa)
    db_session.commit()
    empresa_id = empresa.id

    admin_client = _login_admin(client, db_session)
    resp = admin_client.post(
        f"/api/prospeccao/candidatos/{empresa_id}/pipeline",
        json={
            "observacoes": "Contato via fila REE",
            "valor_estimado": 1500.0,
            "status": "lead",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["ok"] is True
    dados = body["dados"]
    assert dados["pipeline_id"] is not None
    assert dados["empresa_id"] == empresa_id
    assert dados["origem"] == "prospeccao_ree"
    assert dados["ja_vinculado"] is False

    db_session.expire_all()
    empresa_db = db_session.query(EmpresaCandidata).filter_by(id=empresa_id).one()
    pipeline_db = db_session.query(Pipeline).filter_by(id=dados["pipeline_id"]).one()

    assert empresa_db.pipeline_id == pipeline_db.id
    assert pipeline_db.origem == "prospeccao_ree"
    assert pipeline_db.valor_estimado == 1500.0
    assert "Metal Verde SA" in (pipeline_db.observacoes or "")
    assert "98765432000100" in (pipeline_db.observacoes or "")
    assert "Contato via fila REE" in (pipeline_db.observacoes or "")


def test_criar_pipeline_candidato_empresa_inexistente(client, db_session):
    admin_client = _login_admin(client, db_session)
    resp = admin_client.post("/api/prospeccao/candidatos/99999/pipeline", json={})
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False
    assert body["erros"][0]["codigo"] == "EMPRESA_NAO_ENCONTRADA"


def test_criar_pipeline_de_candidato_idempotente(db_session):
    empresa = EmpresaCandidata(
        cnpj="11111111000111",
        razao_social="Ja Vinculada Ltda",
    )
    db_session.add(empresa)
    db_session.flush()
    pipeline = Pipeline(status="lead", origem="manual", valor_estimado=500.0)
    db_session.add(pipeline)
    db_session.flush()
    empresa.pipeline_id = pipeline.id
    db_session.commit()

    resultado = prospeccao_crm_bridge.criar_pipeline_de_candidato(
        db_session,
        empresa.id,
        usuario_id=None,
    )
    assert resultado is not None
    assert resultado["pipeline_id"] == pipeline.id
    assert resultado["ja_vinculado"] is True
