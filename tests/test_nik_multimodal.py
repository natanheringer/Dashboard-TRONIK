"""Testes da foundation multimodal da Nik (análise de imagem)."""

from __future__ import annotations

import base64
import io

from banco_dados.services import nik_provider as np, nik_service as nik_service
from banco_dados.services.nik_provider import NikResposta


def _tiny_png() -> bytes:
    """PNG 1x1 válido (mínimo) para payloads de teste."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _login_admin(client, db_session):
    from banco_dados.modelos import Usuario

    admin = Usuario(
        username="nik_mm_admin",
        email="nik_mm_admin@test.local",
        admin=True,
        ativo=True,
    )
    admin.set_senha("AdminMm123!")
    db_session.add(admin)
    db_session.commit()
    r = client.post("/auth/login", json={"username": "nik_mm_admin", "senha": "AdminMm123!"})
    assert r.status_code == 200, r.get_data(as_text=True)


def test_analisar_imagem_multimodal_desabilitado(client, db_session, monkeypatch):
    monkeypatch.setenv("NIK_MULTIMODAL_ENABLED", "false")
    _login_admin(client, db_session)

    png = _tiny_png()
    resp = client.post(
        "/api/nik/ops/analisar-imagem",
        data={"imagem": (io.BytesIO(png), "test.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fonte"] == "multimodal_desabilitado"
    assert "multimodal desabilitado" in data["texto"]


def test_analisar_imagem_service_desabilitado(db_session, monkeypatch):
    monkeypatch.setenv("NIK_MULTIMODAL_ENABLED", "false")
    out = nik_service.analisar_imagem_coletor(db_session, _tiny_png())
    assert out["fonte"] == "multimodal_desabilitado"
    assert out["texto"] == "multimodal desabilitado"


def test_analisar_imagem_habilitado_mock_visao(client, db_session, monkeypatch):
    monkeypatch.setenv("NIK_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NIK_ENABLED", "true")
    monkeypatch.setenv("NIK_MODELO_OPS", "google/gemma-3-27b-it")

    def fake_visao(system, user_text, image_b64, mime="image/jpeg", **kwargs):
        assert image_b64
        assert mime.startswith("image/")
        return NikResposta(
            texto="Coletor com nível visual alto; priorize coleta.",
            modelo_usado="google/gemma-3-27b-it",
            tokens_prompt=10,
            tokens_resposta=8,
            latencia_ms=42,
            sucesso=True,
        )

    monkeypatch.setattr(np, "chamar_modelo_visao", fake_visao)
    _login_admin(client, db_session)

    b64 = base64.b64encode(_tiny_png()).decode("ascii")
    resp = client.post(
        "/api/nik/ops/analisar-imagem",
        json={"image_base64": b64, "mime": "image/png", "pergunta": "O que vê?"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fonte"] == "modelo"
    assert "priorize coleta" in data["texto"]
    assert data["modelo"] == "google/gemma-3-27b-it"


def test_analisar_imagem_exige_login(client):
    resp = client.post(
        "/api/nik/ops/analisar-imagem",
        json={"image_base64": base64.b64encode(_tiny_png()).decode("ascii")},
    )
    assert resp.status_code in {302, 401, 403}


def test_modelo_suporta_visao_gemma():
    assert np.modelo_suporta_visao("google/gemma-3-27b-it")
    assert not np.modelo_suporta_visao("llama-3.1-8b-instant")
