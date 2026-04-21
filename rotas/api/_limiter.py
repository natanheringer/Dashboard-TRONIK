"""
Flask-Limiter singleton.
========================

Por que existe este modulo:
- Os blueprints da API usam `@decorators.rate_limit(...)` em tempo de import.
- Se o `Limiter` so existir *depois* que os blueprints forem importados
  (como acontecia antes), o decorator nao tem a quem delegar o `.limit(...)`,
  e o rate limiting fica silenciosamente desativado.
- A solucao idiomatica do Flask-Limiter e instanciar o Limiter sem um `app`
  vinculado, e depois chamar `limiter.init_app(app)` no boot. Assim o objeto
  existe cedo (e os decorators podem referenciar ele), e a ligacao ao app
  acontece no momento certo.

Uso:
    from rotas.api._limiter import limiter

    @limiter.limit("10 per minute")
    def minha_rota(): ...

    # em app.py, uma vez:
    limiter.init_app(app)
"""

from __future__ import annotations

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _rate_limiting_enabled() -> bool:
    return os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URL", "memory://"),
    enabled=_rate_limiting_enabled(),
)
