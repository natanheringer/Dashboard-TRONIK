"""
Dashboard-TRONIK - Aplicação Principal
=====================================

Este é o arquivo principal da aplicação Flask.
Aqui devem ser registradas todas as rotas e configurações básicas.
"""

# Importações do Flask
from flask import Flask, request
from flask_cors import CORS

# Importações do SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Importações dos modelos
from banco_dados.modelos import Base

# Importações do sistema de inicialização
from banco_dados.inicializar import criar_banco, inserir_dados_iniciais

# Importações dos blueprints
from rotas.api import api_bp
from rotas.paginas import paginas_bp

# Outras importações
import os

# Criação da instância da aplicação Flask
app = Flask(__name__, static_folder='estatico', static_url_path='/static')

# Configuração do CORS para permitir requisições do frontend
CORS(app)

# Configurações básicas da aplicação
app.config['SECRET_KEY'] = 'dashboard-tronik-2025'
app.config['JSON_SORT_KEYS'] = False

# Configuração do banco de dados SQLite
DATABASE_URL = 'sqlite:///tronik.db'
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine))

# Tornar SessionLocal disponível globalmente para os blueprints
app.config['DATABASE_SESSION'] = SessionLocal

# Criar banco e tabelas se não existirem
if not os.path.exists('tronik.db'):
    print("Banco de dados não encontrado. Criando...")
    criar_banco(DATABASE_URL)
    # Tentar inserir dados iniciais
    caminho_json = 'banco_dados/dados/sensores_mock.json'
    if not os.path.exists(caminho_json):
        caminho_json = 'dados/sensores_mock.json'
    if os.path.exists(caminho_json):
        inserir_dados_iniciais(engine, caminho_json)
    else:
        print("AVISO: Arquivo de dados mock não encontrado. Banco criado vazio.")

# Registrar blueprints
app.register_blueprint(api_bp)
app.register_blueprint(paginas_bp)

# Tratamento de erros 404
@app.errorhandler(404)
def not_found(error):
    """Tratamento de páginas não encontradas"""
    from flask import jsonify
    # Retorna JSON para APIs e mensagem simples para páginas
    if request.path.startswith('/api/'):
        return jsonify({"erro": "Endpoint não encontrado"}), 404
    else:
        return "<h1>404 - Página não encontrada</h1><p>A página que você procura não existe.</p>", 404 

# Configurar execução da aplicação
if __name__ == '__main__':
    print("=" * 50)
    print("Dashboard-TRONIK - Iniciando servidor...")
    print("=" * 50)
    print("Banco de dados: SQLite (tronik.db)")
    print("Acesse: http://localhost:5000")
    print("API: http://localhost:5000/api/lixeiras")
    print("=" * 50)
    
    # Executar aplicação em modo debug
    app.run(debug=True, host='0.0.0.0', port=5000)