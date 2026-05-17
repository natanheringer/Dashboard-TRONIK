"""Tests for prospection ranker health (/api/prospeccao/saude, pipeline_health)."""

import json
from datetime import datetime

from banco_dados.modelos import ModeloProspeccao, ScoreProspeccao
from banco_dados.services import prospeccao_xgb_service
from jobs.prospeccao.pipeline_health import build_pipeline_health_report


def _login_user(client, db_session, username="user_saude_prosp"):
    from banco_dados.modelos import Usuario

    u = Usuario(username=username, email=f"{username}@test.local", ativo=True)
    u.set_senha("UserSaude123!")
    db_session.add(u)
    db_session.commit()
    r = client.post("/auth/login", json={"username": username, "senha": "UserSaude123!"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


def test_saude_sem_modelo(db_session):
    report = build_pipeline_health_report(db_session)
    assert report["modelo_ativo"] is False
    assert report["scores_publicados"] == 0
    assert report["warnings"]


def test_saude_com_modelo_heuristic_bootstrap(db_session):
    model = ModeloProspeccao(
        versao="test-heuristic-v1",
        algoritmo="heuristic_bootstrap",
        pipeline_version="prospeccao-ree-v3.2",
        feature_schema_json=json.dumps([]),
        metricas_json=json.dumps({"validation_ndcg_mean": None}),
        ativo=True,
        treinado_em=datetime(2026, 5, 1, 12, 0, 0),
    )
    db_session.add(model)
    db_session.commit()

    report = build_pipeline_health_report(db_session)
    assert report["modelo_ativo"] is True
    assert report["algoritmo"] == "heuristic_bootstrap"
    assert any("heuristic_bootstrap" in w for w in report["warnings"])
    assert any("Nenhum score publicado" in w for w in report["warnings"])


def test_saude_endpoint_autenticado(client, db_session):
    model = ModeloProspeccao(
        versao="test-api-saude-v1",
        algoritmo="xgboost.ranker",
        pipeline_version="prospeccao-ree-v3.2",
        feature_schema_json=json.dumps([]),
        metricas_json=json.dumps({
            "validation_ndcg_mean": 0.58,
            "train_ndcg_mean": 0.62,
        }),
        ativo=True,
        treinado_em=datetime(2026, 5, 10, 8, 30, 0),
    )
    db_session.add(model)
    db_session.flush()

    db_session.add(
        ScoreProspeccao(
            snapshot_id=1,
            modelo_id=model.id,
            empresa_id=None,
            local_id=None,
            qid="demo:q1",
            score=72.5,
            ranking_contexto=1,
            prioridade="alta",
        )
    )
    db_session.commit()

    authed = _login_user(client, db_session, username="user_saude_api")
    resp = authed.get("/api/prospeccao/saude")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    dados = body["dados"]
    assert dados["modelo_ativo"] is True
    assert dados["algoritmo"] == "xgboost.ranker"
    assert dados["scores_publicados"] == 1
    assert dados["metricas"]["validation_ndcg_mean"] == 0.58
    assert dados["ultimo_treino"].startswith("2026-05-10")

    via_service = prospeccao_xgb_service.saude_prospeccao(db_session)
    assert via_service["scores_publicados"] == 1
