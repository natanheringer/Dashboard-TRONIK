"""Persist CRM pipeline links on prospection candidates (empresa_candidata).

Matches normalized empresa names (razão social / nome fantasia) to won CRM deals
whose coletor.localizacao normalizes to the same key.

SQLite compatibility
--------------------
- **New databases**: ``Base.metadata.create_all`` (app startup or ``jobs.prospeccao.db``)
  creates ``empresa_candidata.pipeline_id`` from the SQLAlchemy model.
- **Existing SQLite files**: ``banco_dados.schema_compat.aplicar_compat_schema`` runs
  ``ALTER TABLE empresa_candidata ADD COLUMN pipeline_id INTEGER`` when the column is
  missing (SQLite does not enforce FK on ADD COLUMN). This job calls that helper before
  writing links.
- **PostgreSQL**: same helper adds ``INTEGER NULL REFERENCES pipeline(id)`` when needed.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import Coletor, EmpresaCandidata, Pipeline
from banco_dados.schema_compat import aplicar_compat_schema
from jobs.prospeccao.labels_internal import (
    _PIPELINE_WON_STATUSES,
    normalize_org_name,
)

logger = logging.getLogger(__name__)


def _pipeline_is_won(pipe: Pipeline) -> bool:
    return (pipe.status or "").strip().lower() in _PIPELINE_WON_STATUSES


def _build_won_location_index(db: Session) -> dict[str, int]:
    """Map normalized coletor.localizacao -> pipeline.id for won deals."""
    coletor_by_id = {c.id: c for c in db.query(Coletor).all()}
    won_by_loc: dict[str, int] = {}

    for pipe in db.query(Pipeline).all():
        if not _pipeline_is_won(pipe) or not pipe.coletor_id:
            continue
        coletor = coletor_by_id.get(pipe.coletor_id)
        if not coletor or not coletor.localizacao:
            continue
        key = normalize_org_name(coletor.localizacao)
        if not key:
            continue
        prev_id = won_by_loc.get(key)
        if prev_id is None or pipe.id > prev_id:
            won_by_loc[key] = pipe.id

    return won_by_loc


def sync_pipeline_links(db: Session) -> dict[str, Any]:
    """Set ``empresa.pipeline_id`` when name matches a won pipeline coletor.localizacao."""
    engine = db.get_bind()
    aplicar_compat_schema(engine)

    won_by_loc = _build_won_location_index(db)
    empresas = db.query(EmpresaCandidata).order_by(EmpresaCandidata.id.asc()).all()

    linked = 0
    unchanged = 0
    no_match = 0

    for empresa in empresas:
        target_id: int | None = None
        for name in (empresa.razao_social, empresa.nome_fantasia):
            key = normalize_org_name(name)
            if key and key in won_by_loc:
                target_id = won_by_loc[key]
                break

        if target_id is None:
            no_match += 1
            continue

        if empresa.pipeline_id == target_id:
            unchanged += 1
            continue

        empresa.pipeline_id = target_id
        linked += 1

    stats = {
        "won_location_keys": len(won_by_loc),
        "empresas": len(empresas),
        "linked": linked,
        "unchanged": unchanged,
        "no_match": no_match,
    }
    logger.info("link_crm_pipeline: %s", stats)
    return stats
