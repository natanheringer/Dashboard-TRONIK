"""Tests for CRM pipeline link sync on empresa_candidata."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Base, Coletor, EmpresaCandidata, Pipeline
from jobs.prospeccao.link_crm_pipeline import sync_pipeline_links


def test_sync_pipeline_links_matches_won_deal_by_name():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    coletor = Coletor(localizacao="Eco Recicla Centro")
    db.add(coletor)
    db.flush()
    db.add(Pipeline(coletor_id=coletor.id, status="fechado", valor_estimado=1000.0))
    db.add(
        EmpresaCandidata(
            cnpj="12345678000195",
            razao_social="Eco Recicla Centro Ltda",
        )
    )
    db.commit()

    stats = sync_pipeline_links(db)
    db.commit()

    empresa = db.query(EmpresaCandidata).first()
    assert stats["linked"] == 1
    assert empresa.pipeline_id == 1

    db.close()
