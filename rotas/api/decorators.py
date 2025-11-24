"""
Decorators da API - Dashboard-TRONIK
====================================
Decorators compartilhados para rotas da API.
"""

from functools import wraps
from flask import jsonify
from flask_login import login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Rate limiter será inicializado no app.py
# Aqui apenas exportamos a função get_remote_address
limiter = None  # Será inicializado no app.py


def admin_required(f):
    """Decorator para exigir que o usuário seja admin"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.admin:
            return jsonify({"erro": "Acesso negado. Apenas administradores."}), 403
        return f(*args, **kwargs)
    return decorated_function


def get_db():
    """Retorna uma sessão do banco de dados"""
    from flask import current_app
    SessionLocal = current_app.config.get('DATABASE_SESSION')
    if SessionLocal:
        return SessionLocal()
    else:
        # Fallback: criar sessão diretamente
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine('sqlite:///tronik.db')
        Session = sessionmaker(bind=engine)
        return Session()


def get_limiter():
    """Retorna o rate limiter se configurado"""
    from flask import current_app
    return current_app.config.get('RATE_LIMITER')


def rate_limit(limit_str):
    """
    Decorator condicional para rate limiting.
    Só aplica rate limiting se o limiter estiver configurado.
    """
    def decorator(f):
        if limiter is not None:
            return limiter.limit(limit_str)(f)
        return f
    return decorator

