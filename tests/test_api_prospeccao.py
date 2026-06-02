from banco_dados.services import prospeccao_xgb_service


def test_prospeccao_candidatos_exige_login(client):
    resp = client.get("/api/prospeccao/candidatos")
    assert resp.status_code in {302, 401}


def test_prospeccao_candidatos_autenticado(auth_client, monkeypatch):
    monkeypatch.setattr(
        prospeccao_xgb_service,
        "buscar_candidatos_prospeccao",
        lambda db, **kwargs: [{"id": 1, "prioridade": "alta"}],
    )
    resp = auth_client.get("/api/prospeccao/candidatos?limite=10&qid=bairro:teste")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dados"] == [{"id": 1, "prioridade": "alta"}]
    assert body["erros"] == []


def test_prospeccao_modelo_ativo_exige_login(client):
    resp = client.get("/api/prospeccao/modelo-ativo")
    assert resp.status_code in {302, 401}


def test_prospeccao_modelo_ativo_autenticado(auth_client, monkeypatch):
    monkeypatch.setattr(
        prospeccao_xgb_service,
        "buscar_modelo_ativo",
        lambda db: {
            "versao": "ranker-v1",
            "algoritmo": "xgboost_ranker",
            "metricas": {"ndcg@10": 0.82},
            "treinado_em": "2026-05-17T12:00:00",
        },
    )
    resp = auth_client.get("/api/prospeccao/modelo-ativo")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dados"]["versao"] == "ranker-v1"
    assert body["dados"]["metricas"]["ndcg@10"] == 0.82
    assert body["erros"] == []
