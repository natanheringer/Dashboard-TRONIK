"""Memória de thread da Nik: resumo LLM após >12 mensagens."""

from datetime import datetime, timedelta

from banco_dados.modelos import NikConversa
from banco_dados.services import nik_service
from banco_dados.services.nik_provider import NikResposta


def _seed_thread(db_session, usuario_id: int | None, thread_id: str, n: int) -> list[NikConversa]:
    base = datetime(2026, 5, 1, 10, 0, 0)
    rows: list[NikConversa] = []
    for i in range(n):
        row = NikConversa(
            usuario_id=usuario_id,
            thread_id=thread_id,
            pergunta=f"Pergunta {i + 1}",
            resposta=f"Resposta {i + 1}",
            criado_em=base + timedelta(minutes=i),
        )
        db_session.add(row)
        rows.append(row)
    db_session.commit()
    for row in rows:
        db_session.refresh(row)
    return rows


def test_resumo_thread_nao_dispara_com_poucas_mensagens(db_session, monkeypatch):
    chamadas: list[dict] = []

    def fake_chamar(*args, **kwargs):
        chamadas.append(kwargs)
        return NikResposta(
            texto="resumo",
            modelo_usado="mock",
            tokens_prompt=1,
            tokens_resposta=1,
            latencia_ms=1,
            sucesso=True,
        )

    monkeypatch.setattr(nik_service.provider, "chamar_modelo", fake_chamar)
    _seed_thread(db_session, usuario_id=1, thread_id="ops-a", n=10)

    out = nik_service._resumir_thread_se_necessario(db_session, 1, "ops-a")
    assert out is None
    assert chamadas == []


def test_resumo_thread_dispara_e_persiste(db_session, monkeypatch):
    resumo_llm = (
        "O usuário pediu status de coletores em Taguatinga; a Nik indicou três em atenção "
        "e sugeriu revisar rotas na próxima semana."
    )

    def fake_chamar(system_prompt, user_prompt, **kwargs):
        assert "Resuma a conversa" in user_prompt
        assert kwargs.get("modelo") == "gemma-3-1b-it"
        return NikResposta(
            texto=resumo_llm,
            modelo_usado=kwargs.get("modelo"),
            tokens_prompt=10,
            tokens_resposta=20,
            latencia_ms=5,
            sucesso=True,
        )

    monkeypatch.setattr(nik_service.provider, "chamar_modelo", fake_chamar)
    monkeypatch.setenv("NIK_MODELO_RESUMO", "gemma-3-1b-it")
    rows = _seed_thread(db_session, usuario_id=2, thread_id="ops-b", n=13)

    out = nik_service._resumir_thread_se_necessario(db_session, 2, "ops-b")
    assert out is not None
    assert len(out) <= 400

    latest = (
        db_session.query(NikConversa)
        .filter(NikConversa.thread_id == "ops-b", NikConversa.usuario_id == 2)
        .order_by(NikConversa.criado_em.desc())
        .first()
    )
    assert latest is not None
    assert latest.id == rows[-1].id
    assert latest.resumo_thread == out[:400]


def test_montar_contexto_inclui_thread_resumo(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "_resumir_thread_se_necessario",
        lambda db, usuario_id, thread_id: "Resumo compacto da thread para o modelo.",
    )
    monkeypatch.setattr(nik_service, "_inferir_consulta_usuario", lambda db, msg: {})
    monkeypatch.setattr(
        nik_service,
        "_planejar_ferramentas_completo",
        lambda msg: ([], "heuristic"),
    )
    monkeypatch.setattr(
        nik_service,
        "_executar_plano_ferramentas",
        lambda db, plano, usuario_id=None: ({}, []),
    )
    monkeypatch.setattr(
        nik_service,
        "_historico_thread",
        lambda db, usuario_id, thread_id, limite=8: [
            {"pergunta": "(resumo da thread)", "resposta": "Resumo compacto", "tipo": "resumo_thread"},
            {"pergunta": "Q1", "resposta": "A1"},
        ],
    )

    ctx = nik_service._montar_contexto_conversa_integrada(
        db_session, "como está a operação?", usuario_id=3, thread_id="maiara"
    )
    assert ctx.get("thread_resumo") == "Resumo compacto da thread para o modelo."
    assert ctx.get("historico_thread")


def test_historico_thread_inclui_resumo_quando_presente(db_session):
    rows = _seed_thread(db_session, usuario_id=4, thread_id="ops-c", n=3)
    rows[-1].resumo_thread = "Contexto anterior: foco em alertas de coleta."
    db_session.commit()

    hist = nik_service._historico_thread(db_session, 4, "ops-c", limite=5)
    assert hist[0]["tipo"] == "resumo_thread"
    assert "Contexto anterior" in hist[0]["resposta"]
    assert hist[1]["pergunta"] == "Pergunta 1"


def test_schema_compat_adds_resumo_thread_column():
    from sqlalchemy import create_engine, inspect, text

    from banco_dados.schema_compat import aplicar_compat_schema

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE nik_conversas (
                    id INTEGER PRIMARY KEY,
                    pergunta VARCHAR(4000) NOT NULL,
                    resposta VARCHAR(8000) NOT NULL
                )
                """
            )
        )

    aplicar_compat_schema(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("nik_conversas")}
    assert "resumo_thread" in cols
    assert "meta_resposta" in cols
