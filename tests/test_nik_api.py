from banco_dados.services import nik_service as nik_service


def test_nik_landing_publica(client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "gerar_bloco_landing",
        lambda tipo: {"bloco": {"titulo": "Nik", "corpo": "Teste"}, "fonte": "fallback"},
    )
    resp = client.get("/api/nik/landing/fala_nik")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bloco"]["titulo"] == "Nik"


def test_nik_ops_exige_login(client):
    resp = client.get("/api/nik/ops/resumo")
    assert resp.status_code in {302, 401}


def test_nik_ops_resumo_autenticado(auth_client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "resumo_operacional",
        lambda db: {"texto": "Resumo Nik", "fonte": "fallback", "modelo": None},
    )
    resp = auth_client.get("/api/nik/ops/resumo")
    assert resp.status_code == 200
    assert resp.get_json()["texto"] == "Resumo Nik"
