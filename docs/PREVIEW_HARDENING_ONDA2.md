# Onda 2 — Performance média (2026-06-02)

## Entregue

| ID | Mudança | Arquivos |
|----|---------|----------|
| P9 | WebSocket atualiza card/marker sem HTMX full reload | `estatico/js/v2/preview.js` |
| P10 | `resumo_relatorios` com agregação SQL | `preview_service.py` |
| P11 | Mapa lazy: `GET /api/coletores/mapa` + fetch client | `coletores.py`, `mapa.html`, `mapa-preview.js`, `preview.py` |
| P12 | `GET /api/crm/dashboard` + pipeline paginado (`page`/`per_page`) | `crm.py`, `crm.js` |
| P13 | Aviso UI limite >200 na prospecção | `prospeccao.html`, `preview-prospeccao.js` |
| P14 | Narrativas parceiro em batch (1 query) | `ml_narrativa.py`, `preview.py` |

## Validação

```
ruff check .  → OK
pytest tests/ → 487 passed
```

## Deploy

Sem migração DB. Mapa exige admin logado para `/api/coletores/mapa` (já `@admin_required`).
