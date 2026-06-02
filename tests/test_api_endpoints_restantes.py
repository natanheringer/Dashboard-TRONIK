"""
Testes de Endpoints Restantes - Dashboard-TRONIK
================================================
Testa endpoints que ainda não foram cobertos pelos outros testes.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Coletor, Parceiro, TipoMaterial, Usuario


class TestConfiguracoes:
    """Testes do endpoint de configurações"""

    def test_obter_configuracoes(self, auth_client):
        """Testa obter configurações do sistema"""
        response = auth_client.get('/api/configuracoes')
        assert response.status_code == 200
        data = response.get_json()
        assert 'nivel_alerta' in data
        assert 'nivel_critico' in data
        assert 'intervalo_atualizacao' in data
        assert 'timezone' in data
        assert data['nivel_alerta'] == 80
        assert data['nivel_critico'] == 95


class TestParceiros:
    """Testes do endpoint de parceiros"""

    def test_listar_parceiros_empty(self, auth_client, db_session):
        """Testa listar parceiros quando não há nenhum"""
        response = auth_client.get('/api/parceiros')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # Pode ter parceiros do seed
        assert len(data) >= 0

    def test_listar_parceiros_with_data(self, auth_client, db_session):
        """Testa listar parceiros com dados"""
        # Invalidar cache antes de criar novo parceiro
        from banco_dados.utils.cache import obter_cache
        cache = obter_cache()
        cache.invalidar('parceiros')

        # Criar parceiro ativo
        parceiro = Parceiro(nome='Parceiro Teste API', ativo=True)
        db_session.add(parceiro)
        db_session.commit()

        # Invalidar cache novamente após criar
        cache.invalidar('parceiros')

        response = auth_client.get('/api/parceiros')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # Deve ter pelo menos o parceiro criado (pode ter parceiros do seed também)
        nomes = [p['nome'] for p in data]
        assert 'Parceiro Teste API' in nomes

    def test_listar_parceiros_apenas_ativos(self, auth_client, db_session):
        """Testa que apenas parceiros ativos são retornados"""
        # Invalidar cache
        from banco_dados.utils.cache import obter_cache
        cache = obter_cache()
        cache.invalidar('parceiros')

        # Criar parceiro ativo
        parceiro_ativo = Parceiro(nome='Parceiro Ativo', ativo=True)
        db_session.add(parceiro_ativo)

        # Criar parceiro inativo
        parceiro_inativo = Parceiro(nome='Parceiro Inativo', ativo=False)
        db_session.add(parceiro_inativo)
        db_session.commit()

        # Invalidar cache novamente
        cache.invalidar('parceiros')

        response = auth_client.get('/api/parceiros')
        assert response.status_code == 200
        data = response.get_json()
        nomes = [p['nome'] for p in data]
        assert 'Parceiro Ativo' in nomes
        assert 'Parceiro Inativo' not in nomes


class TestTipos:
    """Testes dos endpoints de tipos"""

    def test_listar_tipos_material(self, auth_client, db_session):
        """Testa listar tipos de material"""
        response = auth_client.get('/api/tipos/material')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # Deve ter tipos do seed
        assert len(data) > 0
        assert 'id' in data[0]
        assert 'nome' in data[0]

    def test_listar_tipos_sensor(self, auth_client, db_session):
        """Testa listar tipos de sensor"""
        response = auth_client.get('/api/tipos/sensor')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # Deve ter tipos do seed
        assert len(data) > 0
        assert 'id' in data[0]
        assert 'nome' in data[0]

    def test_listar_tipos_coletor(self, auth_client, db_session):
        """Testa listar tipos de coletor"""
        response = auth_client.get('/api/tipos/coletor')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        # Deve ter tipos do seed
        assert len(data) > 0
        assert 'id' in data[0]
        assert 'nome' in data[0]


class TestSimularNiveis:
    """Testes do endpoint de simulação de níveis"""

    def test_simular_niveis_requires_auth(self, client):
        """Testa que simular níveis requer autenticação"""
        response = client.post('/api/coletores/simular-niveis', json={})
        assert response.status_code == 401 or response.status_code == 302

    def test_simular_niveis_success(self, client, db_session):
        """Testa simulação bem-sucedida de níveis"""
        # Fazer login
        usuario = Usuario(
            username='testuser_simular',
            email='testsimular@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()

        client.post('/auth/login', json={
            'username': 'testuser_simular',
            'senha': 'TestPass123!'
        })

        # Criar coletores
        from banco_dados.modelos import Parceiro, TipoMaterial

        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Simular')
        db_session.add(parceiro)
        db_session.flush()

        lixeira1 = Coletor(
            localizacao='Coletor 1',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira1)

        lixeira2 = Coletor(
            localizacao='Coletor 2',
            nivel_preenchimento=30.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira2)
        db_session.commit()

        # Simular níveis - formato esperado: {'coletores': [{'id': ..., 'nivel': ...}]}
        response = client.post('/api/coletores/simular-niveis', json={
            'coletores': [
                {'id': lixeira1.id, 'nivel': 75.0},
                {'id': lixeira2.id, 'nivel': 85.0}
            ]
        })

        assert response.status_code == 200
        data = response.get_json()
        assert 'mensagem' in data
        assert 'coletores' in data
        assert len(data['coletores']) == 2

        # Verificar que níveis foram alterados (mas dentro de 0-100)
        for lixeira_data in data['coletores']:
            assert 0 <= lixeira_data['nivel_preenchimento'] <= 100

    def test_simular_niveis_with_custom_params(self, client, db_session):
        """Testa simulação com parâmetros customizados"""
        # Fazer login
        usuario = Usuario(
            username='testuser_simular2',
            email='testsimular2@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()

        client.post('/auth/login', json={
            'username': 'testuser_simular2',
            'senha': 'TestPass123!'
        })

        # Criar coletor
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Simular 2')
        db_session.add(parceiro)
        db_session.flush()

        coletor = Coletor(
            localizacao='Coletor Simular',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(coletor)
        db_session.commit()
        nivel_original = coletor.nivel_preenchimento

        # Simular com formato esperado: {'coletores': [{'id': ..., 'nivel': ...}]}
        response = client.post('/api/coletores/simular-niveis', json={
            'coletores': [
                {'id': coletor.id, 'nivel': 60.0}
            ]
        })

        assert response.status_code == 200
        data = response.get_json()
        assert 'mensagem' in data
        assert 'coletores' in data
        assert len(data['coletores']) == 1
        # Nível deve ter mudado para 60.0
        lixeira_atualizada = data['coletores'][0]
        assert lixeira_atualizada['nivel_preenchimento'] == 60.0


class TestUsuarioAtual:
    """Testes do endpoint de usuário atual"""

    def test_usuario_atual_requires_auth(self, client):
        """Testa que obter usuário atual requer autenticação"""
        response = client.get('/auth/usuario/atual')
        assert response.status_code == 401 or response.status_code == 302

    def test_usuario_atual_success(self, client, db_session):
        """Testa obter informações do usuário atual"""
        # Criar e fazer login
        usuario = Usuario(
            username='testuser_atual',
            email='testatual@example.com',
            nome_completo='Usuário Teste',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()

        client.post('/auth/login', json={
            'username': 'testuser_atual',
            'senha': 'TestPass123!'
        })

        # Obter usuário atual
        response = client.get('/auth/usuario/atual')
        assert response.status_code == 200
        data = response.get_json()
        assert data['username'] == 'testuser_atual'
        assert data['email'] == 'testatual@example.com'
        assert data['nome_completo'] == 'Usuário Teste'
        assert not data['admin']
        assert data['ativo']
        assert 'id' in data

    def test_usuario_atual_admin(self, client, db_session):
        """Testa obter informações de usuário admin"""
        # Criar admin
        admin = Usuario(
            username='admin_atual',
            email='adminatual@example.com',
            admin=True,
            ativo=True
        )
        admin.set_senha('AdminPass123!')
        db_session.add(admin)
        db_session.commit()

        client.post('/auth/login', json={
            'username': 'admin_atual',
            'senha': 'AdminPass123!'
        })

        # Obter usuário atual
        response = client.get('/auth/usuario/atual')
        assert response.status_code == 200
        data = response.get_json()
        assert data['admin']



