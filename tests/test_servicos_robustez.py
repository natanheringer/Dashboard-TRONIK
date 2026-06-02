"""
Testes de Robustez de Serviços - Dashboard-TRONIK
==================================================
Testa serviços com dados inválidos e casos extremos.
"""

import math
import os
import sys
from datetime import datetime
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Coleta
from banco_dados.services.coleta_service import (
    processar_data_hora,
    validar_dados_coleta,
)
from banco_dados.services.coletor_service import processar_ultima_coleta, validar_dados_lixeira
from banco_dados.services.relatorio_service import (
    agrupar_coletas_por_lixeira,
    agrupar_coletas_por_parceiro,
    calcular_metricas_financeiras,
    processar_filtros_data,
)


class TestRelatorioServiceRobustez:
    """Testes de robustez do serviço de relatórios"""

    def test_calcular_metricas_coleta_sem_atributos(self):
        """Testa cálculo com coleta sem atributos esperados"""
        coleta_mock = Mock()
        # Não definir atributos

        coletas = [coleta_mock]
        resultado = calcular_metricas_financeiras(coletas)

        # Deve lidar graciosamente
        assert resultado['total_coletas'] == 1
        assert math.isfinite(resultado['volume_total'])

    def test_calcular_metricas_mistura_validos_invalidos(self):
        """Testa cálculo com mistura de valores válidos e inválidos"""
        coleta_valida = Mock()
        coleta_valida.volume_estimado = 100.0
        coleta_valida.km_percorrido = 10.0
        coleta_valida.preco_combustivel = 5.50
        coleta_valida.lucro_por_kg = 2.0

        coleta_invalida = Mock()
        coleta_invalida.volume_estimado = float('nan')
        coleta_invalida.km_percorrido = None
        coleta_invalida.preco_combustivel = float('inf')
        coleta_invalida.lucro_por_kg = -5.0

        coletas = [coleta_valida, coleta_invalida]
        resultado = calcular_metricas_financeiras(coletas)

        # Deve calcular apenas valores válidos
        assert resultado['total_coletas'] == 2
        assert resultado['volume_total'] == 100.0
        assert math.isfinite(resultado['lucro_total'])

    def test_agrupar_coletas_coleta_sem_lixeira_id(self):
        """Testa agrupamento quando coleta não tem coletor_id"""
        coleta_mock = Mock()
        # Não definir coletor_id

        resultado = agrupar_coletas_por_lixeira([coleta_mock])

        # Deve retornar lista vazia ou lidar graciosamente
        assert isinstance(resultado, list)

    def test_agrupar_coletas_valores_negativos(self):
        """Testa agrupamento com valores negativos"""
        coleta_mock = Mock()
        coleta_mock.coletor_id = 1
        coleta_mock.volume_estimado = -10.0
        coleta_mock.km_percorrido = -5.0
        coleta_mock.lucro_por_kg = 2.0

        resultado = agrupar_coletas_por_lixeira([coleta_mock])

        # Valores negativos devem ser ignorados
        assert len(resultado) == 1
        assert resultado[0]['volume_total'] == 0.0
        assert resultado[0]['km_total'] == 0.0

    def test_agrupar_coletas_parceiro_sem_atributos(self):
        """Testa agrupamento quando parceiro não tem atributos"""
        coleta_mock = Mock()
        coleta_mock.parceiro_id = 1
        parceiro_mock = Mock()
        # Não definir nome
        coleta_mock.parceiro = parceiro_mock
        coleta_mock.volume_estimado = 100.0
        coleta_mock.lucro_por_kg = 2.0

        resultado = agrupar_coletas_por_parceiro([coleta_mock])

        # Deve lidar graciosamente
        assert isinstance(resultado, list)

    def test_processar_filtros_data_invalida(self, db_session):
        """Testa processamento de filtros de data inválidos"""
        from sqlalchemy.orm import Query

        query = db_session.query(Coleta)

        # Data inválida
        query_result, data_inicio, data_fim = processar_filtros_data(
            query,
            data_inicio='data-invalida',
            data_fim='2025-01-27'
        )

        # Deve lidar graciosamente (não aplicar filtro inválido)
        assert isinstance(query_result, Query)

    def test_processar_filtros_data_vazia(self, db_session):
        """Testa processamento de filtros de data vazios"""
        from sqlalchemy.orm import Query

        query = db_session.query(Coleta)

        query_result, data_inicio, data_fim = processar_filtros_data(
            query,
            data_inicio='',
            data_fim=''
        )

        assert isinstance(query_result, Query)
        assert data_inicio is None
        assert data_fim is None


class TestColetaServiceRobustez:
    """Testes de robustez do serviço de coletas"""

    def test_processar_data_hora_string_vazia(self):
        """Testa processamento de string vazia"""
        data = processar_data_hora('')
        assert isinstance(data, datetime)

    def test_processar_data_hora_whitespace(self):
        """Testa processamento de string com apenas espaços"""
        data = processar_data_hora('   ')
        assert isinstance(data, datetime)

    def test_validar_dados_coleta_sem_campos_obrigatorios(self, db_session):
        """Testa validação sem campos obrigatórios"""
        erros = validar_dados_coleta({}, criar=True, db=db_session)
        assert len(erros) > 0
        assert any('coletor_id' in erro.lower() for erro in erros)
        assert any('data_hora' in erro.lower() for erro in erros)

    def test_validar_dados_coleta_lixeira_inexistente(self, db_session):
        """Testa validação com coletor inexistente"""
        erros = validar_dados_coleta({
            'coletor_id': 99999,
            'data_hora': '2025-01-27T10:00:00'
        }, criar=True, db=db_session)
        assert len(erros) > 0
        assert any('coletor' in erro.lower() and 'não encontrada' in erro.lower() for erro in erros)

    def test_validar_dados_coleta_valores_invalidos(self, db_session):
        """Testa validação com valores inválidos"""
        erros = validar_dados_coleta({
            'coletor_id': 1,
            'data_hora': '2025-01-27T10:00:00',
            'volume_estimado': -10.0,
            'km_percorrido': -5.0
        }, criar=True, db=db_session)
        # Pode ter erros de validação
        assert isinstance(erros, list)


class TestLixeiraServiceRobustez:
    """Testes de robustez do serviço de coletores"""

    def test_processar_ultima_coleta_none(self):
        """Testa processamento de última coleta None"""

        data = processar_ultima_coleta(None)
        assert isinstance(data, datetime)

    def test_processar_ultima_coleta_string_vazia(self):
        """Testa processamento de última coleta vazia"""

        data = processar_ultima_coleta('')
        assert isinstance(data, datetime)

    def test_processar_ultima_coleta_invalida(self):
        """Testa processamento de última coleta inválida"""

        data = processar_ultima_coleta('data-invalida')
        assert isinstance(data, datetime)

    def test_validar_dados_lixeira_sem_localizacao(self, db_session):
        """Testa validação sem localização"""
        erros = validar_dados_lixeira({}, criar=True, db=db_session)
        assert len(erros) > 0
        assert any('localizacao' in erro.lower() for erro in erros)

    def test_validar_dados_lixeira_coordenadas_invalidas(self, db_session):
        """Testa validação com coordenadas inválidas"""
        erros = validar_dados_lixeira({
            'localizacao': 'Teste',
            'latitude': 91.0,
            'longitude': -47.8822
        }, criar=True, db=db_session)
        assert len(erros) > 0

    def test_validar_dados_lixeira_nivel_invalido(self, db_session):
        """Testa validação com nível inválido"""
        erros = validar_dados_lixeira({
            'localizacao': 'Teste',
            'nivel_preenchimento': 150.0
        }, criar=True, db=db_session)
        assert len(erros) > 0


class TestValidacaoEntradaRobustez:
    """Testes de robustez de validação de entrada"""

    def test_validar_tipo_com_none(self):
        """Testa que None é aceito em validação de tipo"""
        from banco_dados.utils.erros import ErroValidacao, validar_tipo

        # None não deve lançar erro (validação opcional)
        try:
            validar_tipo(None, int, 'campo')
        except ErroValidacao:
            pytest.fail("None não deveria lançar ErroValidacao")

    def test_validar_range_com_none(self):
        """Testa que None é aceito em validação de range"""
        from banco_dados.utils.erros import ErroValidacao, validar_range

        try:
            validar_range(None, 0, 100, 'campo')
        except ErroValidacao:
            pytest.fail("None não deveria lançar ErroValidacao")

    def test_validar_tipo_string_vazia(self):
        """Testa validação de string vazia"""
        from banco_dados.utils.erros import validar_tipo

        validar_tipo('', str, 'campo')  # String vazia é válida para str

    def test_validar_range_zero(self):
        """Testa validação de range com zero"""
        from banco_dados.utils.erros import validar_range

        validar_range(0, 0, 100, 'campo')  # Zero no limite mínimo


class TestCasosExtremos:
    """Testes de casos extremos"""

    def test_calcular_metricas_muitas_coletas(self):
        """Testa cálculo com muitas coletas"""
        coletas = []
        for i in range(1000):
            coleta = Mock()
            coleta.volume_estimado = 100.0 + i
            coleta.km_percorrido = 10.0
            coleta.preco_combustivel = 5.50
            coleta.lucro_por_kg = 2.0
            coletas.append(coleta)

        resultado = calcular_metricas_financeiras(coletas)

        assert resultado['total_coletas'] == 1000
        assert math.isfinite(resultado['volume_total'])
        assert math.isfinite(resultado['lucro_total'])

    def test_calcular_metricas_valores_zero(self):
        """Testa cálculo com valores zero"""
        coleta = Mock()
        coleta.volume_estimado = 0.0
        coleta.km_percorrido = 0.0
        coleta.preco_combustivel = 0.0
        coleta.lucro_por_kg = 0.0

        coletas = [coleta]
        resultado = calcular_metricas_financeiras(coletas)

        assert resultado['volume_total'] == 0.0
        assert resultado['km_total'] == 0.0
        assert resultado['custo_combustivel_total'] == 0.0
        assert resultado['lucro_total'] == 0.0

    def test_agrupar_coletas_muitas_lixeiras(self):
        """Testa agrupamento com muitas coletores"""
        coletas = []
        for i in range(100):
            coleta = Mock()
            coleta.coletor_id = i % 10  # 10 coletores diferentes
            coleta.volume_estimado = 100.0
            coleta.km_percorrido = 10.0
            coleta.lucro_por_kg = 2.0
            coletas.append(coleta)

        resultado = agrupar_coletas_por_lixeira(coletas)

        assert len(resultado) == 10
        for item in resultado:
            assert item['total_coletas'] == 10

    def test_processar_data_hora_fuso_horario(self):
        """Testa processamento de data com fuso horário"""
        # Data com fuso horário
        data = processar_data_hora('2025-01-27T10:00:00-03:00')
        assert isinstance(data, datetime)

        # Data UTC
        data = processar_data_hora('2025-01-27T10:00:00Z')
        assert isinstance(data, datetime)

    def test_processar_data_hora_milissegundos(self):
        """Testa processamento de data com milissegundos"""
        data = processar_data_hora('2025-01-27T10:00:00.123456')
        assert isinstance(data, datetime)

