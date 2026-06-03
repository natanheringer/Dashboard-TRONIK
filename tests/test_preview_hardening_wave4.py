"""Regressões da onda 4 — rate limit landing e IDOR Maiara."""

from datetime import datetime

from banco_dados.modelos import NikRelatorioGerado, Usuario


def test_solicitar_coletor_rate_limit(client, db_session):
    payload = {
        "nome": "Teste Rate",
        "email": "rate@test.local",
        "localizacao": "Brasília",
    }
    for _ in range(10):
        resp = client.post("/preview/solicitar-coletor", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    resp = client.post("/preview/solicitar-coletor", json=payload)
    assert resp.status_code == 429
    assert resp.get_json()["ok"] is False


def test_maiara_export_idor_bloqueia_outro_usuario(client, db_session):
    dono = Usuario(
        username="dono_maiara",
        email="dono@test.local",
        admin=False,
        ativo=True,
    )
    dono.set_senha("DonoMai123!")
    intruso = Usuario(
        username="intruso_maiara",
        email="intruso@test.local",
        admin=False,
        ativo=True,
    )
    intruso.set_senha("IntrusoM123!")
    db_session.add_all([dono, intruso])
    db_session.flush()

    rel = NikRelatorioGerado(
        usuario_id=dono.id,
        periodo_inicio=datetime(2026, 1, 1),
        periodo_fim=datetime(2026, 1, 31),
        titulo="Relatório privado",
        conteudo_json='{"titulo": "Relatório privado"}',
        conteudo_markdown="# Privado",
    )
    db_session.add(rel)
    db_session.commit()
    rel_id = rel.id

    r = client.post(
        "/auth/login",
        json={"username": "intruso_maiara", "senha": "IntrusoM123!"},
    )
    assert r.status_code == 200

    resp = client.get(f"/api/nik/maiara/relatorio/{rel_id}/export?formato=md")
    assert resp.status_code == 404
