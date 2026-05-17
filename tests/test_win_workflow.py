"""Tests for CRM win workflow (ganho/fechado)."""

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Base, Coletor, ContaComercial, EmpresaCandidata, Parceiro, Pipeline
from banco_dados.services.crm_service import CRMService
from banco_dados.services.win_workflow import (
    find_empresa_candidata_for_pipeline,
    is_pipeline_won,
    process_pipeline_win,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_is_pipeline_won_accepts_ganho_and_fechado():
    assert is_pipeline_won("fechado")
    assert is_pipeline_won("ganho")
    assert is_pipeline_won("GANHO")
    assert not is_pipeline_won("negociacao")


def test_process_pipeline_win_links_empresa_and_creates_parceiro():
    db = _session()
    coletor = Coletor(localizacao="Eco Recicla Centro")
    db.add(coletor)
    db.flush()
    pipeline = Pipeline(coletor_id=coletor.id, status="fechado", valor_estimado=1000.0)
    db.add(pipeline)
    db.add(
        EmpresaCandidata(
            cnpj="12.345.678/0001-95",
            razao_social="Eco Recicla Centro Ltda",
        )
    )
    db.commit()

    result = process_pipeline_win(db, pipeline)
    db.commit()

    empresa = db.query(EmpresaCandidata).first()
    parceiro = db.query(Parceiro).first()
    assert result["empresa_linked"] is True
    assert result["empresa_id"] == empresa.id
    assert empresa.pipeline_id == pipeline.id
    assert parceiro is not None
    assert parceiro.nome == "Eco Recicla Centro Ltda"
    assert parceiro.cnpj == "12345678000195"
    assert result["parceiro"]["action"] == "created"
    assert result["conta_comercial_id"] is not None
    db.refresh(pipeline)
    assert pipeline.conta_comercial_id == result["conta_comercial_id"]
    conta = db.query(ContaComercial).first()
    assert conta.cnpj == "12345678000195"
    assert conta.empresa_candidata_id == empresa.id

    db.close()


def test_process_pipeline_win_updates_existing_parceiro_cnpj():
    db = _session()
    parceiro = Parceiro(nome="Eco Recicla Centro Ltda", cnpj=None)
    db.add(parceiro)
    db.flush()
    coletor = Coletor(localizacao="Eco Recicla Centro", parceiro_id=parceiro.id)
    db.add(coletor)
    db.flush()
    pipeline = Pipeline(coletor_id=coletor.id, status="ganho")
    db.add(pipeline)
    db.add(
        EmpresaCandidata(
            cnpj="12345678000195",
            razao_social="Eco Recicla Centro Ltda",
        )
    )
    db.commit()

    result = process_pipeline_win(db, pipeline)
    db.commit()

    db.refresh(parceiro)
    assert result["parceiro"]["action"] == "updated"
    assert parceiro.cnpj == "12345678000195"
    assert db.query(EmpresaCandidata).first().pipeline_id == pipeline.id

    db.close()


def test_find_empresa_by_cnpj_in_observacoes():
    db = _session()
    pipeline = Pipeline(
        status="fechado",
        observacoes="Cliente CNPJ 12.345.678/0001-95 fechou contrato",
    )
    db.add(pipeline)
    db.add(
        EmpresaCandidata(
            cnpj="12345678000195",
            razao_social="Empresa Observacoes Ltda",
        )
    )
    db.commit()

    empresa = find_empresa_candidata_for_pipeline(db, pipeline)
    assert empresa is not None
    assert empresa.razao_social == "Empresa Observacoes Ltda"

    db.close()


@patch("banco_dados.services.crm_service.get_db_session")
def test_atualizar_status_triggers_win_workflow(mock_get_db):
    db = _session()
    mock_get_db.return_value = db

    coletor = Coletor(localizacao="Cliente Win Flow")
    db.add(coletor)
    db.flush()
    pipeline = Pipeline(coletor_id=coletor.id, status="negociacao")
    db.add(pipeline)
    db.add(
        EmpresaCandidata(
            cnpj="98765432000100",
            razao_social="Cliente Win Flow SA",
        )
    )
    db.commit()

    CRMService.atualizar_status(pipeline.id, "fechado")

    empresa = db.query(EmpresaCandidata).first()
    assert empresa.pipeline_id == pipeline.id
    assert db.query(Parceiro).count() == 1

    db.close()
