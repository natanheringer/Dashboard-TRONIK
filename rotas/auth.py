"""
Rotas de Autenticação - Dashboard-TRONIK
========================================

Gerencia login, logout e registro de usuários.
"""

import logging
from urllib.parse import urlparse

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from banco_dados.modelos import Usuario
from banco_dados.seguranca import sanitizar_string
from banco_dados.utils import utc_now_naive

# Configurar logging
logger = logging.getLogger(__name__)

# Criar blueprint de autenticação
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _redirect_pos_login_seguro(next_page: str | None, default_url: str):
    """Evita open redirect via parâmetro `next`."""
    if not next_page:
        return redirect(default_url)
    if not next_page.startswith("/") or next_page.startswith("//"):
        return redirect(default_url)
    parsed = urlparse(next_page)
    if parsed.scheme or parsed.netloc:
        return redirect(default_url)
    return redirect(next_page)


def _destino_pos_login(usuario=None):
    """Destino padrão após login conforme papel do usuário."""
    user = usuario if usuario is not None else current_user
    if getattr(user, 'admin', False):
        return url_for('preview.dashboard_home')
    return url_for('preview.parceiro')

# Função auxiliar para obter sessão do banco
def get_db():
    """Retorna uma sessão do banco de dados"""
    from flask import current_app
    SessionLocal = current_app.config.get('DATABASE_SESSION')
    if SessionLocal:
        return SessionLocal()
    else:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine('sqlite:///tronik.db')
        Session = sessionmaker(bind=engine)
        return Session()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página e endpoint de login"""
    if request.method == 'GET':
        # Se já estiver logado, redireciona
        if current_user.is_authenticated:
            return redirect(_destino_pos_login())
        return render_template('login.html')

    # POST - Processar login
    try:
        dados = request.get_json() if request.is_json else request.form

        username = sanitizar_string(dados.get('username', ''))
        senha = dados.get('senha', '')

        if not username or not senha:
            if request.is_json:
                return jsonify({"erro": "Username e senha são obrigatórios"}), 400
            flash("Username e senha são obrigatórios", "error")
            return render_template('login.html')

        db = get_db()
        try:
            # Buscar usuário por username ou email
            usuario = db.query(Usuario).filter(
                (Usuario.username == username) | (Usuario.email == username)
            ).first()

            if not usuario or not usuario.verificar_senha(senha):
                # Logar tentativa sem expor informações sensíveis
                logger.warning(f"Tentativa de login falhada para username: {username[:3]}***")
                if request.is_json:
                    return jsonify({"erro": "Credenciais inválidas"}), 401
                flash("Credenciais inválidas", "error")
                return render_template('login.html')

            if not usuario.ativo:
                logger.warning(f"Tentativa de login com usuário inativo: {username}")
                if request.is_json:
                    return jsonify({"erro": "Usuário inativo"}), 403
                flash("Usuário inativo. Entre em contato com o administrador.", "error")
                return render_template('login.html')

            # Login bem-sucedido
            usuario.ultimo_login = utc_now_naive()
            db.commit()

            login_user(usuario, remember=bool(dados.get('remember', False)))

            logger.info(f"Login bem-sucedido: {usuario.username}")

            if request.is_json:
                from flask import make_response
                resposta = make_response(jsonify({
                    "mensagem": "Login realizado com sucesso",
                    "usuario": {
                        "id": usuario.id,
                        "username": usuario.username,
                        "email": usuario.email,
                        "admin": usuario.admin
                    }
                }), 200)
                # [SEGURANÇA] Evitar cache de dados sensíveis de autenticação
                resposta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                resposta.headers['Pragma'] = 'no-cache'
                resposta.headers['Expires'] = '0'
                return resposta

            next_page = request.args.get('next')
            return _redirect_pos_login_seguro(
                next_page, _destino_pos_login(usuario)
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Erro no login: {str(e)}")
        if request.is_json:
            return jsonify({"erro": "Erro interno do servidor"}), 500
        flash("Erro ao processar login. Tente novamente.", "error")
        return render_template('login.html')


@auth_bp.route('/logout', methods=['POST', 'GET'])
@login_required
def logout():
    """Endpoint de logout"""
    try:
        username = current_user.username if current_user.is_authenticated else "desconhecido"
        logout_user()
        logger.info(f"Logout realizado: {username}")

        if request.is_json:
            from flask import make_response
            resposta = make_response(jsonify({"mensagem": "Logout realizado com sucesso"}), 200)
            # [SEGURANÇA] Evitar cache de dados sensíveis de autenticação
            resposta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resposta.headers['Pragma'] = 'no-cache'
            resposta.headers['Expires'] = '0'
            return resposta

        flash("Logout realizado com sucesso", "success")
        return redirect(url_for('auth.login'))
    except Exception as e:
        logger.error(f"Erro no logout: {str(e)}")
        if request.is_json:
            return jsonify({"erro": "Erro ao fazer logout"}), 500
        return redirect(url_for('paginas.index'))


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """
    Página e endpoint de registro - DESABILITADO POR SEGURANÇA

    Registro público foi desabilitado por segurança.
    Para criar novos usuários ou alterar senhas, use:
    - scripts/alterar_senha_usuarios.py
    - Ou crie manualmente via banco de dados
    """
    logger.warning(f"Tentativa de acesso ao registro público bloqueada de {request.remote_addr}")

    if request.is_json:
        return jsonify({
            "erro": "Registro público desabilitado por segurança. Entre em contato com o administrador."
        }), 403

    flash("Registro público desabilitado por segurança. Entre em contato com o administrador.", "error")
    return redirect(url_for('auth.login'))


@auth_bp.route('/usuario/atual', methods=['GET'])
@login_required
def usuario_atual():
    """Retorna informações do usuário atual"""
    from flask import make_response

    resposta = make_response(jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "nome_completo": current_user.nome_completo,
        "admin": current_user.admin,
        "ativo": current_user.ativo
    }), 200)

    # [SEGURANÇA] Evitar cache de dados sensíveis de autenticação
    resposta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resposta.headers['Pragma'] = 'no-cache'
    resposta.headers['Expires'] = '0'

    return resposta

