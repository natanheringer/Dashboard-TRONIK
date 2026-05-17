"""Testes do resumo operacional de coletores."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from banco_dados.modelos import Coletor
from banco_dados.services.coletor_service import resumo_operacional


def test_coletores_resumo_exige_login(client):
    resp = client.get("/api/coletores/resumo")
    assert resp.status_code == 401


def test_resumo_operacional_vazio(db_session):
    assert resumo_operacional(db_session) == {
        "total_coletores": 0,
        "ativos": 0,
        "alerta_nivel_alto": 0,
        "sem_geocode": 0,
    }


def test_resumo_operacional_contagens(db_session):
    db_session.add_all(
        [
            Coletor(
                localizacao="A",
                nivel_preenchimento=85.0,
                status="OK",
                latitude=-15.79,
                longitude=-47.88,
            ),
            Coletor(
                localizacao="B",
                nivel_preenchimento=50.0,
                status="QUEBRADA",
                latitude=-15.80,
                longitude=-47.89,
            ),
            Coletor(
                localizacao="C",
                nivel_preenchimento=90.0,
                status="OK",
                latitude=None,
                longitude=None,
            ),
            Coletor(
                localizacao="D",
                nivel_preenchimento=10.0,
                status="MANUTENCAO",
                latitude=-15.81,
                longitude=-47.90,
            ),
        ]
    )
    db_session.commit()

    resumo = resumo_operacional(db_session)
    assert resumo["total_coletores"] == 4
    assert resumo["ativos"] == 2
    assert resumo["alerta_nivel_alto"] == 2
    assert resumo["sem_geocode"] == 1


def test_coletores_resumo_autenticado(auth_client, db_session):
    db_session.add(
        Coletor(localizacao="Resumo API", nivel_preenchimento=82.0, status="OK")
    )
    db_session.commit()

    resp = auth_client.get("/api/coletores/resumo")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_coletores"] == 1
    assert data["ativos"] == 1
    assert data["alerta_nivel_alto"] == 1
    assert data["sem_geocode"] == 1
