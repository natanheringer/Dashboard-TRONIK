"""Loló Account: resolve or create ContaComercial from CRM / prospection data."""

from __future__ import annotations

from sqlalchemy.orm import Session

from banco_dados.modelos import ContaComercial
from banco_dados.utils import utc_now_naive
from jobs.prospeccao.labels_internal import normalize_cnpj


def _find_by_cnpj_digits(db: Session, cnpj_digits: str) -> ContaComercial | None:
    for row in db.query(ContaComercial).filter(ContaComercial.cnpj.isnot(None)).all():
        if normalize_cnpj(row.cnpj) == cnpj_digits:
            return row
    return None


def _apply_optional_fields(
    conta: ContaComercial,
    *,
    cnpj_store: str | None,
    razao_social: str | None,
    nome_fantasia: str | None,
    empresa_candidata_id: int | None,
    parceiro_id: int | None,
) -> None:
    if cnpj_store and not conta.cnpj:
        conta.cnpj = cnpj_store
    if razao_social and not conta.razao_social:
        conta.razao_social = razao_social.strip()[:255]
    if nome_fantasia and not conta.nome_fantasia:
        conta.nome_fantasia = nome_fantasia.strip()[:255]
    if empresa_candidata_id and not conta.empresa_candidata_id:
        conta.empresa_candidata_id = empresa_candidata_id
    if parceiro_id and not conta.parceiro_id:
        conta.parceiro_id = parceiro_id
    conta.atualizado_em = utc_now_naive()


def resolver_ou_criar_conta(
    db: Session,
    *,
    cnpj: str | None = None,
    razao_social: str | None = None,
    nome_fantasia: str | None = None,
    empresa_candidata_id: int | None = None,
    parceiro_id: int | None = None,
) -> ContaComercial:
    """Find or create ContaComercial; CNPJ is stored normalized to digits when valid."""
    cnpj_digits = normalize_cnpj(cnpj)
    cnpj_store = cnpj_digits or (cnpj.strip()[:18] if cnpj else None)
    razao = (razao_social or "").strip()[:255] or None
    fantasia = (nome_fantasia or "").strip()[:255] or None

    conta: ContaComercial | None = None
    if cnpj_digits:
        conta = _find_by_cnpj_digits(db, cnpj_digits)

    if conta is None and empresa_candidata_id is not None:
        conta = (
            db.query(ContaComercial)
            .filter_by(empresa_candidata_id=empresa_candidata_id)
            .first()
        )

    if conta is None and parceiro_id is not None:
        conta = db.query(ContaComercial).filter_by(parceiro_id=parceiro_id).first()

    if conta:
        _apply_optional_fields(
            conta,
            cnpj_store=cnpj_store,
            razao_social=razao,
            nome_fantasia=fantasia,
            empresa_candidata_id=empresa_candidata_id,
            parceiro_id=parceiro_id,
        )
        return conta

    conta = ContaComercial(
        cnpj=cnpj_store,
        razao_social=razao,
        nome_fantasia=fantasia,
        empresa_candidata_id=empresa_candidata_id,
        parceiro_id=parceiro_id,
    )
    db.add(conta)
    db.flush()
    return conta
