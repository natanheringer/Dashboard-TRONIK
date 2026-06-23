"""Testes do mapeamento/correção de colunas CSV na importação de coletas (Wave 4)."""

from dataclasses import dataclass

from banco_dados.modelos import Coletor, Parceiro
from banco_dados.services import (
    nik_coleta_import as imp,
    nik_csv_mapping as csv_map,
    nik_provider as provider,
)


def _seed_coletor(db_session, *, parceiro_id=None):
    if parceiro_id is None:
        p = Parceiro(nome="Parceiro CSV Map")
        db_session.add(p)
        db_session.flush()
        parceiro_id = p.id
    c = Coletor(localizacao="L-CSV", parceiro_id=parceiro_id)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def test_mapear_colunas_deterministico_aliases_pt():
    headers = ["Coletor", "Data da coleta", "Peso (kg)", "Quilometragem", "Tipo"]
    mapa = csv_map.mapear_colunas_deterministico(headers)
    assert mapa["Coletor"] == "coletor_id"
    assert mapa["Data da coleta"] == "data_hora"
    assert mapa["Peso (kg)"] == "volume_kg"
    assert mapa["Quilometragem"] == "km_percorrido_km"
    assert mapa["Tipo"] == "tipo_operacao"


def test_ja_canonico_pula_mapeamento():
    headers = ["data_hora", "coletor_id", "volume_kg"]
    assert csv_map.ja_canonico(headers) is True
    assert csv_map.ja_canonico(["Coletor", "Data"]) is False


def test_mapear_colunas_ia_aplica_json(monkeypatch):
    headers = ["ID máquina", "Data da coleta", "Coletor"]

    @dataclass
    class FakeResp:
        sucesso: bool = True
        texto: str = '{"ID máquina": "parceiro_id"}'
        modelo_usado: str = "fake"
        erro: str | None = None

    monkeypatch.setattr(provider, "chamar_modelo", lambda *a, **k: FakeResp())
    mapa_det = csv_map.mapear_colunas_deterministico(headers)
    mapa_ia = csv_map.mapear_colunas_ia(headers, mapa_det, [{"ID máquina": "3"}])
    assert mapa_ia == {"ID máquina": "parceiro_id"}


def test_mapear_colunas_ia_falha_degrada(monkeypatch):
    headers = ["ColunaX", "Coletor"]

    @dataclass
    class FakeResp:
        sucesso: bool = False
        texto: str = "erro"
        modelo_usado: str = "fake"
        erro: str | None = "timeout"

    monkeypatch.setattr(provider, "chamar_modelo", lambda *a, **k: FakeResp())
    mapa_det = csv_map.mapear_colunas_deterministico(headers)
    assert csv_map.mapear_colunas_ia(headers, mapa_det, []) == {}


def test_mapear_colunas_ia_garbage_json_degrada(monkeypatch):
    headers = ["ColunaX", "Coletor"]

    @dataclass
    class FakeResp:
        sucesso: bool = True
        texto: str = "não é json"
        modelo_usado: str = "fake"
        erro: str | None = None

    monkeypatch.setattr(provider, "chamar_modelo", lambda *a, **k: FakeResp())
    mapa_det = csv_map.mapear_colunas_deterministico(headers)
    assert csv_map.mapear_colunas_ia(headers, mapa_det, []) == {}


def test_nik_csv_ia_mapping_desabilitado(monkeypatch):
    headers = ["ColunaObscura", "Coletor", "Data da coleta"]
    chamado = {"n": 0}

    def _fake(*a, **k):
        chamado["n"] += 1
        return None

    monkeypatch.setenv("NIK_CSV_IA_MAPPING", "false")
    monkeypatch.setattr(provider, "chamar_modelo", _fake)
    mapa_det = csv_map.mapear_colunas_deterministico(headers)
    assert csv_map.mapear_colunas_ia(headers, mapa_det, []) == {}
    assert chamado["n"] == 0


def test_preparar_import_headers_nao_canonicos(db_session, monkeypatch):
    monkeypatch.setenv("NIK_CSV_IA_MAPPING", "false")
    c = _seed_coletor(db_session)
    linhas = [
        {
            "Coletor": str(c.id),
            "Data da coleta": "2026-08-01T12:00:00",
            "Peso (kg)": "100",
            "Quilometragem": "10",
        }
    ]
    prep = imp.preparar_import_coletas(
        db_session, linhas, usuario_id=None, thread_id="t-map", filename="coletas.csv"
    )
    assert prep["pendente"] is True
    assert prep["stats"]["validas"] == 1
    assert "Mapeamento de colunas" in prep["texto"]
    assert "Coletor → coletor_id" in prep["texto"]
    pending = imp.obter_pending_import(None, "t-map")
    assert pending is not None
    assert pending["mapeamento"]["mapa"]["Coletor"] == "coletor_id"


def test_preparar_import_correcoes_visiveis(db_session, monkeypatch):
    monkeypatch.setenv("NIK_CSV_IA_MAPPING", "false")
    c = _seed_coletor(db_session)
    linhas = [
        {
            "Coletor": str(c.id),
            "Data da coleta": "22/06/2026",
            "Peso (kg)": "1,5",
            "Quilometragem": "5",
        }
    ]
    prep = imp.preparar_import_coletas(
        db_session, linhas, usuario_id=None, thread_id="t-corr", filename="c.csv"
    )
    assert prep["pendente"] is True
    assert "Correções aplicadas" in prep["texto"]
    assert "1,5" in prep["texto"] or "22/06/2026" in prep["texto"]
    pending = imp.obter_pending_import(None, "t-corr")
    assert pending.get("correcoes")


def test_mapeamento_incompleto_sem_pending(db_session, monkeypatch):
    monkeypatch.setenv("NIK_CSV_IA_MAPPING", "false")
    linhas = [{"Peso (kg)": "100", "Quilometragem": "10"}]
    prep = imp.preparar_import_coletas(
        db_session, linhas, usuario_id=None, thread_id="t-inc", filename="c.csv"
    )
    assert prep["status"] == "mapeamento_incompleto"
    assert prep["pendente"] is False
    assert "coletor_id" in prep["texto"] or "data_hora" in prep["texto"]
    assert imp.obter_pending_import(None, "t-inc") is None


def test_aplicar_mapeamento_rechaveia_linhas():
    linhas = [{"Coletor": "1", "Peso (kg)": "50"}]
    mapa = {"Coletor": "coletor_id", "Peso (kg)": "volume_kg"}
    out = csv_map.aplicar_mapeamento(linhas, mapa)
    assert out[0] == {"coletor_id": "1", "volume_kg": "50"}


def test_resumo_mapeamento_pt():
    resultado = {
        "mapa": {"Coletor": "coletor_id", "Peso (kg)": "volume_kg"},
        "ia_usada": True,
        "nao_mapeados": ["Obs"],
        "faltando_obrigatorios": [],
    }
    linhas = csv_map.resumo_mapeamento(resultado)
    assert any("Coletor → coletor_id" in linha for linha in linhas)
    assert any("IA" in linha for linha in linhas)
