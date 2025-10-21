"""
Dashboard-TRONIK - Aplicação Principal
=====================================

Este é o arquivo principal da aplicação Flask.
Aqui devem ser registradas todas as rotas e configurações básicas.

TODO para a equipe:
- Configurar Flask app
- Registrar blueprints das rotas
- Configurar banco de dados
- Implementar endpoints básicos
"""

# TODO: Importar Flask e outras dependências necessárias

# TODO: Criar instância da aplicação Flask

# TODO: Configurar CORS se necessário

# TODO: Configurar banco de dados

# TODO: Registrar blueprints das rotas

# TODO: Implementar rota principal (/)

# TODO: Implementar endpoints da API (/api/*)

# TODO: Configurar execução da aplicação

# import das bibliotecas necessárias
from flask import Flask, render_template, jsonify
from flask_cors import CORS 
import os 
import json 

# criação da instância da aplicação Flask
app = Flask(__name__)

# configuração do CORS para permitir requisições do frontend
CORS(app)

# configurações basicas da aplicação 
app.config['SECRET_KEY'] = 'dashboard-tronik-2025'
app.config['JSON_SORT_KEYS'] = False

# função para carregar dados mockados 
def carregar_dados_mock(): 
    """Carrega dados do mock do arquivo JSON"""
    try:
        with open('dados/sensores_mock.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"lixeiras": [], "configurações": {}, "historico_coletas": []}

# rota principal - Dashboard
@app.route('/')
def index():
    """Renderiza a pagina principal do dashboard"""
    return render_template('index.html')

# Rota para relatorios 
@app.route('/relatorios')
def relatorios():
    """Renderiza a pagina de relatorios"""
    return render_template('relatorios.html')

# API - Listar todas as lixeiras
@app.route('/api/lixeiras')
def api_lixeiras():
    """Endpoint para obter todas os coletores"""
    dados = carregar_dados_mock
    return jsonify(dados()['lixeiras'])

# API - obter lixeira especifica 
@app.route('/api/lixeira/<int:lixeira_id>')
def api_lixeira(lixeira_id): 
    """Endpoint para obter uma lixeira especifica"""
    dados = carregar_dados_mock()
    lixeira = next((l for l in dados['lixeiras'] if l['id'] == lixeira_id), None)

    if lixeira:
        return jsonify(lixeira)
    else: 
        return jsonify({"erro": "Lixeira nao encontrada"}), 404

# API - Obter configurações
@app.route('/api/configurações')
def api_configurações():
    """Endpoint para obter as configurações do sistema"""
    dados = carregar_dados_mock()
    return jsonify(dados['configurações'])

# API - obter historico de coletas 
@app.route('/api/historico')
def api_historico():
    """Endpoint para obter configurações do sistema"""
    dados = carregar_dados_mock()
    return jsonify(dados['configuracoes'])

# API - obter estatisticas gerais 
@app.route('/api/estatisticas')
def api_estatisticas(): 
    """Endpoint para obter estatisticas gerais"""
    dados = carregar_dados_mock()
    lixeiras = dados['lixeiras']

    total_lixeiras = len(lixeiras)
    lixeiras_alerta = len([l for l in lixeiras if l['nivel_preenchimento'] > 80])
    nivel_medio = sum(l['nivel_preenchimento'] for l in lixeiras) / total_lixeiras if total_lixeiras > 0 else 0

    estatisticas = {
        "total_lixeiras": total_lixeiras,
        "lixeiras_alerta": lixeiras_alerta,
        "nivel_medio": round(nivel_medio, 1),
        "coletas_hoje": len(dados['historico_coletas']) # simplificado para mock
    }

    return jsonify(estatisticas)

# Tratamento de erros 404
@app.errorhandler
def not_found(error):
    """Tratamento de paginas nao encontradas"""
    return render_template('404.html'), 404 

# Configurar execução da aplicação 
if __name__ == '__main__':
    # verificar se o arquivo de dados mock existe
    if not os.path.exists('dados/sensores_mock.json'):
        print("ERRO: Arquivo dados/sensores_mock.json nao encontrado!")
        print("Certifique-se de que o arquivo existe na pasta dados/")
        exit(1)

print("=" * 50)
print("Dashboard-TRONIK - Iniciando servidor...")
print("=" * 50)
print("Acesse http://localhost:5000")
print("API: http://localhost:5000/api/lixeiras")
print("=" * 50)

# executar aplicacao em modo debug
app.run(debug=True, host='0.0.0.0', port=5000)