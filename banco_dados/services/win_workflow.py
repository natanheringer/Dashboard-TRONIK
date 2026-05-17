"""CRM win workflow: link prospection candidates and upsert parceiro on deal won."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session, joinedload

from banco_dados.modelos import EmpresaCandidata, Parceiro, Pipeline
from banco_dados.schema_compat import aplicar_compat_schema
from banco_dados.services import prospeccao_crm_bridge
from jobs.prospeccao.labels_internal import (
    _PIPELINE_WON_STATUSES,
    extract_cnpjs_from_text,
    normalize_cnpj,
    normalize_org_name,
)

logger = logging.getLogger(__name__)


def is_pipeline_won(status: str | None) -> bool:
    return (status or "").strip().lower() in _PIPELINE_WON_STATUSES


def _empresa_por_cnpj(db: Session, cnpj_digits: str) -> EmpresaCandidata | None:
    if not cnpj_digits:
        return None
    for empresa in db.query(EmpresaCandidata).all():
        if normalize_cnpj(empresa.cnpj) == cnpj_digits:
            return empresa
    return None


def _empresa_por_nome_normalizado(db: Session, termo: str) -> EmpresaCandidata | None:
    key = normalize_org_name(termo)
    if len(key) < 3:
        return None
    for empresa in db.query(EmpresaCandidata).order_by(EmpresaCandidata.id.asc()):
        for name in (empresa.razao_social, empresa.nome_fantasia):
            if normalize_org_name(name) == key:
                return empresa
    return None


def _termos_busca_pipeline(pipeline: Pipeline) -> list[str]:
    termos: list[str] = []
    coletor = pipeline.coletor
    if coletor and coletor.localizacao:
        termos.append(coletor.localizacao.strip())
    if pipeline.observacoes:
        termos.append(str(pipeline.observacoes).strip())
    if pipeline.origem:
        termos.append(str(pipeline.origem).strip())
    return [t for t in termos if t]


def find_empresa_candidata_for_pipeline(db: Session, pipeline: Pipeline) -> EmpresaCandidata | None:
    """Resolve empresa_candidata for a won pipeline (persisted link, name, CNPJ, scores)."""
    linked = (
        db.query(EmpresaCandidata)
        .filter(EmpresaCandidata.pipeline_id == pipeline.id)
        .order_by(EmpresaCandidata.id.asc())
        .first()
    )
    if linked:
        return linked

    for cnpj in extract_cnpjs_from_text(pipeline.observacoes):
        empresa = _empresa_por_cnpj(db, cnpj)
        if empresa:
            return empresa

    for termo in _termos_busca_pipeline(pipeline):
        empresa = _empresa_por_nome_normalizado(db, termo)
        if empresa:
            return empresa

    for termo in _termos_busca_pipeline(pipeline):
        candidatos = prospeccao_crm_bridge.buscar_candidatos_por_nome_empresa(db, termo, limite=1)
        if not candidatos:
            continue
        emp_payload = candidatos[0].get("empresa") or {}
        emp_id = emp_payload.get("id")
        if emp_id is None:
            continue
        empresa = db.query(EmpresaCandidata).filter_by(id=int(emp_id)).first()
        if empresa:
            return empresa

    return None


def _upsert_parceiro_from_empresa(db: Session, empresa: EmpresaCandidata) -> dict[str, Any]:
    nome = (empresa.razao_social or empresa.nome_fantasia or "").strip()[:150]
    if not nome:
        return {"action": "skipped", "reason": "sem_nome"}

    cnpj_digits = normalize_cnpj(empresa.cnpj)
    cnpj_store = cnpj_digits or (empresa.cnpj.strip()[:18] if empresa.cnpj else None)

    parceiro: Parceiro | None = None
    if cnpj_digits:
        for row in db.query(Parceiro).filter(Parceiro.cnpj.isnot(None)).all():
            if normalize_cnpj(row.cnpj) == cnpj_digits:
                parceiro = row
                break

    if parceiro is None:
        parceiro = db.query(Parceiro).filter(Parceiro.nome == nome).first()

    if parceiro:
        updated = False
        if cnpj_store and not parceiro.cnpj:
            parceiro.cnpj = cnpj_store
            updated = True
        if not parceiro.ativo:
            parceiro.ativo = True
            updated = True
        return {
            "action": "updated" if updated else "unchanged",
            "parceiro_id": parceiro.id,
        }

    parceiro = Parceiro(nome=nome, cnpj=cnpj_store, ativo=True)
    db.add(parceiro)
    db.flush()
    return {"action": "created", "parceiro_id": parceiro.id}


def process_pipeline_win(db: Session, pipeline: Pipeline) -> dict[str, Any]:
    """On ganho/fechado: link empresa_candidata.pipeline_id and upsert parceiro (no coletor)."""
    if not is_pipeline_won(pipeline.status):
        return {"skipped": True, "reason": "status_not_won"}

    aplicar_compat_schema(db.get_bind())

    pipeline = (
        db.query(Pipeline)
        .options(joinedload(Pipeline.coletor))
        .filter_by(id=pipeline.id)
        .first()
    )
    if not pipeline:
        return {"skipped": True, "reason": "pipeline_not_found"}

    result: dict[str, Any] = {
        "pipeline_id": pipeline.id,
        "status": pipeline.status,
        "empresa_linked": False,
        "empresa_id": None,
        "parceiro": None,
    }

    empresa = find_empresa_candidata_for_pipeline(db, pipeline)
    if empresa:
        if empresa.pipeline_id != pipeline.id:
            empresa.pipeline_id = pipeline.id
            result["empresa_linked"] = True
        result["empresa_id"] = empresa.id
        result["parceiro"] = _upsert_parceiro_from_empresa(db, empresa)
    else:
        result["parceiro"] = {"action": "skipped", "reason": "empresa_nao_encontrada"}

    logger.info("win_workflow pipeline=%s: %s", pipeline.id, result)
    return result
