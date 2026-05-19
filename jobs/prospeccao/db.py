"""Database helpers for prospection batch jobs."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from banco_dados.modelos import Base


_SESSION_FACTORY_CACHE: dict = {}


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///tronik.db")


def make_session_factory(echo: bool = False) -> sessionmaker[Session]:
    url = database_url()
    cache_key = (url, echo)
    if cache_key not in _SESSION_FACTORY_CACHE:
        # SQLite timeout and WAL configuration for concurrent access
        # - timeout: 60 seconds (default 5s is too short for long operations)
        # - check_same_thread: False allows multi-threaded access
        # - WAL mode: enables concurrent reads with writes
        # - PRAGMA synchronous=NORMAL: balances durability vs performance
        # - PRAGMA busy_timeout=60000: 60s wait before "database is locked" error
        engine = create_engine(
            url,
            echo=echo,
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
                # If pragma setup fails, log but don't crash engine creation
                cursor.close()
                raise

        Base.metadata.create_all(engine)
        _SESSION_FACTORY_CACHE[cache_key] = sessionmaker(bind=engine)
    return _SESSION_FACTORY_CACHE[cache_key]


@contextmanager
def session_scope(echo: bool = False) -> Iterator[Session]:
    SessionLocal = make_session_factory(echo=echo)
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
