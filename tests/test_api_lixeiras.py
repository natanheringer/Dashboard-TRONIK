"""
Testes da API de Lixeiras - Dashboard-TRONIK
=============================================
Testa endpoints CRUD de lixeiras.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Lixeira, Parceiro, TipoMaterial, Usuario


class TestListarLixeiras:
    """Testes de listagem de lixeiras"""
    
    def test_listar_lixeiras_no_auth_required(self, client):
        """Testa que listar lixeiras não requer autenticação (comportamento atual)"""
        response = client.get('/api/lixeiras')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_listar_lixeiras_empty(self, client, db_session):
        """Testa listar lixeiras quando não há nenhuma"""
        response = client.get('/api/lixeiras')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_listar_lixeiras_with_data(self, client, db_session, sample_lixeira_data):
        """Testa listar lixeiras com dados"""
        # Usar tipos existentes do seed ou criar novos únicos
        # Buscar primeiro tipo de material existente
        tipo_material = db_session.query(TipoMaterial).first()
        if not tipo_material:
            tipo_material = TipoMaterial(nome=f'Material Teste {db_session.query(TipoMaterial).count()}')
            db_session.add(tipo_material)
            db_session.flush()
        
        # Criar parceiro único
        parceiro = Parceiro(nome=f'Parceiro Teste {db_session.query(Parceiro).count()}')
        db_session.add(parceiro)
        db_session.flush()
        
        # Criar lixeira
        lixeira = Lixeira(
            localizacao=sample_lixeira_data['localizacao'],
            nivel_preenchimento=sample_lixeira_data['nivel_preenchimento'],
            status=sample_lixeira_data['status'],
            latitude=sample_lixeira_data['latitude'],
            longitude=sample_lixeira_data['longitude'],
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Listar lixeiras
        response = client.get('/api/lixeiras')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['localizacao'] == sample_lixeira_data['localizacao']


class TestCriarLixeira:
    """Testes de criação de lixeiras"""
    
    def test_criar_lixeira_requires_auth(self, client):
        """Testa que criar lixeira requer autenticação"""
        response = client.post('/api/lixeira', json={})
        assert response.status_code == 401 or response.status_code == 302
    
    def test_criar_lixeira_success(self, client, db_session, sample_lixeira_data):
        """Testa criação bem-sucedida de lixeira"""
        # Fazer login
        usuario = Usuario(
            username='testuser',
            email='test@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('testpass123')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser',
            'senha': 'testpass123'
        })
        
        # Usar tipos existentes do seed ou criar novos únicos
        # Buscar primeiro tipo de material existente
        tipo_material = db_session.query(TipoMaterial).first()
        if not tipo_material:
            tipo_material = TipoMaterial(nome=f'Material Teste {db_session.query(TipoMaterial).count()}')
            db_session.add(tipo_material)
            db_session.flush()
        
        # Criar parceiro único
        parceiro = Parceiro(nome=f'Parceiro Teste {db_session.query(Parceiro).count()}')
        db_session.add(parceiro)
        db_session.flush()
        
        # Criar lixeira
        dados = sample_lixeira_data.copy()
        dados['parceiro_id'] = parceiro.id
        dados['tipo_material_id'] = tipo_material.id
        
        response = client.post('/api/lixeira', json=dados)
        assert response.status_code == 201
        data = response.get_json()
        # A resposta pode ter 'lixeira' ou retornar diretamente os dados
        if 'lixeira' in data:
            lixeira_data = data['lixeira']
        else:
            lixeira_data = data
        assert lixeira_data['localizacao'] == sample_lixeira_data['localizacao']
        assert 'id' in lixeira_data
    
    def test_criar_lixeira_missing_fields(self, client, db_session):
        """Testa criação de lixeira sem campos obrigatórios"""
        # Fazer login
        usuario = Usuario(
            username='testuser',
            email='test@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('testpass123')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser',
            'senha': 'testpass123'
        })
        
        # Tentar criar sem localização
        response = client.post('/api/lixeira', json={
            'nivel_preenchimento': 50.0
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data
    
    def test_criar_lixeira_invalid_coordinates(self, client, db_session):
        """Testa criação de lixeira com coordenadas inválidas"""
        # Fazer login
        usuario = Usuario(
            username='testuser',
            email='test@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('testpass123')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser',
            'senha': 'testpass123'
        })
        
        # Usar tipos existentes do seed ou criar novos únicos
        # Buscar primeiro tipo de material existente
        tipo_material = db_session.query(TipoMaterial).first()
        if not tipo_material:
            tipo_material = TipoMaterial(nome=f'Material Teste {db_session.query(TipoMaterial).count()}')
            db_session.add(tipo_material)
            db_session.flush()
        
        # Criar parceiro único
        parceiro = Parceiro(nome=f'Parceiro Teste {db_session.query(Parceiro).count()}')
        db_session.add(parceiro)
        db_session.flush()
        
        # Tentar criar com latitude inválida
        response = client.post('/api/lixeira', json={
            'localizacao': 'Teste',
            'latitude': 200.0,  # Latitude inválida (> 90)
            'longitude': -47.8822,
            'parceiro_id': parceiro.id,
            'tipo_material_id': tipo_material.id
        })
        assert response.status_code == 400


class TestObterLixeira:
    """Testes de obter lixeira específica"""
    
    def test_obter_lixeira_not_found(self, client):
        """Testa obter lixeira inexistente"""
        response = client.get('/api/lixeira/999')
        assert response.status_code == 404
    
    def test_obter_lixeira_success(self, client, db_session, sample_lixeira_data):
        """Testa obter lixeira existente"""
        # Usar tipos existentes do seed ou criar novos únicos
        # Buscar primeiro tipo de material existente
        tipo_material = db_session.query(TipoMaterial).first()
        if not tipo_material:
            tipo_material = TipoMaterial(nome=f'Material Teste {db_session.query(TipoMaterial).count()}')
            db_session.add(tipo_material)
            db_session.flush()
        
        # Criar parceiro único
        parceiro = Parceiro(nome=f'Parceiro Teste {db_session.query(Parceiro).count()}')
        db_session.add(parceiro)
        db_session.flush()
        
        # Criar lixeira
        lixeira = Lixeira(
            localizacao=sample_lixeira_data['localizacao'],
            nivel_preenchimento=sample_lixeira_data['nivel_preenchimento'],
            status=sample_lixeira_data['status'],
            latitude=sample_lixeira_data['latitude'],
            longitude=sample_lixeira_data['longitude'],
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Obter lixeira
        response = client.get(f'/api/lixeira/{lixeira.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['localizacao'] == sample_lixeira_data['localizacao']
        assert data['id'] == lixeira.id

