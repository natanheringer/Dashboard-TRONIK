"""Preview v2: shell CRM/comercial/contratos e redirects legados."""

import pytest

from banco_dados.modelos import Parceiro, Usuario


@pytest.fixture
def admin_preview_client(client, db_session):
    """Cliente autenticado como administrador."""
    admin = Usuario(
        username="admin_preview",
        email="admin_preview@test.local",
        ativo=True,
        admin=True,
    )
    admin.set_senha("AdminPreview123!")
    db_session.add(admin)
    db_session.commit()

    r = client.post(
        "/auth/login",
        json={"username": "admin_preview", "senha": "AdminPreview123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


@pytest.fixture
def parceiro_preview_client(client, db_session):
    """Cliente autenticado como parceiro (não-admin)."""
    p = Parceiro(nome="Parceiro Preview Shell")
    db_session.add(p)
    db_session.flush()

    u = Usuario(
        username="parceiro_preview_shell",
        email="parceiro_shell@test.local",
        ativo=True,
        admin=False,
        parceiro_id=p.id,
    )
    u.set_senha("ParceiroShell123!")
    db_session.add(u)
    db_session.commit()

    r = client.post(
        "/auth/login",
        json={"username": "parceiro_preview_shell", "senha": "ParceiroShell123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return client


def test_admin_preview_crm_200(admin_preview_client):
    resp = admin_preview_client.get("/preview/crm")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "CRM · Pipeline de Vendas" in html
    assert "crm.js" in html


def test_parceiro_preview_crm_403(parceiro_preview_client):
    resp = parceiro_preview_client.get("/preview/crm")
    assert resp.status_code == 403


def test_legacy_crm_redirects_to_preview(admin_preview_client):
    resp = admin_preview_client.get("/crm", follow_redirects=False)
    assert resp.status_code == 301
    location = resp.headers.get("Location", "")
    assert "/preview/crm" in location


def test_preview_comercial_contratos_redirect_to_crm(admin_preview_client):
    for path in ("/preview/comercial", "/preview/contratos"):
        resp = admin_preview_client.get(path, follow_redirects=False)
        assert resp.status_code == 302
        assert "/preview/crm" in resp.headers.get("Location", "")


def test_legacy_comercial_contratos_redirect_to_preview_crm(admin_preview_client):
    for path in ("/comercial", "/contratos"):
        resp = admin_preview_client.get(path, follow_redirects=False)
        assert resp.status_code == 301
        assert "/preview/crm" in resp.headers.get("Location", "")
