"""
Configuração do Pytest - Dashboard-TRONIK
==========================================
Configuração compartilhada para todos os testes.
"""

import contextlib
import os
import sys
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
    # Windows: o driver SQLite por vezes mantém o ficheiro aberto.
    with contextlib.suppress(PermissionError):
        os.unlink(db_path)


@pytest.fixture(scope='function')
def db_session(test_db):
    """Cria uma sessão do banco para cada teste"""
    # Limpar todas as tabelas antes de cada teste
    from banco_dados.modelos import (
        Coleta,
        Coletor,
        ContaComercial,
        EmpresaCandidata,
        FeatureSnapshotProspeccao,
        FontePublicaRegistro,
        LeituraSensor,
        LocalCandidato,
        ModeloProspeccao,
        NarrativaGerada,
        NikConversa,
        NikRelatorioGerado,
        Notificacao,
        Parceiro,
        PredicaoEnchimento,
        # 14 Tabelas ML
        ScoreProspeccao,
        Sensor,
        SolicitacaoColetor,
        TronikScore,
        Usuario,
    )

    Session = sessionmaker(bind=test_db)
    session = Session()

    try:
        # Limpar dados (manter tipos que são populados no seed)
        # Ordem de limpeza: filhos antes dos pais (respeitando ForeignKeys)

        # Tier 1: Scores (dependem de FeatureSnapshotProspeccao e ModeloProspeccao)
        session.query(ScoreProspeccao).delete()

        # Tier 2: Snapshots de Features (dependem de Empresa e Local)
        session.query(FeatureSnapshotProspeccao).delete()

        # Tier 3: Modelos de Prospecção
        session.query(ModeloProspeccao).delete()

        # Tier 4: Locais Candidatos (dependem de Empresa, tem ondelete=CASCADE)
        session.query(LocalCandidato).delete()

        # Tier 5: Conta Comercial (depende de Empresa)
        session.query(ContaComercial).delete()

        # Tier 6: Empresas Candidatas, Fonte Pública (não têm dependentes além de LocalCandidato e ContaComercial)
        session.query(EmpresaCandidata).delete()
        session.query(FontePublicaRegistro).delete()

        # Tier 7: Leitura Sensor, Predições e Scores TRONIK (dependem de Coletor/Sensor)
        session.query(LeituraSensor).delete()
        session.query(PredicaoEnchimento).delete()
        session.query(TronikScore).delete()
        session.query(Notificacao).delete()

        # Tier 8: Narrativas, Nik Reports, Nik Conversas (dependem de Parceiro/Usuario)
        session.query(NarrativaGerada).delete()
        session.query(NikRelatorioGerado).delete()
        session.query(NikConversa).delete()

        # Tier 9: Solicitação Coletor
        session.query(SolicitacaoColetor).delete()

        # Limpeza das tabelas originais (não-ML)
        session.query(Coleta).delete()
        session.query(Sensor).delete()
        session.query(Coletor).delete()
        session.query(Usuario).delete()
        session.query(Parceiro).delete()
        session.commit()

        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(test_db, db_session, monkeypatch):
    """Cria um cliente de teste Flask"""
    monkeypatch.setenv("TELEMETRIA_ALLOW_NO_TOKEN", "true")
    # Configurar app para testes
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key-with-32-plus-chars!!'
    app.config['LOGIN_DISABLED'] = False  # Manter autenticação ativa nos testes

    # Substituir sessão do banco pela sessão de teste
    app.config['DATABASE_SESSION'] = lambda: db_session

    # Desabilitar rate limiting em testes (o limiter singleton ja esta ligado ao app)
    from rotas.api._limiter import limiter as api_limiter
    api_limiter.enabled = False

    # Criar cliente de teste
    with app.test_client() as client, app.app_context():
        yield client


@pytest.fixture
def auth_client(client, db_session):
    """Cliente Flask com sessão autenticada (usuário comum) para GETs da API."""
    u = Usuario(
        username="leitor_api",
        email="leitor_api@test.local",
        ativo=True,
        admin=False,
    )
    u.set_senha("LeitorApi123!")
    db_session.add(u)
    db_session.commit()
    r = client.post(
        "/auth/login",
        json={"username": "leitor_api", "senha": "LeitorApi123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


@pytest.fixture
def admin_client(client, db_session):
    """Cliente Flask autenticado como administrador."""
    admin = Usuario(
        username="admin_api",
        email="admin_api@test.local",
        ativo=True,
        admin=True,
    )
    admin.set_senha("AdminApi123!")
    db_session.add(admin)
    db_session.commit()
    r = client.post(
        "/auth/login",
        json={"username": "admin_api", "senha": "AdminApi123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


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
    """Retorna dados de exemplo para criar uma coletor"""
    return {
        'localizacao': 'Teste Localização',
        'nivel_preenchimento': 50.0,
        'status': 'OK',
        'latitude': -15.7942,
        'longitude': -47.8822
    }

@pytest.fixture
def create_lixeira(db_session):
    """Fixture factory para criar coletores de teste"""

    from banco_dados.modelos import Coletor, Parceiro, TipoMaterial
    from banco_dados.utils import utc_now_naive

    def _create_lixeira(localizacao="Coletor Teste", nivel=50.0, status="OK", lat=-15.7942, lon=-47.8822, parceiro_id=None, tipo_material_id=None):
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

        coletor = Coletor(
            localizacao=localizacao,
            nivel_preenchimento=nivel,
            status=status,
            latitude=lat,
            longitude=lon,
            parceiro_id=parceiro_id,
            tipo_material_id=tipo_material_id,
            ultima_coleta=utc_now_naive()
        )
        db_session.add(coletor)
        db_session.commit()
        db_session.refresh(coletor)
        return coletor

    return _create_lixeira

