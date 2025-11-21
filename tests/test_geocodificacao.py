"""
Testes de Geocodificação - Dashboard-TRONIK
===========================================
Testa funcionalidades de geocodificação.
Usa mocks para evitar requisições reais ao Nominatim durante os testes.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Lixeira, Parceiro, TipoMaterial, Usuario


class TestGeocodificacaoEndpoint:
    """Testes do endpoint de geocodificação manual"""
    
    def test_geocodificar_lixeira_requires_auth(self, client):
        """Testa que geocodificar lixeira requer autenticação"""
        response = client.post('/api/lixeira/1/geocodificar', json={})
        assert response.status_code == 401 or response.status_code == 302
    
    def test_geocodificar_lixeira_not_found(self, client, db_session):
        """Testa geocodificar lixeira inexistente"""
        # Fazer login
        usuario = Usuario(
            username='testuser_geo',
            email='testgeo@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_geo',
            'senha': 'TestPass123!'
        })
        
        # Tentar geocodificar lixeira inexistente
        response = client.post('/api/lixeira/99999/geocodificar', json={})
        assert response.status_code == 404
    
    @patch('banco_dados.geocodificacao.geocodificar_endereco')
    def test_geocodificar_lixeira_success(self, mock_geocodificar, client, db_session):
        """Testa geocodificação bem-sucedida de lixeira"""
        # Mock da função de geocodificação
        mock_geocodificar.return_value = {
            'latitude': -15.8000,
            'longitude': -47.9000,
            'display_name': 'Teste Localização, Brasília, DF',
            'importance': 0.8
        }
        
        # Fazer login
        usuario = Usuario(
            username='testuser_geo_success',
            email='testgeosuccess@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_geo_success',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira sem coordenadas
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Geo')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Shopping Conjunto Nacional',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Geocodificar
        response = client.post(f'/api/lixeira/{lixeira.id}/geocodificar', json={
            'cidade': 'Brasília',
            'estado': 'DF'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'mensagem' in data
        assert 'lixeira' in data
        assert data['lixeira']['latitude'] == -15.8000
        assert data['lixeira']['longitude'] == -47.9000
        
        # Verificar que foi atualizado no banco
        lixeira_atualizada = db_session.query(Lixeira).filter_by(id=lixeira.id).first()
        assert lixeira_atualizada.latitude == -15.8000
        assert lixeira_atualizada.longitude == -47.9000
    
    @patch('banco_dados.geocodificacao.geocodificar_endereco')
    def test_geocodificar_lixeira_failure(self, mock_geocodificar, client, db_session):
        """Testa geocodificação quando falha"""
        # Mock retornando None (não encontrado)
        mock_geocodificar.return_value = None
        
        # Fazer login
        usuario = Usuario(
            username='testuser_geo_fail',
            email='testgeofail@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_geo_fail',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Geo Fail')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Endereço Inexistente 12345',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Tentar geocodificar (deve falhar e usar fallback)
        response = client.post(f'/api/lixeira/{lixeira.id}/geocodificar', json={})
        
        # Pode retornar 200 com coordenadas de fallback ou 400 com erro
        # Dependendo da implementação de geocodificar_lixeira
        assert response.status_code in [200, 400]


class TestGeocodificacaoAutomatica:
    """Testes de geocodificação automática na criação/atualização"""
    
    @patch('banco_dados.geocodificacao.geocodificar_endereco')
    def test_criar_lixeira_geocodificacao_automatica(self, mock_geocodificar, client, db_session):
        """Testa geocodificação automática ao criar lixeira sem coordenadas"""
        # Mock da função de geocodificação
        mock_geocodificar.return_value = {
            'latitude': -15.7900,
            'longitude': -47.8800,
            'display_name': 'Nova Localização, Brasília, DF',
            'importance': 0.7
        }
        
        # Fazer login
        usuario = Usuario(
            username='testuser_auto_geo',
            email='testautogeo@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_auto_geo',
            'senha': 'TestPass123!'
        })
        
        # Criar parceiro e tipo material
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Auto Geo')
        db_session.add(parceiro)
        db_session.flush()
        
        # Criar lixeira sem coordenadas (deve geocodificar automaticamente)
        dados = {
            'localizacao': 'Hotel Royal Tulip',
            'nivel_preenchimento': 50.0,
            'status': 'OK',
            'parceiro_id': parceiro.id,
            'tipo_material_id': tipo_material.id if tipo_material else None
            # Não fornecer latitude/longitude
        }
        
        response = client.post('/api/lixeira', json=dados)
        
        assert response.status_code == 201
        data = response.get_json()
        # Deve ter coordenadas (geocodificadas automaticamente)
        assert 'latitude' in data
        assert 'longitude' in data
        assert data['latitude'] == -15.7900
        assert data['longitude'] == -47.8800
    
    @patch('banco_dados.geocodificacao.geocodificar_endereco')
    def test_atualizar_lixeira_geocodificacao_automatica(self, mock_geocodificar, client, db_session):
        """Testa geocodificação automática ao atualizar localização"""
        # Mock da função de geocodificação
        mock_geocodificar.return_value = {
            'latitude': -15.8100,
            'longitude': -47.8900,
            'display_name': 'Nova Localização Atualizada, Brasília, DF',
            'importance': 0.75
        }
        
        # Fazer login
        usuario = Usuario(
            username='testuser_update_geo',
            email='testupdategeo@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_update_geo',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira sem coordenadas
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Update Geo')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Localização Original',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Atualizar localização (deve geocodificar automaticamente)
        response = client.put(f'/api/lixeira/{lixeira.id}', json={
            'localizacao': 'Shopping Iguatemi Brasília'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        # Deve ter coordenadas (geocodificadas automaticamente)
        assert 'latitude' in data
        assert 'longitude' in data
        assert data['latitude'] == -15.8100
        assert data['longitude'] == -47.8900


class TestGeocodificacaoFuncao:
    """Testes da função de geocodificação (com mock)"""
    
    def test_geocodificar_endereco_vazio(self):
        """Testa geocodificação com endereço vazio"""
        from banco_dados.geocodificacao import geocodificar_endereco
        
        resultado = geocodificar_endereco('')
        assert resultado is None
        
        resultado = geocodificar_endereco(None)
        assert resultado is None
    
    @patch('banco_dados.geocodificacao.requests.get')
    def test_geocodificar_endereco_success(self, mock_get):
        """Testa geocodificação bem-sucedida (mock)"""
        # Mock da resposta do Nominatim
        mock_response = MagicMock()
        mock_response.json.return_value = [{
            'lat': '-15.7942',
            'lon': '-47.8822',
            'display_name': 'Brasília, DF, Brasil',
            'importance': 0.9,
            'address': {
                'city': 'Brasília',
                'state': 'Distrito Federal'
            }
        }]
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        from banco_dados.geocodificacao import geocodificar_endereco
        
        resultado = geocodificar_endereco('Brasília')
        
        assert resultado is not None
        assert 'latitude' in resultado
        assert 'longitude' in resultado
        assert resultado['latitude'] == -15.7942
        assert resultado['longitude'] == -47.8822
    
    @patch('banco_dados.geocodificacao.requests.get')
    def test_geocodificar_endereco_not_found(self, mock_get):
        """Testa geocodificação quando endereço não é encontrado"""
        # Mock retornando lista vazia
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        from banco_dados.geocodificacao import geocodificar_endereco
        
        resultado = geocodificar_endereco('Endereço Inexistente 12345')
        
        # Deve retornar coordenadas de fallback (Brasília)
        assert resultado is not None
        assert 'latitude' in resultado
        assert 'longitude' in resultado
        # Deve usar coordenadas de fallback
        assert resultado['latitude'] == -15.7942  # Coordenadas de Brasília
        assert resultado['longitude'] == -47.8822


