"""
Testes do serviço de coletores — listagem, filtros e contagem (stats de paginação).
"""

import pytest
from datetime import datetime

from banco_dados.modelos import Coletor, Parceiro, TipoMaterial
from banco_dados.services.coletor_service import (
    validar_dados_coletor,
    processar_ultima_coleta,
    criar_coletor,
    atualizar_coletor,
    obter_coletores_com_filtros,
)


class TestObterColetoresComFiltros:
    """Listagem paginada e total_count usados pela API como stats de paginação."""

    def test_lista_vazia_total_zero(self, db_session):
        coletores, total = obter_coletores_com_filtros(db_session)
        assert coletores == []
        assert total == 0

    def test_total_count_reflete_todos_registros(self, db_session, create_lixeira):
        for i in range(3):
            create_lixeira(localizacao=f"Coletor {i}", status="OK")
        coletores, total = obter_coletores_com_filtros(db_session, pagina=1, por_pagina=2)
        assert len(coletores) == 2
        assert total == 3

    def test_pagina_segunda_retorna_restante(self, db_session, create_lixeira):
        for i in range(5):
            create_lixeira(localizacao=f"P{i}")
        coletores, total = obter_coletores_com_filtros(db_session, pagina=2, por_pagina=2)
        assert len(coletores) == 2
        assert total == 5

    def test_filtro_status(self, db_session, create_lixeira):
        create_lixeira(localizacao="OK-1", status="OK")
        create_lixeira(localizacao="ALERTA-1", status="ALERTA")
        coletores, total = obter_coletores_com_filtros(db_session, status="ALERTA")
        assert total == 1
        assert coletores[0].status == "ALERTA"

    def test_filtro_parceiro_id(self, db_session):
        p1 = Parceiro(nome="Parceiro A")
        p2 = Parceiro(nome="Parceiro B")
        db_session.add_all([p1, p2])
        db_session.flush()
        tipo = db_session.query(TipoMaterial).first()
        db_session.add_all([
            Coletor(localizacao="L1", nivel_preenchimento=10, status="OK", parceiro_id=p1.id, tipo_material_id=tipo.id),
            Coletor(localizacao="L2", nivel_preenchimento=20, status="OK", parceiro_id=p2.id, tipo_material_id=tipo.id),
        ])
        db_session.commit()
        coletores, total = obter_coletores_com_filtros(db_session, parceiro_id=p1.id)
        assert total == 1
        assert coletores[0].parceiro_id == p1.id

    def test_eager_load_parceiro_e_tipo_material(self, db_session, create_lixeira):
        create_lixeira(localizacao="Com relações")
        coletores, _ = obter_coletores_com_filtros(db_session)
        assert len(coletores) == 1
        assert coletores[0].parceiro is not None
        assert coletores[0].tipo_material is not None


class TestValidarDadosColetor:
    def test_criar_exige_localizacao(self, db_session):
        erros = validar_dados_coletor({}, criar=True, db=db_session)
        assert any("localizacao" in e.lower() for e in erros)

    def test_atualizar_localizacao_vazia_rejeitada(self, db_session):
        erros = validar_dados_coletor({"localizacao": ""}, criar=False, db=db_session)
        assert any("localizacao" in e.lower() for e in erros)

    def test_parceiro_inexistente(self, db_session):
        erros = validar_dados_coletor(
            {"localizacao": "X", "parceiro_id": 99999},
            criar=True,
            db=db_session,
        )
        assert any("parceiro" in e.lower() for e in erros)


class TestCriarAtualizarColetor:
    def test_criar_coletor_persiste_campos(self, db_session):
        coletor = criar_coletor(db_session, {
            "localizacao": "  Praça Central  ",
            "nivel_preenchimento": 42.5,
            "status": "OK",
            "ultima_coleta": "2025-06-01T12:00:00",
        })
        assert coletor.id is not None
        assert coletor.localizacao == "Praça Central"
        assert coletor.nivel_preenchimento == 42.5

    def test_atualizar_coletor_altera_nivel(self, db_session, create_lixeira):
        coletor = create_lixeira(nivel=30.0)
        atualizado = atualizar_coletor(db_session, coletor, {"nivel_preenchimento": 75.0})
        assert atualizado.nivel_preenchimento == 75.0


class TestProcessarUltimaColeta:
    def test_iso_valido(self):
        dt = processar_ultima_coleta("2025-01-15T08:30:00")
        assert isinstance(dt, datetime)
        assert dt.year == 2025

    def test_none_retorna_datetime_atual(self):
        dt = processar_ultima_coleta(None)
        assert isinstance(dt, datetime)
