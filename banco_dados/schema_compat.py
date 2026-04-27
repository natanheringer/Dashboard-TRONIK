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
    dialect = engine.dialect.name

    def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
        if table not in insp.get_table_names():
            return
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if column in table_cols:
            return
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        logger.info("Schema compat: coluna %s.%s adicionada.", table, column)

    if "api_token" not in cols:
        if dialect in ("postgresql", "postgres"):
            _add_column_if_missing("sensores", "api_token", "VARCHAR(128) NULL")
        else:
            _add_column_if_missing("sensores", "api_token", "VARCHAR(128)")

    # Conversas da Nik: thread para memória por tópico
    if dialect in ("postgresql", "postgres"):
        _add_column_if_missing("nik_conversas", "thread_id", "VARCHAR(80) NULL")
    else:
        _add_column_if_missing("nik_conversas", "thread_id", "VARCHAR(80)")
