"""
Utilitário de Sessão de Banco - Dashboard-TRONIK
=================================================
Helper para obter sessão do banco de dados nos serviços.
"""

import os

from flask import current_app, has_app_context
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_SESSION_FACTORY_CACHE: dict = {}


def get_db_session():
    """
    Retorna uma sessão do banco de dados.
    Funciona dentro e fora do contexto Flask.
    """
    # Tentar obter do contexto Flask primeiro
    if has_app_context():
        SessionLocal = current_app.config.get('DATABASE_SESSION')
        if SessionLocal:
            return SessionLocal()

    # Fallback: criar sessão com cache singleton
    database_url = os.getenv('DATABASE_URL', 'sqlite:///banco_dados/tronik.db')
    cache_key = database_url

    if cache_key not in _SESSION_FACTORY_CACHE:
        engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={
                "timeout": 60,
                "check_same_thread": False,
            },
        )

        # Event listener to configure SQLite pragmas on each new connection
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=60000")
                cursor.close()
            except Exception:
                cursor.close()
                raise

        _SESSION_FACTORY_CACHE[cache_key] = sessionmaker(bind=engine)

    SessionLocal = _SESSION_FACTORY_CACHE[cache_key]
    return SessionLocal()

