"""
Compatibilidade de schema em bases já existentes (SQLite / PostgreSQL).

Adiciona colunas novas sem Alembic quando o deploy já tem tabelas antigas.
``create_all`` em app startup / jobs cria tabelas e colunas em DB novo; este módulo
aplica ``ALTER TABLE ... ADD COLUMN`` só quando a tabela já existe sem a coluna
(ex.: ``empresa_candidata.pipeline_id`` em SQLite não traz FK no ALTER).
"""

from __future__ import annotations

import contextlib
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

_LIXEIRA_FK_TABLES = ("coletas", "sensores")


def _migrar_lixeira_para_coletor(engine, insp) -> None:
    """Bases legadas: tabela ``lixeiras`` + FK ``lixeira_id`` → ``coletores`` + ``coletor_id``."""
    tables = set(insp.get_table_names())

    if "lixeiras" in tables and "coletores" in tables:
        with engine.begin() as conn:
            n_coletores = conn.execute(text("SELECT COUNT(*) FROM coletores")).scalar() or 0
            n_lixeiras = conn.execute(text("SELECT COUNT(*) FROM lixeiras")).scalar() or 0
            if n_lixeiras > 0 and n_coletores == 0:
                conn.execute(
                    text(
                        """
                        INSERT INTO coletores (
                            id, localizacao, nivel_preenchimento, status, ultima_coleta,
                            latitude, longitude, parceiro_id, tipo_material_id
                        )
                        SELECT
                            id, localizacao, nivel_preenchimento, status, ultima_coleta,
                            latitude, longitude, parceiro_id, tipo_material_id
                        FROM lixeiras
                        """
                    )
                )
                max_id = conn.execute(text("SELECT MAX(id) FROM coletores")).scalar()
                if max_id is not None:
                    try:
                        updated = conn.execute(
                            text(
                                "UPDATE sqlite_sequence SET seq = :seq WHERE name = 'coletores'"
                            ),
                            {"seq": int(max_id)},
                        ).rowcount
                        if not updated:
                            conn.execute(
                                text(
                                    "INSERT INTO sqlite_sequence (name, seq) VALUES ('coletores', :seq)"
                                ),
                                {"seq": int(max_id)},
                            )
                    except Exception:
                        logger.debug(
                            "sqlite_sequence nao atualizado para coletores (ignorado).",
                            exc_info=True,
                        )
                logger.info(
                    "Schema compat: copiados %s registros de lixeiras -> coletores.",
                    n_lixeiras,
                )

    for table in _LIXEIRA_FK_TABLES:
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "coletor_id" in cols or "lixeira_id" not in cols:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN coletor_id INTEGER"))
            conn.execute(
                text(f"UPDATE {table} SET coletor_id = lixeira_id WHERE coletor_id IS NULL")
            )
        logger.info("Schema compat: %s.lixeira_id copiado para coletor_id.", table)


def aplicar_compat_schema(engine) -> None:
    """Garante colunas esperadas pelo código atual."""
    insp = inspect(engine)
    _migrar_lixeira_para_coletor(engine, insp)
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

    # Resumo compacto da thread (memória de longo prazo)
    if is_pg:
        _add_column_if_missing("nik_conversas", "resumo_thread", "TEXT NULL")
    else:
        _add_column_if_missing("nik_conversas", "resumo_thread", "TEXT")

    # Metadados ricos da resposta (anexos, documento, fontes, traços) em JSON
    if is_pg:
        _add_column_if_missing("nik_conversas", "meta_resposta", "TEXT NULL")
    else:
        _add_column_if_missing("nik_conversas", "meta_resposta", "TEXT")

    # Relatórios longos podem exceder o antigo VARCHAR(8000); migrar para TEXT no PG
    if is_pg and "nik_conversas" in insp.get_table_names():
        with contextlib.suppress(Exception):
            col_resposta = next(
                (c for c in insp.get_columns("nik_conversas") if c["name"] == "resposta"),
                None,
            )
            tipo_atual = str(col_resposta["type"]).lower() if col_resposta else ""
            if col_resposta is not None and "text" not in tipo_atual:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE nik_conversas "
                            "ALTER COLUMN resposta TYPE TEXT USING resposta::text"
                        )
                    )
                logger.info("Schema compat: nik_conversas.resposta migrada para TEXT.")

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

    # Loló Account: tabela conta_comercial (DB legado sem create_all completo)
    if "conta_comercial" not in insp.get_table_names():
        with engine.begin() as conn:
            if is_pg:
                conn.execute(
                    text(
                        """
                        CREATE TABLE conta_comercial (
                            id SERIAL PRIMARY KEY,
                            cnpj VARCHAR(18) UNIQUE,
                            razao_social VARCHAR(255),
                            nome_fantasia VARCHAR(255),
                            parceiro_id INTEGER REFERENCES parceiros(id),
                            empresa_candidata_id INTEGER REFERENCES empresa_candidata(id),
                            criado_em TIMESTAMP,
                            atualizado_em TIMESTAMP
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE conta_comercial (
                            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                            cnpj VARCHAR(18),
                            razao_social VARCHAR(255),
                            nome_fantasia VARCHAR(255),
                            parceiro_id INTEGER,
                            empresa_candidata_id INTEGER,
                            criado_em DATETIME,
                            atualizado_em DATETIME
                        )
                        """
                    )
                )
        logger.info("Schema compat: tabela conta_comercial criada.")

    # Pipeline: vínculo com conta comercial (ganho/fechado)
    if is_pg:
        _add_column_if_missing(
            "pipeline",
            "conta_comercial_id",
            "INTEGER NULL REFERENCES conta_comercial(id)",
        )
    else:
        _add_column_if_missing("pipeline", "conta_comercial_id", "INTEGER")

    # Performance: composite index for priority-tier queries on score_prospeccao (1M+ rows)
    if "score_prospeccao" in insp.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_score_prospeccao_modelo_prio_score "
                "ON score_prospeccao (modelo_id, prioridade, score DESC)"
            ))
