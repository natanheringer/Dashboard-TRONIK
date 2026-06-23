"""Testes das ferramentas de relatório e listagem de parceiros/empresas da Nik."""

import re
from datetime import datetime

from banco_dados.modelos import Coleta, EmpresaCandidata, Parceiro
from banco_dados.services import nik_service, nik_tools
from banco_dados.utils.cache import obter_cache


def _seed_parceiros(db_session, create_lixeira):
    p1 = Parceiro(nome="Alpha Recicla", cnpj="11.111.111/0001-11", ativo=True)
    p2 = Parceiro(nome="Beta Sustentável", cnpj="22.222.222/0001-22", ativo=True)
    p3 = Parceiro(nome="Gamma Inativa", cnpj="33.333.333/0001-33", ativo=False)
    db_session.add_all([p1, p2, p3])
    db_session.flush()

    coletor = create_lixeira(localizacao="Coletor Alpha", parceiro_id=p1.id)
    coleta = Coleta(
        coletor_id=coletor.id,
        parceiro_id=p1.id,
        data_hora=datetime(2026, 3, 15, 10, 0, 0),
        volume_estimado=200.0,
        km_percorrido=12.0,
        preco_combustivel=5.5,
        tipo_operacao="Avulsa",
    )
    db_session.add(coleta)
    db_session.commit()
    db_session.refresh(p1)
    db_session.refresh(p2)
    db_session.refresh(p3)
    return {"p1": p1, "p2": p2, "p3": p3, "coleta": coleta}


def test_listar_parceiros_retorna_contagens(db_session, create_lixeira):
    seed = _seed_parceiros(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_parceiros(db_session, limite=50)
    nomes = {p["nome"] for p in out["parceiros"]}
    assert seed["p1"].nome in nomes
    assert seed["p2"].nome in nomes
    assert seed["p3"].nome in nomes
    alpha = next(p for p in out["parceiros"] if p["nome"] == seed["p1"].nome)
    assert alpha["n_coletores"] >= 1
    assert alpha["n_coletas"] >= 1
    assert "resumo" in out
    dumped = str(out)
    assert "secret" not in dumped.lower()


def test_listar_parceiros_filtro_ativo(db_session, create_lixeira):
    _seed_parceiros(db_session, create_lixeira)
    out = nik_tools.ferramenta_listar_parceiros(db_session, ativo=True, limite=50)
    assert all(p["ativo"] for p in out["parceiros"])
    assert "Gamma Inativa" not in {p["nome"] for p in out["parceiros"]}


def test_listar_empresas_prospeccao_vazio(db_session):
    out = nik_tools.ferramenta_listar_empresas_prospeccao(db_session)
    assert out["total"] == 0
    assert "nenhuma" in out["resumo"].lower() or "0" in out["resumo"]


def test_listar_empresas_prospeccao_com_seed(db_session):
    emp = EmpresaCandidata(
        cnpj="44.444.444/0001-44",
        razao_social="Empresa Teste Prospecção Ltda",
        nome_fantasia="Teste REE",
        cnae_principal="4751-2/01",
        bairro="Asa Norte",
        situacao_cadastral="ATIVA",
        telefone="61999999999",
        email="contato@secreto.local",
    )
    db_session.add(emp)
    db_session.commit()
    out = nik_tools.ferramenta_listar_empresas_prospeccao(db_session, limite=20)
    assert out["total"] >= 1
    item = out["empresas"][0]
    assert item["razao_social"] == "Empresa Teste Prospecção Ltda"
    assert item["cnae_principal"] == "4751-2/01"
    assert "telefone" not in item
    assert "email" not in item


def test_planejador_relatorio_empresas_cadastradas():
    plano = nik_service._planejar_ferramentas("relatório de todas as empresas cadastradas no sistema")
    nomes = [p["nome"] for p in plano]
    assert "listar_parceiros" in nomes


def test_planejador_gerar_relatorio_coletas():
    for msg in ("gera um relatório de coletas", "exportar relatório pdf"):
        plano = nik_service._planejar_ferramentas(msg)
        nomes = [p["nome"] for p in plano]
        assert "gerar_relatorio_coletas" in nomes


def test_gerar_relatorio_coletas_com_coletas(db_session, create_lixeira):
    _seed_parceiros(db_session, create_lixeira)
    out = nik_tools.ferramenta_gerar_relatorio_coletas(
        db_session,
        inicio="2026-01-01",
        fim="2026-12-31",
        usuario_id=1,
    )
    assert out["status"] == "ok"
    assert out["total_linhas"] > 0
    assert out["csv"]["download_url"].startswith("/api/nik/ops/export/")
    assert out["pdf"] is not None
    assert out["pdf"]["download_url"].startswith("/api/nik/ops/export/")
    assert not out.get("pdf_indisponivel")
    assert "coleta" in out["resumo"].lower()

    token_pdf = out["pdf"]["download_url"].rsplit("/", 1)[-1]
    cached = obter_cache().obter(f"nik:export:{token_pdf}", ttl_segundos=3600)
    assert cached is not None
    assert cached.get("mime") == "application/pdf"
    assert cached.get("conteudo_bytes")


def test_anexos_resposta_gerar_relatorio_coletas():
    contexto = {
        "gerar_relatorio_coletas": {
            "status": "ok",
            "total_linhas": 5,
            "periodo": {"inicio": "2026-01-01", "fim": "2026-03-31"},
            "csv": {
                "download_url": "/api/nik/ops/export/tok_csv",
                "filename": "coletas.csv",
            },
            "pdf": {
                "download_url": "/api/nik/ops/export/tok_pdf",
                "filename": "relatorio.pdf",
            },
        }
    }
    anexos = nik_service._anexos_resposta_from_contexto(contexto)
    assert anexos["arquivo_export"]["url"] == "/api/nik/ops/export/tok_csv"
    assert anexos["documento"]["url"] == "/api/nik/ops/export/tok_pdf"
    assert anexos["documento"]["tipo"] == "pdf"


def test_rota_download_pdf(admin_client, db_session, create_lixeira):
    _seed_parceiros(db_session, create_lixeira)
    out = nik_tools.ferramenta_gerar_relatorio_coletas(
        db_session,
        inicio="2026-01-01",
        fim="2026-12-31",
        usuario_id=1,
    )
    url = out["pdf"]["download_url"]
    m = re.search(r"/ops/export/([^/]+)$", url)
    assert m
    token = m.group(1)
    resp = admin_client.get(f"/api/nik/ops/export/{token}")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/pdf")
    assert resp.data[:4] == b"%PDF"
