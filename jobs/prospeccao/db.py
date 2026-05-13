"""Database helpers for prospection batch jobs."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from banco_dados.modelos import Base


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///tronik.db")


def make_session_factory(echo: bool = False) -> sessionmaker[Session]:
    engine = create_engine(database_url(), echo=echo)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


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
