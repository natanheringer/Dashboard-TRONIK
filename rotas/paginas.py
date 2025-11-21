"""
Rotas das Páginas - Dashboard-TRONIK
===================================

Rotas para as páginas web do dashboard.
Gerencia a navegação e renderização das páginas.
"""

from flask import Blueprint, render_template
from flask_login import login_required

# Criar blueprint das páginas
paginas_bp = Blueprint('paginas', __name__)

@paginas_bp.route('/')
@login_required
def index():
    """Renderiza a página principal do dashboard"""
    return render_template('index.html')

@paginas_bp.route('/relatorios')
@login_required
def relatorios():
    """Renderiza a página de relatórios"""
    return render_template('relatorios.html')

@paginas_bp.route('/configuracoes')
@login_required
def configuracoes():
    """Renderiza a página de configurações"""
    return render_template('configuracoes.html')

@paginas_bp.route('/mapa')
@login_required
def mapa():
    """Renderiza a página de mapa com localização das lixeiras"""
    return render_template('mapa.html')

@paginas_bp.route('/sobre')
def sobre():
    """Renderiza a página sobre o projeto (pública)"""
    return render_template('sobre.html')

@paginas_bp.route('/notificacoes')
@login_required
def notificacoes():
    """Renderiza a página de notificações"""
    return render_template('notificacoes.html')
