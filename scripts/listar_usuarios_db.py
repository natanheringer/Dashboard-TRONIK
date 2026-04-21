"""Lista usuarios do banco (sem senha). Uso: python scripts/listar_usuarios_db.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("SECRET_KEY", "temp-script-key-at-least-32-chars-long!!")

from sqlalchemy import text

import app as A

eng = A.engine
dialect = eng.dialect.name
print("Dialect:", dialect)

with eng.connect() as conn:
    if dialect == "sqlite":
        q = text("SELECT id, username, email, ativo, admin FROM usuarios ORDER BY id")
    else:
        q = text("SELECT id, username, email, ativo, admin FROM usuarios ORDER BY id")
    rows = conn.execute(q).fetchall()
    if not rows:
        print("Nenhum usuario na tabela usuarios.")
        sys.exit(0)
    print("Usuarios (use username ou email no campo de login, campo senha = sua senha):")
    for r in rows:
        print(f"  id={r[0]} username={r[1]!r} email={r[2]!r} ativo={r[3]} admin={r[4]}")
