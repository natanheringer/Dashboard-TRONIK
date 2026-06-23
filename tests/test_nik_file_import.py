"""Testes do upload/ingestão de arquivos no chat Nik (Wave 1)."""

from banco_dados.modelos import Coleta, Coletor, Parceiro
from banco_dados.services import nik_coleta_import as imp, nik_file_service as fsvc


def _seed_coletor(db_session, *, parceiro_id=None):
    if parceiro_id is None:
        p = Parceiro(nome="Parceiro Import")
        db_session.add(p)
        db_session.flush()
        parceiro_id = p.id
    c = Coletor(localizacao="L-Import", parceiro_id=parceiro_id)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def test_detectar_tipo_pdf_e_csv():
    assert fsvc.detectar_tipo("x.pdf", b"%PDF-1.7 conteudo") == "pdf"
    assert fsvc.detectar_tipo("x.pdf", b"nao eh pdf") is None
    assert fsvc.detectar_tipo("x.csv", b"a,b,c\n1,2,3\n") == "csv"


def test_sanitizar_celula_csv_injecao():
    assert fsvc.sanitizar_celula_csv("=SOMA(A1:A2)").startswith("'")
    assert fsvc.sanitizar_celula_csv("texto normal") == "texto normal"


def test_ler_linhas_csv_delimitador():
    data = b"data_hora;coletor_id;volume_kg\n2026-01-10T12:00:00;5;120\n"
    linhas = fsvc.ler_linhas_csv(data)
    assert linhas[0]["coletor_id"] == "5"
    assert linhas[0]["volume_kg"] == "120"


def test_import_preview_confirma_cria_coletas(db_session):
    c = _seed_coletor(db_session)
    linhas = [
        {"data_hora": "2026-02-01T12:00:00", "coletor_id": str(c.id), "volume_kg": "100", "km_percorrido_km": "10"},
        {"data_hora": "2026-02-02T12:00:00", "coletor_id": str(c.id), "volume_kg": "200", "km_percorrido_km": "20"},
    ]
    prep = imp.preparar_import_coletas(
        db_session, linhas, usuario_id=None, thread_id="t-imp", filename="coletas.csv"
    )
    assert prep["pendente"] is True
    assert prep["stats"]["validas"] == 2

    res = imp.executar_import_coletas(db_session, None, "t-imp")
    assert res["status"] == "ok"
    assert res["criadas"] == 2
    assert db_session.query(Coleta).filter(Coleta.coletor_id == c.id).count() == 2
    # pending limpo
    assert imp.obter_pending_import(None, "t-imp") is None


def test_import_detecta_duplicata(db_session):
    c = _seed_coletor(db_session)
    linha = {"data_hora": "2026-03-01T12:00:00", "coletor_id": str(c.id), "volume_kg": "50", "km_percorrido_km": "5"}
    imp.preparar_import_coletas(db_session, [linha], usuario_id=None, thread_id="t-dup", filename="c.csv")
    imp.executar_import_coletas(db_session, None, "t-dup")

    prep2 = imp.preparar_import_coletas(
        db_session, [linha], usuario_id=None, thread_id="t-dup2", filename="c.csv"
    )
    assert prep2["stats"]["duplicadas"] == 1
    assert prep2["stats"]["validas"] == 0
    assert prep2["pendente"] is False


def test_import_linha_invalida_sem_coletor(db_session):
    linhas = [{"data_hora": "2026-04-01T12:00:00", "coletor_id": "999999", "volume_kg": "10"}]
    prep = imp.preparar_import_coletas(
        db_session, linhas, usuario_id=None, thread_id="t-inv", filename="c.csv"
    )
    assert prep["stats"]["invalidas"] == 1
    assert prep["pendente"] is False


def test_processar_mensagem_import_confirma(db_session):
    c = _seed_coletor(db_session)
    linhas = [{"data_hora": "2026-05-01T12:00:00", "coletor_id": str(c.id), "volume_kg": "80", "km_percorrido_km": "8"}]
    imp.preparar_import_coletas(db_session, linhas, usuario_id=None, thread_id="t-msg", filename="c.csv")
    res = imp.processar_mensagem_import(db_session, "CONFIRMAR", None, "t-msg")
    assert res["status"] == "ok"
    assert res["criadas"] == 1

    # sem pendência → None (segue chat normal)
    assert imp.processar_mensagem_import(db_session, "qualquer coisa", None, "t-msg") is None


def test_processar_mensagem_import_cancela(db_session):
    c = _seed_coletor(db_session)
    linhas = [{"data_hora": "2026-06-01T12:00:00", "coletor_id": str(c.id), "volume_kg": "30", "km_percorrido_km": "3"}]
    imp.preparar_import_coletas(db_session, linhas, usuario_id=None, thread_id="t-cancel", filename="c.csv")
    res = imp.processar_mensagem_import(db_session, "CANCELAR", None, "t-cancel")
    assert res["status"] == "cancelado"
    assert imp.obter_pending_import(None, "t-cancel") is None


def test_upload_rejeita_tipo_invalido(admin_client):
    import io

    data = {
        "file": (io.BytesIO(b"\x00\x01\x02binario"), "x.bin"),
        "mode": "analyze",
    }
    resp = admin_client.post("/api/nik/ops/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_import_coletas_endpoint(admin_client, db_session):
    import io

    c = _seed_coletor(db_session)
    csv_bytes = (
        "data_hora,coletor_id,volume_kg,km_percorrido_km\n"
        f"2026-07-01T12:00:00,{c.id},90,9\n"
    ).encode()
    data = {
        "file": (io.BytesIO(csv_bytes), "coletas.csv"),
        "mode": "import_coletas",
        "thread_id": "api-imp",
    }
    resp = admin_client.post("/api/nik/ops/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["mode"] == "import_coletas"
    assert body["pendente"] is True

    confirm = admin_client.post("/api/nik/ops/upload/confirm", json={"thread_id": "api-imp"})
    assert confirm.status_code == 200
    assert confirm.get_json()["criadas"] == 1


def test_upload_analyze_csv_endpoint(admin_client, monkeypatch):
    import io

    from banco_dados.services import nik_file_service as fsvc

    monkeypatch.setattr(
        fsvc,
        "analisar_arquivo_conversa",
        lambda **kw: {"texto": "Análise pronta.", "fonte": "modelo", "modelo": "fake", "chars_extraidos": kw.get("texto_extraido") and len(kw["texto_extraido"]) or 0},
    )
    data = {
        "file": (io.BytesIO(b"col1,col2\n1,2\n"), "dados.csv"),
        "mode": "analyze",
        "pergunta": "Resuma",
        "thread_id": "api-analise",
    }
    resp = admin_client.post("/api/nik/ops/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["mode"] == "analyze"
    assert body["texto"] == "Análise pronta."
    assert body["historico_id"]
