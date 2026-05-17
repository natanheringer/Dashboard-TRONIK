"""
Compatibilidade de schema em bases já existentes (SQLite / PostgreSQL).

Adiciona colunas novas sem Alembic quando o deploy já tem tabelas antigas.
``create_all`` em app startup / jobs cria tabelas e colunas em DB novo; este módulo
aplica ``ALTER TABLE ... ADD COLUMN`` só quando a tabela já existe sem a coluna
(ex.: ``empresa_candidata.pipeline_id`` em SQLite não traz FK no ALTER).
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_PARCEIRO_ID_TABLES = (
    "usuarios",
    "coletores",
    "coletas",
    "contratos_recorrentes",
    "narrativas_geradas",
    "nik_relatorios_gerados",
)


def aplicar_compat_schema(engine) -> None:
    """Garante colunas esperadas pelo código atual."""
    insp = inspect(engine)
    dialect = engine.dialect.name
    is_pg = dialect in ("postgresql", "postgres")

    def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
        if table not in insp.get_table_names():
            return
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if column in table_cols:
            return
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        logger.info("Schema compat: coluna %s.%s adicionada.", table, column)

    if "sensores" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("sensores")}
        if "api_token" not in cols:
            if is_pg:
                _add_column_if_missing("sensores", "api_token", "VARCHAR(128) NULL")
            else:
                _add_column_if_missing("sensores", "api_token", "VARCHAR(128)")

    # Conversas da Nik: thread para memória por tópico
    if is_pg:
        _add_column_if_missing("nik_conversas", "thread_id", "VARCHAR(80) NULL")
    else:
        _add_column_if_missing("nik_conversas", "thread_id", "VARCHAR(80)")

    # Prospecção: vínculo persistido empresa_candidata -> pipeline CRM (ganho/fechado)
    if "empresa_candidata" in insp.get_table_names():
        if is_pg:
            _add_column_if_missing(
                "empresa_candidata",
                "pipeline_id",
                "INTEGER NULL REFERENCES pipeline(id)",
            )
        else:
            # SQLite: ADD COLUMN não aplica FK; create_all em DB novo já cria a coluna.
            _add_column_if_missing("empresa_candidata", "pipeline_id", "INTEGER")

    # Parceiros: CNPJ opcional (fundação Account; unique/index em DB novo via create_all)
    if dialect in ("postgresql", "postgres"):
        _add_column_if_missing("parceiros", "cnpj", "VARCHAR(18) NULL")
    else:
        _add_column_if_missing("parceiros", "cnpj", "VARCHAR(18)")

    # Multi-parceiro: coluna parceiro_id em tabelas legadas
    for table in _PARCEIRO_ID_TABLES:
        if is_pg:
            _add_column_if_missing(
                table,
                "parceiro_id",
                "INTEGER NULL REFERENCES parceiros(id)",
            )
        else:
            _add_column_if_missing(table, "parceiro_id", "INTEGER")
