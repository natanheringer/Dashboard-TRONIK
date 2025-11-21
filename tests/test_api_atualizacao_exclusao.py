"""
Testes de Atualização e Exclusão - Dashboard-TRONIK
===================================================
Testa endpoints PUT e DELETE de lixeiras.
IMPORTANTE: Todos os testes usam banco de dados isolado (test_db) para não afetar dados reais.
"""

import pytest
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Lixeira, Parceiro, TipoMaterial, Usuario
from banco_dados.utils import utc_now_naive


class TestAtualizarLixeira:
    """Testes de atualização de lixeiras"""
    
    def test_atualizar_lixeira_requires_auth(self, client):
        """Testa que atualizar lixeira requer autenticação"""
        response = client.put('/api/lixeira/1', json={})
        assert response.status_code == 401 or response.status_code == 302
    
    def test_atualizar_lixeira_not_found(self, client, db_session):
        """Testa atualizar lixeira inexistente"""
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
        
        # Tentar atualizar lixeira inexistente
        response = client.put('/api/lixeira/99999', json={
            'localizacao': 'Nova Localização'
        })
        assert response.status_code == 404
        data = response.get_json()
        assert 'erro' in data
    
    def test_atualizar_lixeira_success(self, client, db_session):
        """Testa atualização bem-sucedida de lixeira"""
        # Fazer login
        usuario = Usuario(
            username='testuser_update',
            email='testupdate@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_update',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira para atualizar
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste Update')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Localização Original',
            nivel_preenchimento=50.0,
            status='OK',
            latitude=-15.7942,
            longitude=-47.8822,
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Atualizar lixeira
        response = client.put(f'/api/lixeira/{lixeira.id}', json={
            'localizacao': 'Localização Atualizada',
            'nivel_preenchimento': 75.0,
            'status': 'ALERTA'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['localizacao'] == 'Localização Atualizada'
        assert data['nivel_preenchimento'] == 75.0
        assert data['status'] == 'ALERTA'
        
        # Verificar que foi realmente atualizado no banco (buscar novamente)
        lixeira_atualizada = db_session.query(Lixeira).filter_by(id=lixeira.id).first()
        assert lixeira_atualizada is not None
        assert lixeira_atualizada.localizacao == 'Localização Atualizada'
        assert lixeira_atualizada.nivel_preenchimento == 75.0
    
    def test_atualizar_lixeira_partial(self, client, db_session):
        """Testa atualização parcial de lixeira (apenas alguns campos)"""
        # Fazer login
        usuario = Usuario(
            username='testuser_partial',
            email='testpartial@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_partial',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste Partial')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Localização Original',
            nivel_preenchimento=50.0,
            status='OK',
            latitude=-15.7942,
            longitude=-47.8822,
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        lixeira_id = lixeira.id
        localizacao_original = lixeira.localizacao
        
        # Atualizar apenas nível de preenchimento
        response = client.put(f'/api/lixeira/{lixeira_id}', json={
            'nivel_preenchimento': 90.0
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['nivel_preenchimento'] == 90.0
        # Localização deve permanecer a mesma
        assert data['localizacao'] == localizacao_original
    
    def test_atualizar_lixeira_invalid_data(self, client, db_session):
        """Testa atualização com dados inválidos"""
        # Fazer login
        usuario = Usuario(
            username='testuser_invalid',
            email='testinvalid@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_invalid',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste Invalid')
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
        db_session.commit()
        
        # Tentar atualizar com nível inválido (> 100)
        response = client.put(f'/api/lixeira/{lixeira.id}', json={
            'nivel_preenchimento': 150.0
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data
    
    def test_atualizar_lixeira_coordenadas(self, client, db_session):
        """Testa atualização de coordenadas"""
        # Fazer login
        usuario = Usuario(
            username='testuser_coords',
            email='testcoords@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_coords',
            'senha': 'TestPass123!'
        })
        
        # Criar lixeira sem coordenadas
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Teste Coords')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Teste Coordenadas',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        
        # Atualizar com coordenadas
        response = client.put(f'/api/lixeira/{lixeira.id}', json={
            'latitude': -15.8000,
            'longitude': -47.9000
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['latitude'] == -15.8000
        assert data['longitude'] == -47.9000


class TestDeletarLixeira:
    """Testes de exclusão de lixeiras (APENAS ADMIN)"""
    
    def test_deletar_lixeira_requires_auth(self, client):
        """Testa que deletar lixeira requer autenticação"""
        response = client.delete('/api/lixeira/1')
        assert response.status_code == 401 or response.status_code == 302
    
    def test_deletar_lixeira_requires_admin(self, client, db_session):
        """Testa que deletar lixeira requer permissão de admin"""
        # Fazer login como usuário comum (não admin)
        usuario = Usuario(
            username='testuser_common',
            email='testcommon@example.com',
            admin=False,  # NÃO é admin
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_common',
            'senha': 'TestPass123!'
        })
        
        # Tentar deletar (deve falhar - não é admin)
        response = client.delete('/api/lixeira/1')
        assert response.status_code == 403
        data = response.get_json()
        assert 'erro' in data
        assert 'admin' in data['erro'].lower()
    
    def test_deletar_lixeira_not_found(self, client, db_session):
        """Testa deletar lixeira inexistente"""
        # Fazer login como admin
        admin = Usuario(
            username='admin_delete',
            email='admindelete@example.com',
            admin=True,  # É admin
            ativo=True
        )
        admin.set_senha('AdminPass123!')
        db_session.add(admin)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'admin_delete',
            'senha': 'AdminPass123!'
        })
        
        # Tentar deletar lixeira inexistente
        response = client.delete('/api/lixeira/99999')
        assert response.status_code == 404
        data = response.get_json()
        assert 'erro' in data
    
    def test_deletar_lixeira_success(self, client, db_session):
        """Testa exclusão bem-sucedida de lixeira (apenas admin)"""
        # IMPORTANTE: Este teste usa banco de dados isolado (test_db)
        # Os dados são limpos automaticamente após o teste
        
        # Fazer login como admin
        admin = Usuario(
            username='admin_delete_success',
            email='admindeletesuccess@example.com',
            admin=True,
            ativo=True
        )
        admin.set_senha('AdminPass123!')
        db_session.add(admin)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'admin_delete_success',
            'senha': 'AdminPass123!'
        })
        
        # Criar lixeira para deletar (em banco de teste isolado)
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Para Deletar')
        db_session.add(parceiro)
        db_session.flush()
        
        lixeira = Lixeira(
            localizacao='Lixeira Para Deletar',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.commit()
        lixeira_id = lixeira.id
        
        # Verificar que lixeira existe
        lixeira_existente = db_session.query(Lixeira).filter_by(id=lixeira_id).first()
        assert lixeira_existente is not None
        
        # Deletar lixeira
        response = client.delete(f'/api/lixeira/{lixeira_id}')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'mensagem' in data
        assert 'deletada' in data['mensagem'].lower()
        
        # Verificar que lixeira foi realmente deletada (no banco de teste)
        lixeira_deletada = db_session.query(Lixeira).filter_by(id=lixeira_id).first()
        assert lixeira_deletada is None
    
    def test_deletar_lixeira_with_coletas(self, client, db_session):
        """Testa que deletar lixeira também deleta coletas relacionadas (cascade)"""
        # Fazer login como admin
        admin = Usuario(
            username='admin_cascade',
            email='admincascade@example.com',
            admin=True,
            ativo=True
        )
        admin.set_senha('AdminPass123!')
        db_session.add(admin)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'admin_cascade',
            'senha': 'AdminPass123!'
        })
        
        # Criar lixeira com coletas
        from banco_dados.modelos import Coleta, TipoColetor
        
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Cascade')
        db_session.add(parceiro)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        lixeira = Lixeira(
            localizacao='Lixeira Com Coletas',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        # Criar coleta associada
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None
        )
        db_session.add(coleta)
        db_session.commit()
        
        coleta_id = coleta.id
        lixeira_id = lixeira.id
        
        # Deletar lixeira
        response = client.delete(f'/api/lixeira/{lixeira_id}')
        assert response.status_code == 200
        
        # Verificar que lixeira foi deletada
        lixeira_deletada = db_session.query(Lixeira).filter_by(id=lixeira_id).first()
        assert lixeira_deletada is None
        
        # Verificar que coletas também foram deletadas (cascade)
        coleta_deletada = db_session.query(Coleta).filter_by(id=coleta_id).first()
        assert coleta_deletada is None

