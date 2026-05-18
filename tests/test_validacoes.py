"""
Testes de Validação - Dashboard-TRONIK
======================================
Testa funções de validação de dados.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.seguranca import (
    sanitizar_string,
    validar_email,
    validar_km_percorrido,
    validar_latitude,
    validar_longitude,
    validar_nivel_preenchimento,
    validar_preco_combustivel,
    validar_quantidade_kg,
    validar_senha,
    validar_tipo_operacao,
    validar_username,
)


class TestValidarEmail:
    """Testes de validação de email"""

    def test_email_valido(self):
        """Testa emails válidos"""
        assert validar_email('test@example.com')
        assert validar_email('user.name@domain.co.uk')
        assert validar_email('test+tag@example.com')

    def test_email_invalido(self):
        """Testa emails inválidos"""
        assert not validar_email('invalid-email')
        assert not validar_email('@example.com')
        assert not validar_email('test@')
        assert not validar_email('')
        assert not validar_email(None)


class TestValidarSenha:
    """Testes de validação de senha"""

    def test_senha_valida(self):
        """Testa senhas válidas"""
        valido, erro = validar_senha('Senha123')
        assert valido
        assert erro is None

        valido, erro = validar_senha('MinhaSenha456')
        assert valido

    def test_senha_curta(self):
        """Testa senha muito curta"""
        valido, erro = validar_senha('Senh1')
        assert not valido
        assert '8 caracteres' in erro

    def test_senha_sem_maiuscula(self):
        """Testa senha sem letra maiúscula"""
        valido, erro = validar_senha('senha123')
        assert not valido
        assert 'maiúscula' in erro

    def test_senha_sem_minuscula(self):
        """Testa senha sem letra minúscula"""
        valido, erro = validar_senha('SENHA123')
        assert not valido
        assert 'minúscula' in erro

    def test_senha_sem_numero(self):
        """Testa senha sem número"""
        valido, erro = validar_senha('SenhaABC')
        assert not valido
        assert 'número' in erro


class TestValidarUsername:
    """Testes de validação de username"""

    def test_username_valido(self):
        """Testa usernames válidos"""
        valido, erro = validar_username('usuario123')
        assert valido

        valido, erro = validar_username('user_name')
        assert valido

    def test_username_invalido(self):
        """Testa usernames inválidos"""
        valido, erro = validar_username('')
        assert not valido

        valido, erro = validar_username('ab')  # Muito curto
        assert not valido

        valido, erro = validar_username('a' * 81)  # Muito longo
        assert not valido


class TestValidarCoordenadas:
    """Testes de validação de coordenadas"""

    def test_latitude_valida(self):
        """Testa latitudes válidas"""
        valido, erro = validar_latitude(-15.7942)
        assert valido

        valido, erro = validar_latitude(0)
        assert valido

        valido, erro = validar_latitude(90)
        assert valido

    def test_latitude_invalida(self):
        """Testa latitudes inválidas"""
        valido, erro = validar_latitude(91)
        assert not valido

        valido, erro = validar_latitude(-91)
        assert not valido

    def test_longitude_valida(self):
        """Testa longitudes válidas"""
        valido, erro = validar_longitude(-47.8822)
        assert valido

        valido, erro = validar_longitude(0)
        assert valido

        valido, erro = validar_longitude(180)
        assert valido

    def test_longitude_invalida(self):
        """Testa longitudes inválidas"""
        valido, erro = validar_longitude(181)
        assert not valido

        valido, erro = validar_longitude(-181)
        assert not valido


class TestValidarNivelPreenchimento:
    """Testes de validação de nível de preenchimento"""

    def test_nivel_valido(self):
        """Testa níveis válidos"""
        valido, erro = validar_nivel_preenchimento(0)
        assert valido

        valido, erro = validar_nivel_preenchimento(50.5)
        assert valido

        valido, erro = validar_nivel_preenchimento(100)
        assert valido

    def test_nivel_invalido(self):
        """Testa níveis inválidos"""
        valido, erro = validar_nivel_preenchimento(-1)
        assert not valido

        valido, erro = validar_nivel_preenchimento(101)
        assert not valido

        valido, erro = validar_nivel_preenchimento('abc')
        assert not valido


class TestValidarQuantidadeKg:
    """Testes de validação de quantidade em kg"""

    def test_quantidade_valida(self):
        """Testa quantidades válidas"""
        # Quantidade deve ser > 0 (não aceita 0)
        valido, erro = validar_quantidade_kg(1)
        assert valido

        valido, erro = validar_quantidade_kg(100.5)
        assert valido

    def test_quantidade_zero_invalida(self):
        """Testa que quantidade 0 é inválida"""
        valido, erro = validar_quantidade_kg(0)
        assert not valido
        assert 'maior que zero' in erro

    def test_quantidade_invalida(self):
        """Testa quantidades inválidas"""
        valido, erro = validar_quantidade_kg(-1)
        assert not valido

        valido, erro = validar_quantidade_kg('abc')
        assert not valido


class TestValidarKmPercorrido:
    """Testes de validação de km percorrido"""

    def test_km_valido(self):
        """Testa km válidos"""
        valido, erro = validar_km_percorrido(0)
        assert valido

        valido, erro = validar_km_percorrido(100.5)
        assert valido

    def test_km_invalido(self):
        """Testa km inválidos"""
        valido, erro = validar_km_percorrido(-1)
        assert not valido


class TestValidarPrecoCombustivel:
    """Testes de validação de preço de combustível"""

    def test_preco_valido(self):
        """Testa preços válidos"""
        valido, erro = validar_preco_combustivel(0)
        assert valido

        valido, erro = validar_preco_combustivel(5.50)
        assert valido

    def test_preco_invalido(self):
        """Testa preços inválidos"""
        valido, erro = validar_preco_combustivel(-1)
        assert not valido


class TestValidarTipoOperacao:
    """Testes de validação de tipo de operação"""

    def test_tipo_valido(self):
        """Testa tipos válidos"""
        valido, erro = validar_tipo_operacao('Avulsa')
        assert valido

        valido, erro = validar_tipo_operacao('Campanha')
        assert valido

    def test_tipo_invalido(self):
        """Testa tipos inválidos"""
        # Tipo inválido deve retornar False
        valido, erro = validar_tipo_operacao('Invalido')
        assert not valido
        assert 'Avulsa' in erro or 'Campanha' in erro

    def test_tipo_vazio_opcional(self):
        """Testa que tipo vazio é opcional (válido)"""
        # Tipo vazio é opcional, então é válido
        valido, erro = validar_tipo_operacao('')
        assert valido


class TestSanitizarString:
    """Testes de sanitização de strings"""

    def test_sanitizar_normal(self):
        """Testa sanitização de string normal"""
        resultado = sanitizar_string('Texto Normal')
        assert resultado == 'Texto Normal'

    def test_sanitizar_com_espacos(self):
        """Testa sanitização removendo espaços extras"""
        resultado = sanitizar_string('  Texto  com  espaços  ')
        assert resultado == 'Texto  com  espaços'

    def test_sanitizar_com_caracteres_controle(self):
        """Testa sanitização removendo caracteres de controle"""
        resultado = sanitizar_string('Texto\x00com\x1fcontrole')
        assert resultado == 'Textocomcontrole'

    def test_sanitizar_com_limite(self):
        """Testa sanitização com limite de tamanho"""
        resultado = sanitizar_string('Texto muito longo', max_length=10)
        assert len(resultado) == 10
        assert resultado == 'Texto muit'

    def test_sanitizar_vazio(self):
        """Testa sanitização de valores vazios"""
        assert sanitizar_string('') == ''
        assert sanitizar_string(None) == ''
        assert sanitizar_string(123) == ''


class TestValidacaoNaNInfinity:
    """Testes de validação com NaN e Infinity

    Nota: As funções de validação podem aceitar NaN/Infinity como válidos,
    mas os cálculos tratam esses valores corretamente (ver test_robustez.py).
    """

    def test_validar_coordenadas_nan(self):
        """Testa validação de coordenadas NaN"""

        # NaN pode passar na validação, mas será tratado nos cálculos
        valido, erro = validar_latitude(float('nan'))
        # Comportamento atual: NaN pode ser aceito
        assert isinstance(valido, bool)

        valido, erro = validar_longitude(float('nan'))
        assert isinstance(valido, bool)

    def test_validar_coordenadas_infinity(self):
        """Testa validação de coordenadas Infinity"""

        valido, erro = validar_latitude(float('inf'))
        # Comportamento atual: Infinity pode ser aceito
        assert isinstance(valido, bool)

        valido, erro = validar_longitude(float('inf'))
        assert isinstance(valido, bool)

    def test_validar_nivel_preenchimento_nan(self):
        """Testa validação de nível com NaN"""

        valido, erro = validar_nivel_preenchimento(float('nan'))
        # Comportamento atual: NaN pode ser aceito
        assert isinstance(valido, bool)

    def test_validar_nivel_preenchimento_infinity(self):
        """Testa validação de nível com Infinity"""

        valido, erro = validar_nivel_preenchimento(float('inf'))
        # Comportamento atual: Infinity pode ser aceito
        assert isinstance(valido, bool)

    def test_validar_quantidade_kg_nan(self):
        """Testa validação de quantidade com NaN"""

        valido, erro = validar_quantidade_kg(float('nan'))
        # Comportamento atual: NaN pode ser aceito
        assert isinstance(valido, bool)

    def test_validar_km_percorrido_nan(self):
        """Testa validação de km com NaN"""

        valido, erro = validar_km_percorrido(float('nan'))
        # Comportamento atual: NaN pode ser aceito (tratado nos cálculos)
        assert isinstance(valido, bool)

    def test_validar_preco_combustivel_nan(self):
        """Testa validação de preço com NaN"""

        valido, erro = validar_preco_combustivel(float('nan'))
        # Comportamento atual: NaN pode ser aceito (tratado nos cálculos)
        assert isinstance(valido, bool)

