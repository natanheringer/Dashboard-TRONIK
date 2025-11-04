"""
Rotas das Páginas - Dashboard-TRONIK
===================================

Rotas para as páginas web do dashboard.
Gerencia a navegação e renderização das páginas.
"""

from flask import Blueprint, render_template

# Criar blueprint das páginas
paginas_bp = Blueprint('paginas', __name__)

@paginas_bp.route('/')
def index():
    """Renderiza a página principal do dashboard"""
    return render_template('index.html')

@paginas_bp.route('/relatorios')
def relatorios():
    """Renderiza a página de relatórios"""
    return render_template('relatorios.html')

@paginas_bp.route('/configuracoes')
def configuracoes():
    """Renderiza a página de configurações"""
    return render_template('configuracoes.html')

@paginas_bp.route('/sobre')
def sobre():
    """Renderiza a página sobre o projeto"""
    return render_template('sobre.html')
