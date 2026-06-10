"""Regressoes do caminho telemetria -> banco/cache/WebSocket."""

from banco_dados.modelos import Notificacao, Sensor
from banco_dados.utils.cache import obter_cache


def test_telemetria_invalida_cache_e_emite_apos_persistir(
    client, db_session, create_lixeira, monkeypatch
):
    coletor = create_lixeira(nivel=10.0)
    sensor = Sensor(coletor_id=coletor.id, bateria=90.0)
    db_session.add(sensor)
    db_session.commit()

    cache = obter_cache()
    cache.definir("estatisticas", {"nivel_medio": 10})
    cache.definir(f"estatisticas:{coletor.parceiro_id}", {"nivel_medio": 10})
    cache.definir("preview:estatisticas_resumo", {"nivel_medio": 10})
    cache.definir("preview:coletores_geojson", [{"id": coletor.id, "nivel": 10}])

    eventos = []
    monkeypatch.setattr(
        "rotas.websocket.emitir_atualizacao_coletor",
        lambda data, evento="coletor_atualizado": eventos.append((evento, data)),
    )
    monkeypatch.setattr(
        "rotas.websocket.emitir_atualizacao_sensor",
        lambda data, evento="sensor_atualizado": eventos.append((evento, data)),
    )
    monkeypatch.setattr(
        "rotas.websocket.emitir_nova_notificacao",
        lambda data: eventos.append(("nova_notificacao", data)),
    )
    commits = []
    commit_original = db_session.commit

    def commit_contado():
        commits.append(True)
        return commit_original()

    monkeypatch.setattr(db_session, "commit", commit_contado)

    response = client.post(
        "/api/sensor/telemetria",
        json={
            "sensor_id": sensor.id,
            "coletor_id": coletor.id,
            "nivel_preenchimento": 96,
            "bateria": 10,
        },
    )

    assert response.status_code == 200
    assert len(commits) == 1
    assert response.get_json()["notificacoes_criadas"] == 2
    assert [evento for evento, _ in eventos] == [
        "coletor_atualizado",
        "sensor_atualizado",
        "nova_notificacao",
        "nova_notificacao",
    ]
    assert eventos[0][1]["nivel_preenchimento"] == 96
    assert eventos[1][1]["bateria"] == 10
    assert db_session.query(Notificacao).count() == 2
    assert cache.obter("estatisticas") is None
    assert cache.obter(f"estatisticas:{coletor.parceiro_id}") is None
    assert cache.obter("preview:estatisticas_resumo") is None
    assert cache.obter("preview:coletores_geojson") is None


def test_falha_em_um_evento_nao_bloqueia_demais_emissoes(
    client, db_session, create_lixeira, monkeypatch
):
    db_session.query(Notificacao).delete()
    db_session.commit()

    coletor = create_lixeira(nivel=10.0)
    sensor = Sensor(coletor_id=coletor.id, bateria=90.0)
    db_session.add(sensor)
    db_session.commit()

    eventos = []

    def falhar_coletor(_data, evento="coletor_atualizado"):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr("rotas.websocket.emitir_atualizacao_coletor", falhar_coletor)
    monkeypatch.setattr(
        "rotas.websocket.emitir_atualizacao_sensor",
        lambda data, evento="sensor_atualizado": eventos.append((evento, data)),
    )
    monkeypatch.setattr(
        "rotas.websocket.emitir_nova_notificacao",
        lambda data: eventos.append(("nova_notificacao", data)),
    )

    response = client.post(
        "/api/sensor/telemetria",
        json={
            "sensor_id": sensor.id,
            "coletor_id": coletor.id,
            "nivel_preenchimento": 96,
            "bateria": 10,
        },
    )

    assert response.status_code == 200
    assert [evento for evento, _ in eventos] == [
        "sensor_atualizado",
        "nova_notificacao",
        "nova_notificacao",
    ]
