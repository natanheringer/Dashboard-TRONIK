"""
Configuração do Pytest - Dashboard-TRONIK
==========================================
Configuração compartilhada para todos os testes.
"""

import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

# Importar app e modelos
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from banco_dados.modelos import Base, Usuario
from banco_dados.seed_tipos import popular_tipos


@pytest.fixture(scope='session')
def test_db():
    """Cria um banco de dados temporário para testes"""
    # Criar arquivo temporário para o banco de testes
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Criar engine com SQLite em memória para testes mais rápidos
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool
    )
    
    # Criar todas as tabelas
    Base.metadata.create_all(engine)
    
    # Popular tipos básicos
    popular_tipos(engine)
    
    yield engine
    
    # Limpar após os testes
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def db_session(test_db):
    """Cria uma sessão do banco para cada teste"""
    # Limpar todas as tabelas antes de cada teste
    from banco_dados.modelos import Usuario, Lixeira, Coleta, Sensor, Parceiro, TipoMaterial, TipoSensor, TipoColetor
    
    Session = sessionmaker(bind=test_db)
    session = Session()
    
    try:
        # Limpar dados (manter tipos que são populados no seed)
        session.query(Coleta).delete()
        session.query(Sensor).delete()
        session.query(Lixeira).delete()
        session.query(Usuario).delete()
        session.query(Parceiro).delete()
        session.commit()
        
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(test_db, db_session):
    """Cria um cliente de teste Flask"""
    # Configurar app para testes
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['LOGIN_DISABLED'] = False  # Manter autenticação ativa nos testes
    
    # Substituir sessão do banco pela sessão de teste
    app.config['DATABASE_SESSION'] = lambda: db_session
    
    # Criar cliente de teste
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def auth_headers(client, db_session):
    """Cria um usuário de teste e retorna headers de autenticação"""
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
    
    # Fazer login
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'senha': 'testpass123'
    })
    
    # Retornar headers (se necessário para futuras implementações)
    return {
        'Content-Type': 'application/json'
    }


@pytest.fixture
def admin_headers(client, db_session):
    """Cria um admin de teste e retorna headers de autenticação"""
    # Criar admin de teste
    admin = Usuario(
        username='admin',
        email='admin@example.com',
        admin=True,
        ativo=True
    )
    admin.set_senha('admin123')
    
    db_session.add(admin)
    db_session.commit()
    
    # Fazer login
    response = client.post('/auth/login', json={
        'username': 'admin',
        'senha': 'admin123'
    })
    
    return {
        'Content-Type': 'application/json'
    }


@pytest.fixture
def sample_lixeira_data():
    """Retorna dados de exemplo para criar uma lixeira"""
    return {
        'localizacao': 'Teste Localização',
        'nivel_preenchimento': 50.0,
        'status': 'OK',
        'latitude': -15.7942,
        'longitude': -47.8822
    }

@pytest.fixture
def create_lixeira(db_session):
    """Fixture factory para criar lixeiras de teste"""
    from banco_dados.modelos import Lixeira, Parceiro, TipoMaterial
    from banco_dados.utils import utc_now_naive
    from datetime import datetime
    
    def _create_lixeira(localizacao="Lixeira Teste", nivel=50.0, status="OK", lat=-15.7942, lon=-47.8822, parceiro_id=None, tipo_material_id=None):
        if parceiro_id is None:
            parceiro = db_session.query(Parceiro).first()
            if not parceiro:
                parceiro = Parceiro(nome="Parceiro Teste")
                db_session.add(parceiro)
                db_session.flush()
            parceiro_id = parceiro.id
        
        if tipo_material_id is None:
            tipo_material = db_session.query(TipoMaterial).first()
            if not tipo_material:
                tipo_material = TipoMaterial(nome="Material Teste")
                db_session.add(tipo_material)
                db_session.flush()
            tipo_material_id = tipo_material.id
        
        lixeira = Lixeira(
            localizacao=localizacao,
            nivel_preenchimento=nivel,
            status=status,
            latitude=lat,
            longitude=lon,
            parceiro_id=parceiro_id,
            tipo_material_id=tipo_material_id,
            ultima_coleta=utc_now_naive()
        )
        db_session.add(lixeira)
        db_session.commit()
        db_session.refresh(lixeira)
        return lixeira
    
    return _create_lixeira

