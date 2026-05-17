"""
Testes de Autenticação - Dashboard-TRONIK
==========================================
Testa login, registro e logout de usuários.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Usuario


class TestLogin:
    """Testes de login"""
    
    def test_login_page_loads(self, client):
        """Testa se a página de login carrega"""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Login' in response.data or b'login' in response.data.lower()
    
    def test_login_success_json(self, client, db_session):
        """Testa login bem-sucedido via JSON"""
        # Criar usuário de teste
        usuario = Usuario(
            username='testuser',
            email='test@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('testpass123')
        db_session.add(usuario)
        db_session.commit()
        
        # Tentar fazer login
        response = client.post('/auth/login', json={
            'username': 'testuser',
            'senha': 'testpass123'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['mensagem'] == 'Login realizado com sucesso'
        assert data['usuario']['username'] == 'testuser'
        assert data['usuario']['email'] == 'test@example.com'
    
    def test_login_with_email(self, client, db_session):
        """Testa login usando email em vez de username"""
        # Criar usuário de teste com dados únicos
        usuario = Usuario(
            username='testuser_email',
            email='testemail@example.com',
            admin=False,
            ativo=True
        )
        usuario.set_senha('testpass123')
        db_session.add(usuario)
        db_session.commit()
        
        # Tentar fazer login com email
        response = client.post('/auth/login', json={
            'username': 'testemail@example.com',
            'senha': 'testpass123'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['mensagem'] == 'Login realizado com sucesso'
    
    def test_login_invalid_credentials(self, client):
        """Testa login com credenciais inválidas"""
        response = client.post('/auth/login', json={
            'username': 'nonexistent',
            'senha': 'wrongpass'
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'erro' in data
        assert 'inválidas' in data['erro'].lower() or 'credenciais' in data['erro'].lower()
    
    def test_login_missing_fields(self, client):
        """Testa login sem campos obrigatórios"""
        # Sem username
        response = client.post('/auth/login', json={
            'senha': 'testpass123'
        })
        assert response.status_code == 400
        
        # Sem senha
        response = client.post('/auth/login', json={
            'username': 'testuser'
        })
        assert response.status_code == 400
    
    def test_login_inactive_user(self, client, db_session):
        """Testa login com usuário inativo"""
        # Criar usuário inativo
        usuario = Usuario(
            username='inactive',
            email='inactive@example.com',
            admin=False,
            ativo=False
        )
        usuario.set_senha('testpass123')
        db_session.add(usuario)
        db_session.commit()
        
        # Tentar fazer login
        response = client.post('/auth/login', json={
            'username': 'inactive',
            'senha': 'testpass123'
        })
        
        assert response.status_code == 403
        data = response.get_json()
        assert 'inativo' in data['erro'].lower()


class TestRegistro:
    """Registro público desabilitado por segurança (rotas/auth.py)."""

    def test_registro_page_blocked(self, client):
        response = client.get('/auth/registro')
        assert response.status_code in (302, 403)

    def test_registro_post_blocked(self, client, db_session):
        response = client.post('/auth/registro', json={
            'username': 'newuser_unique',
            'email': 'newuser_unique@example.com',
            'senha': 'NewPass123!',
            'confirmar_senha': 'NewPass123!',
        })
        assert response.status_code == 403
        assert db_session.query(Usuario).filter_by(username='newuser_unique').first() is None


class TestLogout:
    """Testes de logout"""
    
    def test_logout_requires_login(self, client):
        """Testa que logout requer autenticação"""
        response = client.post('/auth/logout')
        # Pode redirecionar ou retornar erro, dependendo da implementação
        assert response.status_code in [302, 401, 403]

