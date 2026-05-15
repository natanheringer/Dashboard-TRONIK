"""
Utilitário de Sessão de Banco - Dashboard-TRONIK
=================================================
Helper para obter sessão do banco de dados nos serviços.
"""

from flask import current_app, has_app_context
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os


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

    # Fallback: criar sessão diretamente com configurações de concorrência
    database_url = os.getenv('DATABASE_URL', 'sqlite:///banco_dados/tronik.db')
    engine = create_engine(
        database_url,
        echo=False,
        connect_args={
            "timeout": 60,
            "check_same_thread": False,
        },
    )

    # Enable WAL mode for concurrent access
    with engine.begin() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

    Session = sessionmaker(bind=engine)
    return Session()

