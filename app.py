"""
Dashboard-TRONIK - Aplicação Principal
=====================================

Este é o arquivo principal da aplicação Flask.
Aqui devem ser registradas todas as rotas e configurações básicas.
"""

# Importações do Flask
from flask import Flask, request
from flask_cors import CORS
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from dotenv import load_dotenv
import os
import secrets
import logging

# Importações do SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Importações dos modelos
# Importar todos os modelos para garantir que as tabelas sejam criadas
from banco_dados.modelos import Base, Usuario, Lixeira, Sensor, Coleta

# Importações do sistema de inicialização
from banco_dados.inicializar import criar_banco, inserir_dados_iniciais

# Importações dos blueprints
from rotas.api import api_bp
from rotas.paginas import paginas_bp
from rotas.auth import auth_bp

# Carregar variáveis de ambiente
load_dotenv()

# Criação da instância da aplicação Flask
app = Flask(__name__, static_folder='estatico', static_url_path='/static')

# ========================================
# CONFIGURAÇÕES DE SEGURANÇA
# ========================================

# SECRET_KEY - CRÍTICO: Deve estar em variável de ambiente
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    # Gerar uma chave temporária se não estiver configurada (apenas desenvolvimento)
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    print("⚠️  AVISO: SECRET_KEY não configurada. Usando chave temporária.")
    print("⚠️  Configure SECRET_KEY no arquivo .env para produção!")

# Configurações básicas
app.config['JSON_SORT_KEYS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora

# Configuração de ambiente
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
app.config['DEBUG'] = os.getenv('DEBUG', 'false').lower() == 'true'

# Configuração de CORS - Restrito a origens específicas
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000')
if FLASK_ENV == 'development':
    # Em desenvolvimento, permite localhost
    CORS(app, origins=cors_origins.split(','), supports_credentials=True)
else:
    # Em produção, apenas origens específicas
    CORS(app, origins=cors_origins.split(','), supports_credentials=True)

# Configuração de cookies de sessão
if FLASK_ENV == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True  # Apenas HTTPS
else:
    app.config['SESSION_COOKIE_SECURE'] = False

# ========================================
# FLASK-LOGIN (Autenticação)
# ========================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'  # Proteção contra session fixation

@login_manager.user_loader
def load_user(user_id):
    """Carrega usuário para sessão"""
    db = app.config.get('DATABASE_SESSION')
    if db:
        session = db()
        try:
            return session.query(Usuario).get(int(user_id))
        finally:
            session.close()
    return None

# ========================================
# FLASK-LIMITER (Rate Limiting)
# ========================================
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URL', 'memory://'),
    enabled=os.getenv('RATELIMIT_ENABLED', 'true').lower() == 'true'
)

# ========================================
# FLASK-TALISMAN (Headers de Segurança)
# ========================================
# Adiciona headers de segurança HTTP
talisman = Talisman(
    app,
    force_https=FLASK_ENV == 'production',
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,  # 1 ano
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data: https:",
        'font-src': "'self' data:",
    },
    content_security_policy_nonce_in=['script-src']
)

# ========================================
# LOGGING
# ========================================
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ========================================
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine))

# Tornar SessionLocal disponível globalmente para os blueprints
app.config['DATABASE_SESSION'] = SessionLocal

# Criar/atualizar banco e tabelas
# Base.metadata.create_all() cria apenas tabelas que não existem, então é seguro chamar sempre
db_exists = os.path.exists('tronik.db')
if not db_exists:
    logger.info("Banco de dados não encontrado. Criando...")
else:
    logger.info("Banco de dados encontrado. Verificando/atualizando tabelas...")

# Sempre criar todas as tabelas (SQLAlchemy só cria as que não existem)
Base.metadata.create_all(engine)

# Se o banco não existia, inserir dados iniciais
if not db_exists:
    # Tentar inserir dados iniciais
    caminho_json = 'banco_dados/dados/sensores_mock.json'
    if not os.path.exists(caminho_json):
        caminho_json = 'dados/sensores_mock.json'
    if os.path.exists(caminho_json):
        inserir_dados_iniciais(engine, caminho_json)
    else:
        logger.warning("Arquivo de dados mock não encontrado. Banco criado vazio.")

# Sempre verificar/criar usuário admin (pode não existir mesmo se o banco existir)
from banco_dados.inicializar import criar_usuario_admin
criar_usuario_admin(engine)

# ========================================
# REGISTRAR BLUEPRINTS
# ========================================
app.register_blueprint(auth_bp)  # Autenticação primeiro
app.register_blueprint(api_bp)
app.register_blueprint(paginas_bp)

# ========================================
# TRATAMENTO DE ERROS
# ========================================
@app.errorhandler(404)
def not_found(error):
    """Tratamento de páginas não encontradas"""
    from flask import jsonify
    logger.warning(f"404 - Página não encontrada: {request.path}")
    if request.path.startswith('/api/'):
        return jsonify({"erro": "Endpoint não encontrado"}), 404
    else:
        return "<h1>404 - Página não encontrada</h1><p>A página que você procura não existe.</p>", 404

@app.errorhandler(403)
def forbidden(error):
    """Tratamento de acesso negado"""
    from flask import jsonify
    logger.warning(f"403 - Acesso negado: {request.path}")
    if request.path.startswith('/api/'):
        return jsonify({"erro": "Acesso negado"}), 403
    else:
        return "<h1>403 - Acesso Negado</h1><p>Você não tem permissão para acessar esta página.</p>", 403

@app.errorhandler(429)
def ratelimit_handler(e):
    """Tratamento de rate limit excedido"""
    from flask import jsonify
    logger.warning(f"429 - Rate limit excedido: {request.remote_addr}")
    return jsonify({"erro": "Muitas requisições. Tente novamente mais tarde."}), 429

@app.errorhandler(500)
def internal_error(error):
    """Tratamento de erros internos"""
    from flask import jsonify
    logger.error(f"500 - Erro interno: {str(error)}")
    if request.path.startswith('/api/'):
        return jsonify({"erro": "Erro interno do servidor"}), 500
    else:
        return "<h1>500 - Erro Interno</h1><p>Ocorreu um erro no servidor.</p>", 500 

# ========================================
# EXECUÇÃO DA APLICAÇÃO
# ========================================
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Dashboard-TRONIK - Iniciando servidor...")
    logger.info("=" * 50)
    logger.info(f"Ambiente: {FLASK_ENV}")
    logger.info(f"Banco de dados: {DATABASE_URL}")
    logger.info(f"Rate Limiting: {'Ativado' if limiter.enabled else 'Desativado'}")
    logger.info(f"Acesse: http://localhost:5000")
    logger.info(f"Login: http://localhost:5000/auth/login")
    logger.info("=" * 50)
    
    # Executar aplicação
    app.run(
        debug=app.config['DEBUG'],
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )