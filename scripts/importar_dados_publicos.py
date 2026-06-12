"""Importador legado — descontinuado.

A antiga rotina gravava candidatos na tabela ``locais_prospeccao`` com heurística/MLP.
Essa camada foi removida do produto para evitar conflito com o pipeline futuro
(XGBRanker, novas tabelas; ver ``docs/PLANO_ML_TRONIK.md``).

Implementação anterior permanece no histórico do Git se precisar consultar.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "Este script foi descontinuado.\n"
        "Prospecção será refeita conforme docs/PLANO_ML_TRONIK.md (ingestão batch + XGBRanker).\n"
        "Consulte o histórico Git se precisar do código antigo.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
