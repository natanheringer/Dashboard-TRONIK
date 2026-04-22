"""One-shot script: extrai CSS e HTML views do planos_preview.html.

Nao precisa rodar toda hora - so quando o preview HTML mudar. Gera:
- estatico/css/v2/tokens.css   (apenas o bloco :root)
- estatico/css/v2/preview.css  (todo o CSS do preview)
- estatico/js/v2/preview.js    (o <script> de navegacao entre views)
- templates/preview/_views_raw.html (todos os <div class="view"> concatenados
                                     sem alteracoes, para recorte manual)
- templates/preview/_sidebar_raw.html (o <aside class="sidebar"> original)

Idempotente: sobrescreve os arquivos destino.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "planos_preview.html"

html = SRC.read_text(encoding="utf-8")

# --- CSS completo + tokens isolados ----------------------------------------
m_style = re.search(r"<style>(.*?)</style>", html, flags=re.DOTALL)
if not m_style:
    raise SystemExit("Bloco <style> nao encontrado no preview.")
css_full = m_style.group(1).strip()

m_tokens = re.search(r":root\s*\{[^}]*\}", css_full, flags=re.DOTALL)
tokens_only = m_tokens.group(0) if m_tokens else ""

(ROOT / "estatico" / "css" / "v2" / "tokens.css").write_text(
    "/* Auto-gerado por scripts/extrair_preview_css.py */\n" + tokens_only + "\n",
    encoding="utf-8",
)
(ROOT / "estatico" / "css" / "v2" / "preview.css").write_text(
    "/* Auto-gerado por scripts/extrair_preview_css.py */\n" + css_full + "\n",
    encoding="utf-8",
)

# --- Script de navegacao entre views --------------------------------------
m_script = re.search(r"<script>(.*?)</script>", html, flags=re.DOTALL)
if m_script:
    # Salva como snapshot - o JS real vive em estatico/js/v2/preview.js
    (ROOT / "estatico" / "js" / "v2" / "_preview_snapshot.js").write_text(
        "/* Auto-gerado por scripts/extrair_preview_css.py */\n" + m_script.group(1).strip() + "\n",
        encoding="utf-8",
    )

# --- Sidebar e views (raw) ------------------------------------------------
m_sidebar = re.search(r"(<aside class=\"sidebar\">.*?</aside>)", html, flags=re.DOTALL)
if m_sidebar:
    (ROOT / "templates" / "preview" / "_partials" / "_sidebar_raw.html").write_text(
        m_sidebar.group(1) + "\n", encoding="utf-8"
    )

lines = html.splitlines()
starts: list[tuple[str, int]] = []
for i, line in enumerate(lines):
    m = re.search(r'<div class="view[^"]*" id="view-([^"]+)">', line)
    if m:
        starts.append((m.group(1), i))
main_end = next(
    (i for i, line in enumerate(lines) if "</main>" in line), len(lines)
)
boundaries = [i for _, i in starts] + [main_end]
views_out: dict[str, list[str]] = {}
for idx, (name, start) in enumerate(starts):
    end = boundaries[idx + 1]
    block = lines[start:end]
    # remove o wrapper <div class="view ..."> ... </div> externo
    # primeira linha = abertura; ultima linha nao-vazia de fechamento e </div>
    inner = block[1:]
    while inner and inner[-1].strip() == "":
        inner.pop()
    if inner and inner[-1].strip() == "</div>":
        inner.pop()
    views_out[name] = inner

views_dir = ROOT / "templates" / "preview" / "views"
views_dir.mkdir(exist_ok=True)
for name, block in views_out.items():
    dest = views_dir / f"_{name}_raw.html"
    dest.write_text("\n".join(block) + "\n", encoding="utf-8")

print(f"[ok] extraido:")
print(f"  estatico/css/v2/tokens.css   ({len(tokens_only)} bytes)")
print(f"  estatico/css/v2/preview.css  ({len(css_full)} bytes)")
if m_script:
    print(f"  estatico/js/v2/_preview_snapshot.js ({len(m_script.group(1))} bytes)")
print(f"  templates/preview/views/_*_raw.html  ({len(views_out)} views: {list(views_out)})")
