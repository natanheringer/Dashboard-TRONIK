"""Smoke test do preview v2.

Loga e bate nas 5 rotas de /preview/*, reportando status, tamanho e
se os assets v2 (css/js) estao referenciados no HTML.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault(
    "SECRET_KEY", "smoke-test-key-with-32-plus-chars-XXXXXXXX"
)
os.environ.setdefault("ADMIN_USERNAME", "smoke")
os.environ.setdefault("ADMIN_EMAIL", "smoke@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "Smoke123!@#")

import app  # noqa: E402

cli = app.app.test_client()

r = cli.post(
    "/auth/login",
    json={"username": "smoke", "senha": "Smoke123!@#"},
)
if r.status_code != 200:
    print(f"[fail] login: {r.status_code} body={r.data[:200]!r}")
    sys.exit(1)
print(f"[ok] login: {r.status_code}")

rotas = [
    "/preview/",
    "/preview/monitoramento",
    "/preview/mapa",
    "/preview/relatorios",
    "/preview/parceiro",
]
falhas = 0
for rota in rotas:
    r = cli.get(rota)
    html = r.data.decode("utf-8", "ignore")
    tem_css = "/static/css/v2/preview.css" in html
    tem_motion = "/static/css/v2/motion.css" in html
    tem_js = "/static/js/v2/preview.js" in html
    tem_htmx = "htmx.org" in html
    ok = r.status_code == 200 and tem_css and tem_motion and tem_js and tem_htmx
    marker = "ok  " if ok else "FAIL"
    print(
        f"[{marker}] {rota:30s} status={r.status_code} css={tem_css} motion={tem_motion} js={tem_js} htmx={tem_htmx} bytes={len(html)}"
    )
    if not ok:
        falhas += 1

# Bate tambem nos assets
for asset in [
    "/static/css/v2/tokens.css",
    "/static/css/v2/preview.css",
    "/static/css/v2/motion.css",
    "/static/js/v2/preview.js",
]:
    r = cli.get(asset)
    print(f"[{'ok  ' if r.status_code == 200 else 'FAIL'}] {asset:30s} status={r.status_code} bytes={len(r.data)}")
    if r.status_code != 200:
        falhas += 1


# Envelope padronizado de erros: 404 em /api/ deve bater com o novo formato
r = cli.get("/api/rota-que-nao-existe")
j = r.get_json()
ok404 = (
    r.status_code == 404
    and j is not None
    and j.get("ok") is False
    and j.get("dados") is None
    and isinstance(j.get("erros"), list)
    and j["erros"]
    and j["erros"][0].get("codigo") == "NAO_ENCONTRADO"
    and j.get("erro")  # legacy alias mantido
)
print(f"[{'ok  ' if ok404 else 'FAIL'}] envelope 404 /api/* -> {j}")
if not ok404:
    falhas += 1

# ErroValidacao do Pydantic tambem deve cair no envelope global
r = cli.post("/api/sensor/telemetria", json={"sensor_id": "nao-eh-int"})
j = r.get_json()
ok_val = (
    r.status_code == 400
    and j is not None
    and j.get("ok") is False
    and isinstance(j.get("erros"), list)
    and j["erros"]
    and j["erros"][0].get("codigo") == "VALIDACAO"
)
print(f"[{'ok  ' if ok_val else 'FAIL'}] envelope validacao telemetria -> status={r.status_code} body={j}")
if not ok_val:
    falhas += 1

sys.exit(1 if falhas else 0)
