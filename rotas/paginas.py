"""
Rotas das Páginas - Dashboard-TRONIK
===================================

Rotas para as páginas web do dashboard.
Gerencia a navegação e renderização das páginas.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

# Criar blueprint das páginas
paginas_bp = Blueprint('paginas', __name__)

@paginas_bp.route('/')
def index():
    """Primeira página do site: landing de preview (marketing v2)."""
    return redirect(url_for('preview.landing_preview'))


@paginas_bp.route('/dashboard')
@login_required
def dashboard():
    """Renderiza a página principal do dashboard (protegida por login)."""
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
    """Renderiza a página de mapa com localização das coletores"""
    return render_template('mapa.html')

@paginas_bp.route('/sobre')
def sobre():
    """Renderiza a página sobre o projeto (pública)"""
    return render_template('sobre.html')

@paginas_bp.route('/nik-public')
def nik_public():
    """Nik Pública — blocos educativos gerados (antes /landing)."""
    return render_template('landing/landing.html')


@paginas_bp.route('/landing')
def landing_redirect():
    """Compatibilidade: antiga URL da Nik pública."""
    return redirect(url_for('paginas.nik_public'), code=301)

@paginas_bp.route('/notificacoes')
@login_required
def notificacoes():
    """Renderiza a página de notificações"""
    return render_template('notificacoes.html')

@paginas_bp.route('/comercial')
@login_required
def comercial():
    """Renderiza a página do dashboard comercial"""
    return render_template('comercial.html')

@paginas_bp.route('/crm')
@login_required
def crm():
    """Renderiza a página do CRM"""
    return render_template('crm.html')

@paginas_bp.route('/contratos')
@login_required
def contratos():
    """Renderiza a página de contratos"""
    return render_template('contratos.html')
