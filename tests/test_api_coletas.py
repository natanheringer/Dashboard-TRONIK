"""
Testes da API de Coletas - Dashboard-TRONIK
===========================================
Testa endpoints de coletas (listar, criar, histórico).
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Coleta, Lixeira, Parceiro, TipoMaterial, TipoColetor, Usuario
from banco_dados.utils import utc_now_naive


class TestListarColetas:
    """Testes de listagem de coletas"""
    
    def test_listar_coletas_empty(self, client, db_session):
        """Testa listar coletas quando não há nenhuma"""
        response = client.get('/api/coletas')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_listar_coletas_with_data(self, client, db_session):
        """Testa listar coletas com dados"""
        # Criar lixeira, parceiro e tipo coletor
        tipo_material = db_session.query(TipoMaterial).first()
        if not tipo_material:
            tipo_material = TipoMaterial(nome='Material Teste')
            db_session.add(tipo_material)
            db_session.flush()
        
        parceiro = Parceiro(nome='Parceiro Teste')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Teste Localização',
            nivel_preenchimento=50.0,
            status='OK',
            latitude=-15.7942,
            longitude=-47.8822,
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id
        )
        db_session.add(lixeira)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        if not tipo_coletor:
            tipo_coletor = TipoColetor(nome='Coletor Teste')
            db_session.add(tipo_coletor)
            db_session.flush()
        
        # Criar coleta
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            tipo_operacao='Avulsa',
            km_percorrido=10.0,
            preco_combustivel=5.50,
            lucro_por_kg=2.0,
            parceiro_id=parceiro.id,
            tipo_coletor_id=tipo_coletor.id
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Listar coletas
        response = client.get('/api/coletas')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['volume_estimado'] == 100.0
        assert data[0]['tipo_operacao'] == 'Avulsa'
    
    def test_listar_coletas_filter_by_lixeira(self, client, db_session):
        """Testa filtrar coletas por lixeira"""
        # Criar duas lixeiras
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira1 = Lixeira(
            localizacao='Lixeira 1',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira1)
        db_session.flush()
        
        lixeira2 = Lixeira(
            localizacao='Lixeira 2',
            nivel_preenchimento=60.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira2)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        # Criar coletas para cada lixeira
        coleta1 = Coleta(
            lixeira_id=lixeira1.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None
        )
        db_session.add(coleta1)
        
        coleta2 = Coleta(
            lixeira_id=lixeira2.id,
            data_hora=utc_now_naive(),
            volume_estimado=200.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None
        )
        db_session.add(coleta2)
        db_session.commit()
        
        # Filtrar por lixeira 1
        response = client.get(f'/api/coletas?lixeira_id={lixeira1.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['lixeira_id'] == lixeira1.id
    
    def test_listar_coletas_filter_by_date(self, client, db_session):
        """Testa filtrar coletas por data"""
        # Criar lixeira
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Teste',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        # Criar coleta com data específica
        data_especifica = datetime(2025, 11, 20, 10, 0, 0)
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=data_especifica,
            volume_estimado=100.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Filtrar por data
        response = client.get('/api/coletas?data_inicio=2025-11-20&data_fim=2025-11-20')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) >= 1


class TestCriarColeta:
    """Testes de criação de coletas"""
    
    def test_criar_coleta_requires_auth(self, client):
        """Testa que criar coleta requer autenticação"""
        response = client.post('/api/coleta', json={})
        assert response.status_code == 401 or response.status_code == 302
    
    def test_criar_coleta_success(self, client, db_session):
        """Testa criação bem-sucedida de coleta"""
        # Fazer login
        usuario = Usuario(
            username='testuser',
            email='test@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira, parceiro e tipo coletor
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Teste Localização',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        # Criar coleta (data_hora é obrigatório na validação)
        dados_coleta = {
            'lixeira_id': lixeira.id,
            'data_hora': utc_now_naive().isoformat(),
            'volume_estimado': 100.0,
            'tipo_operacao': 'Avulsa',
            'km_percorrido': 10.0,
            'preco_combustivel': 5.50,
            'lucro_por_kg': 2.0,
            'parceiro_id': parceiro.id,
            'tipo_coletor_id': tipo_coletor.id if tipo_coletor else None
        }
        
        response = client.post('/api/coleta', json=dados_coleta)
        if response.status_code != 201:
            # Se falhou, verificar o erro
            data = response.get_json()
            print(f"Erro ao criar coleta: {data}")
        assert response.status_code == 201
        data = response.get_json()
        # A resposta retorna diretamente os dados da coleta
        assert 'id' in data
        assert data['volume_estimado'] == 100.0
    
    def test_criar_coleta_missing_lixeira_id(self, client, db_session):
        """Testa criação de coleta sem lixeira_id"""
        # Fazer login
        usuario = Usuario(
            username='testuser2',
            email='test2@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser2',
            'senha': 'TestPass123!'
        })
        
        # Tentar criar sem lixeira_id
        response = client.post('/api/coleta', json={
            'volume_estimado': 100.0
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data
    
    def test_criar_coleta_invalid_lixeira_id(self, client, db_session):
        """Testa criação de coleta com lixeira_id inexistente"""
        # Fazer login
        usuario = Usuario(
            username='testuser3',
            email='test3@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser3',
            'senha': 'TestPass123!'
        })
        
        # Tentar criar com lixeira_id inexistente (validação retorna 400, não 404)
        response = client.post('/api/coleta', json={
            'lixeira_id': 99999,
            'data_hora': utc_now_naive().isoformat(),
            'volume_estimado': 100.0
        })
        # A validação retorna 400 com erro de validação, não 404
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data or 'detalhes' in data


class TestHistorico:
    """Testes de histórico de coletas"""
    
    def test_obter_historico_empty(self, client, db_session):
        """Testa obter histórico quando não há coletas"""
        response = client.get('/api/historico')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_obter_historico_with_data(self, client, db_session):
        """Testa obter histórico com dados"""
        # Criar lixeira e coleta
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Teste',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Obter histórico
        response = client.get('/api/historico')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) >= 1
    
    def test_obter_historico_filter_by_date(self, client, db_session):
        """Testa filtrar histórico por data"""
        # Criar lixeira
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Teste',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        # Criar coleta com data específica
        data_especifica = datetime(2025, 11, 20, 10, 0, 0)
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=data_especifica,
            volume_estimado=100.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Filtrar por data
        response = client.get('/api/historico?data=2025-11-20')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) >= 1

