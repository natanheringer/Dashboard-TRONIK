"""
Testes da API de Lixeiras - Dashboard-TRONIK
=============================================
Testa endpoints CRUD de coletores.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Coletor, Parceiro, TipoMaterial, Usuario


class TestListarLixeiras:
    """Testes de listagem de coletores"""

    def test_listar_lixeiras_requires_login(self, client):
        """Listagem exige sessão autenticada."""
        response = client.get('/api/coletores')
        assert response.status_code == 401

    def test_listar_lixeiras_empty(self, auth_client, db_session):
        """Testa listar coletores quando não há nenhuma"""
        response = auth_client.get('/api/coletores')
        assert response.status_code == 200
        data = response.get_json()
        # Ajustar para formato paginado
        if isinstance(data, dict) and 'dados' in data:
            assert isinstance(data['dados'], list)
            assert len(data['dados']) == 0
        else:
            assert isinstance(data, list)
            assert len(data) == 0

    def test_listar_lixeiras_with_data(self, auth_client, db_session, sample_lixeira_data):
        """Testa listar coletores com dados"""
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

        # Criar coletor
        coletor = Coletor(
            localizacao=sample_lixeira_data['localizacao'],
            nivel_preenchimento=sample_lixeira_data['nivel_preenchimento'],
            status=sample_lixeira_data['status'],
            latitude=sample_lixeira_data['latitude'],
            longitude=sample_lixeira_data['longitude'],
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id
        )
        db_session.add(coletor)
        db_session.commit()

        # Listar coletores
        response = auth_client.get('/api/coletores')
        assert response.status_code == 200
        data = response.get_json()
        # Ajustar para formato paginado
        if isinstance(data, dict) and 'dados' in data:
            coletores = data['dados']
            assert len(coletores) >= 1
            assert any(c['localizacao'] == sample_lixeira_data['localizacao'] for c in coletores)
        else:
            assert len(data) >= 1
            assert any(c['localizacao'] == sample_lixeira_data['localizacao'] for c in data)


class TestCriarLixeira:
    """Testes de criação de coletores"""

    def test_criar_lixeira_requires_auth(self, client):
        """Testa que criar coletor requer autenticação"""
        response = client.post('/api/coletor', json={})
        assert response.status_code == 401 or response.status_code == 302

    def test_criar_lixeira_success(self, client, db_session, sample_lixeira_data):
        """Testa criação bem-sucedida de coletor"""
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

        # Criar coletor
        dados = sample_lixeira_data.copy()
        dados['parceiro_id'] = parceiro.id
        dados['tipo_material_id'] = tipo_material.id

        response = client.post('/api/coletor', json=dados)
        assert response.status_code == 201
        data = response.get_json()
        # A resposta pode ter 'coletor' ou retornar diretamente os dados
        if 'coletor' in data:
            lixeira_data = data['coletor']
        else:
            lixeira_data = data
        assert lixeira_data['localizacao'] == sample_lixeira_data['localizacao']
        assert 'id' in lixeira_data

    def test_criar_lixeira_missing_fields(self, client, db_session):
        """Testa criação de coletor sem campos obrigatórios"""
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
        response = client.post('/api/coletor', json={
            'nivel_preenchimento': 50.0
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data

    def test_criar_lixeira_invalid_coordinates(self, client, db_session):
        """Testa criação de coletor com coordenadas inválidas"""
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
        response = client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'latitude': 200.0,  # Latitude inválida (> 90)
            'longitude': -47.8822,
            'parceiro_id': parceiro.id,
            'tipo_material_id': tipo_material.id
        })
        assert response.status_code == 400


class TestObterLixeira:
    """Testes de obter coletor específica"""

    def test_obter_lixeira_not_found(self, auth_client):
        """Testa obter coletor inexistente"""
        response = auth_client.get('/api/coletor/999')
        assert response.status_code == 404

    def test_obter_lixeira_success(self, auth_client, db_session, sample_lixeira_data):
        """Testa obter coletor existente"""
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

        # Criar coletor
        coletor = Coletor(
            localizacao=sample_lixeira_data['localizacao'],
            nivel_preenchimento=sample_lixeira_data['nivel_preenchimento'],
            status=sample_lixeira_data['status'],
            latitude=sample_lixeira_data['latitude'],
            longitude=sample_lixeira_data['longitude'],
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id
        )
        db_session.add(coletor)
        db_session.commit()

        # Obter coletor
        response = auth_client.get(f'/api/coletor/{coletor.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['localizacao'] == sample_lixeira_data['localizacao']
        assert data['id'] == coletor.id

    def test_criar_lixeira_paginacao_valida(self, auth_client, db_session, create_lixeira):
        """Testa listagem com paginação válida"""
        for i in range(5):
            create_lixeira(localizacao=f"Coletor {i}")

        response = auth_client.get('/api/coletores?pagina=1&por_pagina=10')
        assert response.status_code == 200

    def test_criar_lixeira_paginacao_invalida(self, auth_client):
        """Testa validação de paginação inválida (valores são ajustados)"""
        response = auth_client.get('/api/coletores?pagina=0')
        assert response.status_code == 200
        # Página 0 é ajustada para 1

        response = auth_client.get('/api/coletores?por_pagina=200')
        assert response.status_code == 200
        # por_pagina 200 é ajustado para o máximo

    def test_criar_lixeira_coordenadas_invalidas(self, auth_client, auth_headers):
        """Testa criação com coordenadas inválidas"""
        # Latitude fora do range
        response = auth_client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'nivel_preenchimento': 50.0,
            'latitude': 91.0,
            'longitude': -47.8822
        })
        assert response.status_code == 400

        # Longitude fora do range
        response = auth_client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'nivel_preenchimento': 50.0,
            'latitude': -15.7942,
            'longitude': 181.0
        })
        assert response.status_code == 400

    def test_criar_lixeira_tipo_invalido(self, auth_client, auth_headers):
        """Testa criação com tipos inválidos"""
        # Nível como string
        response = auth_client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'nivel_preenchimento': 'invalid'
        })
        assert response.status_code == 400

        # Latitude como string
        response = auth_client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'nivel_preenchimento': 50.0,
            'latitude': 'invalid'
        })
        assert response.status_code == 400

    def test_criar_lixeira_range_invalido(self, auth_client, auth_headers):
        """Testa criação com ranges inválidos"""
        # Nível > 100
        response = auth_client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'nivel_preenchimento': 150.0
        })
        assert response.status_code == 400

        # Nível < 0
        response = auth_client.post('/api/coletor', json={
            'localizacao': 'Teste',
            'nivel_preenchimento': -10.0
        })
        assert response.status_code == 400

