"""Tests for Loló Account (ContaComercial) service."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Base, ContaComercial, EmpresaCandidata, Parceiro
from banco_dados.services.account_service import resolver_ou_criar_conta


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_resolver_cria_conta_com_cnpj_normalizado():
    db = _session()
    conta = resolver_ou_criar_conta(
        db,
        cnpj="12.345.678/0001-95",
        razao_social="Eco Recicla Centro Ltda",
        nome_fantasia="Eco Recicla",
    )
    db.commit()

    assert conta.id is not None
    assert conta.cnpj == "12345678000195"
    assert conta.razao_social == "Eco Recicla Centro Ltda"
    assert conta.nome_fantasia == "Eco Recicla"
    assert db.query(ContaComercial).count() == 1

    db.close()


def test_resolver_reutiliza_conta_por_cnpj():
    db = _session()
    db.add(ContaComercial(cnpj="12345678000195", razao_social="Existente SA"))
    db.commit()

    conta = resolver_ou_criar_conta(db, cnpj="123.456.780/001-95", razao_social="Outro Nome")
    db.commit()

    assert db.query(ContaComercial).count() == 1
    assert conta.razao_social == "Existente SA"

    db.close()


def test_resolver_vincula_parceiro_e_empresa_em_conta_existente():
    db = _session()
    parceiro = Parceiro(nome="Parceiro Win", cnpj=None)
    empresa = EmpresaCandidata(cnpj="98765432000100", razao_social="Empresa Win SA")
    db.add_all([parceiro, empresa])
    db.flush()
    db.add(ContaComercial(cnpj="98765432000100", razao_social="Empresa Win SA"))
    db.commit()

    conta = resolver_ou_criar_conta(
        db,
        cnpj="98765432000100",
        empresa_candidata_id=empresa.id,
        parceiro_id=parceiro.id,
    )
    db.commit()

    assert conta.parceiro_id == parceiro.id
    assert conta.empresa_candidata_id == empresa.id

    db.close()


def test_resolver_cria_sem_cnpj_por_empresa_candidata():
    db = _session()
    empresa = EmpresaCandidata(cnpj="00000000000000", razao_social="Sem CNPJ Conta SA")
    db.add(empresa)
    db.commit()

    conta = resolver_ou_criar_conta(
        db,
        razao_social="Sem CNPJ Conta SA",
        empresa_candidata_id=empresa.id,
    )
    db.commit()

    assert conta.cnpj is None
    assert conta.empresa_candidata_id == empresa.id
    assert conta.razao_social == "Sem CNPJ Conta SA"

    db.close()
