"""Idempotency and FK hygiene for prospeccao → CRM pipeline creation."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Base, EmpresaCandidata, Pipeline
from banco_dados.services.prospeccao_crm_bridge import criar_pipeline_de_candidato


def test_criar_pipeline_clears_stale_empresa_pipeline_fk():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add(
        EmpresaCandidata(
            cnpj="12345678000195",
            razao_social="Stale FK Ltda",
            pipeline_id=9999,
        ),
    )
    db.commit()

    empresa = db.query(EmpresaCandidata).first()
    out = criar_pipeline_de_candidato(db, empresa.id, usuario_id=None)
    assert out is not None
    assert out.get("ja_vinculado") is False

    db.refresh(empresa)
    pipe = db.query(Pipeline).filter_by(id=empresa.pipeline_id).first()
    assert pipe is not None
    assert pipe.origem == "prospeccao_ree"
    db.close()


def test_criar_pipeline_segunda_chamada_retorna_vinculado():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add(
        EmpresaCandidata(
            cnpj="12345678000196",
            razao_social="Idempotente Ltda",
        ),
    )
    db.commit()

    empresa = db.query(EmpresaCandidata).first()
    first = criar_pipeline_de_candidato(db, empresa.id, usuario_id=1)
    second = criar_pipeline_de_candidato(db, empresa.id, usuario_id=1)

    assert first is not None
    assert second is not None
    assert first["pipeline_id"] == second["pipeline_id"]
    assert second.get("ja_vinculado") is True
    assert db.query(Pipeline).count() == 1
    db.close()
