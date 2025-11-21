"""
Testes da API de Sensores - Dashboard-TRONIK
============================================
Testa todos os endpoints relacionados a sensores.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Sensor, Lixeira, TipoSensor, Parceiro, TipoMaterial
from banco_dados.utils import utc_now_naive


class TestListarSensores:
    """Testes do endpoint de listar sensores"""
    
    def test_listar_sensores_empty(self, client, db_session):
        """Testa listar sensores quando não há nenhum"""
        response = client.get('/api/sensores')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_listar_sensores_with_data(self, client, db_session, create_lixeira):
        """Testa listar sensores com dados"""
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor1 = Sensor(
            lixeira_id=lixeira.id,
            tipo_sensor_id=tipo_sensor.id if tipo_sensor else None,
            bateria=85.0
        )
        db_session.add(sensor1)
        db_session.commit()
        
        response = client.get('/api/sensores')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['bateria'] == 85.0
        assert data[0]['lixeira_id'] == lixeira.id
    
    def test_listar_sensores_filter_by_lixeira(self, client, db_session, create_lixeira):
        """Testa filtrar sensores por lixeira"""
        lixeira1 = create_lixeira(localizacao="Lixeira 1")
        lixeira2 = create_lixeira(localizacao="Lixeira 2")
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor1 = Sensor(lixeira_id=lixeira1.id, tipo_sensor_id=tipo_sensor.id if tipo_sensor else None)
        sensor2 = Sensor(lixeira_id=lixeira2.id, tipo_sensor_id=tipo_sensor.id if tipo_sensor else None)
        db_session.add_all([sensor1, sensor2])
        db_session.commit()
        
        response = client.get(f'/api/sensores?lixeira_id={lixeira1.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['lixeira_id'] == lixeira1.id
    
    def test_listar_sensores_filter_by_bateria(self, client, db_session, create_lixeira):
        """Testa filtrar sensores por nível de bateria"""
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor1 = Sensor(lixeira_id=lixeira.id, tipo_sensor_id=tipo_sensor.id if tipo_sensor else None, bateria=20.0)
        sensor2 = Sensor(lixeira_id=lixeira.id, tipo_sensor_id=tipo_sensor.id if tipo_sensor else None, bateria=80.0)
        db_session.add_all([sensor1, sensor2])
        db_session.commit()
        
        response = client.get('/api/sensores?bateria_min=50')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['bateria'] == 80.0


class TestObterSensor:
    """Testes do endpoint de obter sensor específico"""
    
    def test_obter_sensor_success(self, client, db_session, create_lixeira):
        """Testa obter um sensor específico com sucesso"""
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor = Sensor(
            lixeira_id=lixeira.id,
            tipo_sensor_id=tipo_sensor.id if tipo_sensor else None,
            bateria=75.0
        )
        db_session.add(sensor)
        db_session.commit()
        
        response = client.get(f'/api/sensor/{sensor.id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == sensor.id
        assert data['bateria'] == 75.0
        assert data['lixeira_id'] == lixeira.id
    
    def test_obter_sensor_not_found(self, client):
        """Testa obter sensor que não existe"""
        response = client.get('/api/sensor/99999')
        assert response.status_code == 404
        data = response.get_json()
        assert 'erro' in data


class TestCriarSensor:
    """Testes do endpoint de criar sensor"""
    
    def test_criar_sensor_requires_auth(self, client):
        """Testa que criar sensor requer autenticação"""
        response = client.post('/api/sensor', json={
            'lixeira_id': 1,
            'bateria': 100.0
        })
        assert response.status_code == 401 or response.status_code == 302
    
    def test_criar_sensor_success(self, client, db_session, create_lixeira):
        """Testa criar sensor com sucesso"""
        # Fazer login
        from banco_dados.modelos import Usuario
        usuario = Usuario(
            username='testuser_sensor',
            email='testsensor@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_sensor',
            'senha': 'TestPass123!'
        })
        
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        response = client.post('/api/sensor', json={
            'lixeira_id': lixeira.id,
            'tipo_sensor_id': tipo_sensor.id if tipo_sensor else None,
            'bateria': 90.0
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert 'id' in data
        assert data['bateria'] == 90.0
        assert data['lixeira_id'] == lixeira.id
    
    def test_criar_sensor_missing_lixeira_id(self, client, db_session):
        """Testa criar sensor sem lixeira_id"""
        from banco_dados.modelos import Usuario
        usuario = Usuario(
            username='testuser_sensor2',
            email='testsensor2@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_sensor2',
            'senha': 'TestPass123!'
        })
        
        response = client.post('/api/sensor', json={
            'bateria': 100.0
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data
    
    def test_criar_sensor_invalid_lixeira_id(self, client, db_session):
        """Testa criar sensor com lixeira_id inválido"""
        from banco_dados.modelos import Usuario
        usuario = Usuario(
            username='testuser_sensor3',
            email='testsensor3@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_sensor3',
            'senha': 'TestPass123!'
        })
        
        response = client.post('/api/sensor', json={
            'lixeira_id': 99999,
            'bateria': 100.0
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data
    
    def test_criar_sensor_invalid_bateria(self, client, db_session, create_lixeira):
        """Testa criar sensor com bateria inválida"""
        from banco_dados.modelos import Usuario
        usuario = Usuario(
            username='testuser_sensor4',
            email='testsensor4@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_sensor4',
            'senha': 'TestPass123!'
        })
        
        lixeira = create_lixeira()
        
        response = client.post('/api/sensor', json={
            'lixeira_id': lixeira.id,
            'bateria': 150.0  # Inválido (> 100)
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'erro' in data


class TestAtualizarSensor:
    """Testes do endpoint de atualizar sensor"""
    
    def test_atualizar_sensor_requires_auth(self, client):
        """Testa que atualizar sensor requer autenticação"""
        response = client.put('/api/sensor/1', json={'bateria': 50.0})
        assert response.status_code == 401 or response.status_code == 302
    
    def test_atualizar_sensor_not_found(self, client, db_session):
        """Testa atualizar sensor que não existe"""
        from banco_dados.modelos import Usuario
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
        
        response = client.put('/api/sensor/99999', json={'bateria': 50.0})
        assert response.status_code == 404
    
    def test_atualizar_sensor_success(self, client, db_session, create_lixeira):
        """Testa atualizar sensor com sucesso"""
        from banco_dados.modelos import Usuario
        usuario = Usuario(
            username='testuser_update2',
            email='testupdate2@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_update2',
            'senha': 'TestPass123!'
        })
        
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor = Sensor(
            lixeira_id=lixeira.id,
            tipo_sensor_id=tipo_sensor.id if tipo_sensor else None,
            bateria=100.0
        )
        db_session.add(sensor)
        db_session.commit()
        
        response = client.put(f'/api/sensor/{sensor.id}', json={
            'bateria': 50.0
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['bateria'] == 50.0


class TestDeletarSensor:
    """Testes do endpoint de deletar sensor"""
    
    def test_deletar_sensor_requires_auth(self, client):
        """Testa que deletar sensor requer autenticação"""
        response = client.delete('/api/sensor/1')
        assert response.status_code == 401 or response.status_code == 302
    
    def test_deletar_sensor_requires_admin(self, client, db_session, create_lixeira):
        """Testa que deletar sensor requer admin"""
        from banco_dados.modelos import Usuario
        usuario = Usuario(
            username='testuser_delete',
            email='testdelete@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('TestPass123!')
        db_session.add(usuario)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'testuser_delete',
            'senha': 'TestPass123!'
        })
        
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor = Sensor(
            lixeira_id=lixeira.id,
            tipo_sensor_id=tipo_sensor.id if tipo_sensor else None
        )
        db_session.add(sensor)
        db_session.commit()
        
        response = client.delete(f'/api/sensor/{sensor.id}')
        assert response.status_code == 403
    
    def test_deletar_sensor_success(self, client, db_session, create_lixeira):
        """Testa deletar sensor com sucesso (admin)"""
        from banco_dados.modelos import Usuario
        admin = Usuario(
            username='admin_delete',
            email='admindelete@example.com',
            admin=True,
            ativo=True
        )
        admin.set_senha('AdminPass123!')
        db_session.add(admin)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'admin_delete',
            'senha': 'AdminPass123!'
        })
        
        lixeira = create_lixeira()
        tipo_sensor = db_session.query(TipoSensor).first()
        
        sensor = Sensor(
            lixeira_id=lixeira.id,
            tipo_sensor_id=tipo_sensor.id if tipo_sensor else None
        )
        db_session.add(sensor)
        db_session.commit()
        sensor_id = sensor.id
        
        response = client.delete(f'/api/sensor/{sensor_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'mensagem' in data
        
        # Verificar que foi deletado
        sensor_deletado = db_session.query(Sensor).filter(Sensor.id == sensor_id).first()
        assert sensor_deletado is None
    
    def test_deletar_sensor_not_found(self, client, db_session):
        """Testa deletar sensor que não existe"""
        from banco_dados.modelos import Usuario
        admin = Usuario(
            username='admin_delete2',
            email='admindelete2@example.com',
            admin=True,
            ativo=True
        )
        admin.set_senha('AdminPass123!')
        db_session.add(admin)
        db_session.commit()
        
        client.post('/auth/login', json={
            'username': 'admin_delete2',
            'senha': 'AdminPass123!'
        })
        
        response = client.delete('/api/sensor/99999')
        assert response.status_code == 404



