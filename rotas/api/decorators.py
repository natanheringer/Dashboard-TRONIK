"""
Decorators e helpers compartilhados da API.
===========================================

Ponto unico de verdade para:
- `admin_required`: exige usuario admin autenticado.
- `get_db`: abre uma sessao do banco a partir do config do app.
- `rate_limit`: wrapper em cima do Flask-Limiter singleton (`_limiter.limiter`).

O `rate_limit` antigo consultava uma variavel `limiter = None` que so era
atribuida em `app.py` depois do import dos blueprints. Resultado: em tempo
de decoracao o limiter era sempre `None` e o rate limit *nunca* era aplicado.
Agora delegamos direto ao singleton, que ja existe no momento do import.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import current_app, jsonify
from flask_login import current_user, login_required

from rotas.api._limiter import limiter as _limiter

# Reexportar o limiter para codigo legado que faz `decorators.limiter`
limiter = _limiter


def admin_required(f: Callable) -> Callable:
    """Exige usuario autenticado com flag `admin=True`."""

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.admin:
            return jsonify({"erro": "Acesso negado. Apenas administradores."}), 403
        return f(*args, **kwargs)

    return decorated_function


def get_db():
    """Retorna uma sessao do banco de dados configurada no app.

    Levanta RuntimeError em vez de cair num SQLite hardcoded: se a sessao
    nao estiver configurada, queremos falhar cedo em vez de mascarar bug
    de configuracao.
    """
    session_factory = current_app.config.get("DATABASE_SESSION")
    if session_factory is None:
        raise RuntimeError(
            "DATABASE_SESSION nao configurada no app. "
            "Confira banco_dados.inicializar / app.py."
        )
    return session_factory()


def get_limiter():
    """Retorna o Flask-Limiter singleton (com `.enabled` respeitando env)."""
    return _limiter


def rate_limit(limit_str: str) -> Callable[[Callable], Callable]:
    """Aplica `limiter.limit(limit_str)` ao endpoint.

    Equivalente a `@limiter.limit(limit_str)`, mas mantemos a funcao para
    compatibilidade com o codigo existente e para termos um ponto central
    caso queiramos trocar de implementacao de rate limiting.
    """
    return _limiter.limit(limit_str)
