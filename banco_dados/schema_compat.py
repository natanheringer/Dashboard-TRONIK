"""
Compatibilidade de schema em bases já existentes (SQLite / PostgreSQL).

Adiciona colunas novas sem Alembic quando o deploy já tem tabelas antigas.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def aplicar_compat_schema(engine) -> None:
    """Garante colunas esperadas pelo código atual."""
    insp = inspect(engine)
    if "sensores" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("sensores")}
    if "api_token" in cols:
        return

    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("ALTER TABLE sensores ADD COLUMN api_token VARCHAR(128)"))
        elif dialect in ("postgresql", "postgres"):
            conn.execute(
                text("ALTER TABLE sensores ADD COLUMN api_token VARCHAR(128) NULL")
            )
        else:
            conn.execute(text("ALTER TABLE sensores ADD COLUMN api_token VARCHAR(128)"))
    logger.info("Schema compat: coluna sensores.api_token adicionada.")
