#!/usr/bin/env python3
"""Importa SOMENTE tabelas de prospecção (SQLite -> PostgreSQL).

Não mexe em coletores, coletas, usuarios, etc.

Uso:
    export RAILWAY_DB="postgresql://user:pass@host:port/railway"
    python scripts/importar_prospeccao_postgres.py --sqlite tronik-2gb.db

Requisitos: psycopg[binary], sqlalchemy (requirements.txt)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TABELAS = (
    "empresa_candidata",
    "local_candidato",
    "feature_snapshot_prospeccao",
    "modelo_prospeccao",
    "score_prospeccao",
)

LOTE = 2000


def _pg_url(raw: str) -> str:
    url = raw.strip()
    if "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _sqlite_url(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise FileNotFoundError(p)
    return f"sqlite:///{p}"


def _assert_empty(session, tabela: str, force: bool) -> None:
    n = session.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar() or 0
    if n > 0 and not force:
        raise SystemExit(
            f"Abortado: {tabela} já tem {n} linhas no Postgres. "
            "Use --force se souber o que está fazendo."
        )
    if n > 0 and force:
        session.execute(text(f"DELETE FROM {tabela}"))
        session.commit()
        logger.warning("DELETE FROM %s (%s linhas removidas)", tabela, n)


def _bool_cols(engine, tabela: str) -> set[str]:
    insp = inspect(engine)
    out: set[str] = set()
    for col in insp.get_columns(tabela):
        t = str(col["type"]).upper()
        if "BOOL" in t:
            out.add(col["name"])
    return out


def _import_table(sqlite_sess, pg_sess, pg_engine, tabela: str) -> int:
    bool_cols = _bool_cols(pg_engine, tabela)
    rows = sqlite_sess.execute(text(f"SELECT * FROM {tabela}")).fetchall()
    if not rows:
        logger.info("%s: vazia no SQLite, pulando", tabela)
        return 0

    cols = rows[0]._mapping.keys()
    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    insert = text(f"INSERT INTO {tabela} ({col_list}) VALUES ({placeholders})")

    total = 0
    batch: list[dict] = []
    for row in rows:
        rec = dict(row._mapping)
        for c in bool_cols:
            if c in rec and isinstance(rec[c], (int, float)):
                rec[c] = bool(rec[c])
        batch.append(rec)
        if len(batch) >= LOTE:
            pg_sess.execute(insert, batch)
            pg_sess.commit()
            total += len(batch)
            logger.info("%s: %s / %s", tabela, total, len(rows))
            batch = []

    if batch:
        pg_sess.execute(insert, batch)
        pg_sess.commit()
        total += len(batch)

    logger.info("%s: %s registros importados", tabela, total)
    return total


def _reset_sequences(pg_sess, tabela: str) -> None:
    pg_sess.execute(
        text(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{tabela}', 'id'),
                COALESCE((SELECT MAX(id) FROM {tabela}), 1),
                true
            )
            """
        )
    )
    pg_sess.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa prospecção SQLite -> Postgres")
    parser.add_argument("--sqlite", default="tronik-2gb.db", help="Arquivo SQLite fonte")
    parser.add_argument(
        "--postgres",
        default=os.getenv("RAILWAY_DB") or os.getenv("DATABASE_URL"),
        help="URL Postgres (ou env RAILWAY_DB)",
    )
    parser.add_argument("--force", action="store_true", help="Apaga prospecção existente no destino")
    args = parser.parse_args()

    if not args.postgres:
        logger.error("Defina RAILWAY_DB ou passe --postgres")
        return 1

    sqlite_engine = create_engine(_sqlite_url(args.sqlite), echo=False)
    pg_engine = create_engine(_pg_url(args.postgres), echo=False)

    sqlite_sess = sessionmaker(bind=sqlite_engine)()
    pg_sess = sessionmaker(bind=pg_engine)()

    pg_sess.execute(text("SELECT 1"))
    logger.info("Conexão Postgres OK")

    insp = inspect(pg_engine)
    missing = [t for t in TABELAS if t not in insp.get_table_names()]
    if missing:
        logger.error("Tabelas faltando no Postgres: %s. Rode create_all antes.", missing)
        return 1

    for t in TABELAS:
        _assert_empty(pg_sess, t, args.force)

    # FK order
    totals = {}
    for t in TABELAS:
        logger.info("Importando %s ...", t)
        totals[t] = _import_table(sqlite_sess, pg_sess, pg_engine, t)
        try:
            _reset_sequences(pg_sess, t)
        except Exception:
            logger.debug("sequence reset ignorado para %s", t, exc_info=True)

    logger.info("=== CONCLUÍDO ===")
    for t, n in totals.items():
        logger.info("  %s: %s", t, n)

    logger.info("Verifique no Railway:")
    logger.info(
        "  SELECT COUNT(*) FROM score_prospeccao "
        "WHERE modelo_id=(SELECT id FROM modelo_prospeccao WHERE ativo=true);"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
