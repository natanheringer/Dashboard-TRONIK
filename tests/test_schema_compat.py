"""Schema compat migrations on legacy SQLite databases."""

from sqlalchemy import create_engine, inspect, text

from banco_dados.schema_compat import aplicar_compat_schema


def test_aplicar_compat_schema_adds_parceiros_cnpj():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE parceiros (
                    id INTEGER PRIMARY KEY,
                    nome VARCHAR(150) NOT NULL,
                    ativo BOOLEAN,
                    criado_em DATETIME
                )
                """
            )
        )
        conn.execute(text("CREATE TABLE sensores (id INTEGER PRIMARY KEY)"))

    aplicar_compat_schema(engine)

    cols = {c["name"] for c in inspect(engine).get_columns("parceiros")}
    assert "cnpj" in cols
