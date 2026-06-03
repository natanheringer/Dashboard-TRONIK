# Preview Hardening — Onda 4 (AuthZ & hardening)

**Data:** 2026-06-02 · **Status:** concluída

## Resumo

Onda 4 fecha lacunas de autorização (escopo parceiro, IDOR Maiara), reforça cookies/sessão, fail-fast de telemetria em produção, rate limit em formulário público e respostas 500 genéricas na API de prospecção.

| ID | Mudança | Arquivos |
|----|---------|----------|
| S7 | `escopo_parceiro_id` em coletas, relatórios (GET + PDF), contratos; comercial admin-only | `coletas.py`, `relatorios.py`, `contratos.py`, `comercial.py`, `nik.py` (Maiara generate) |
| S8 | Export Maiara filtra por `usuario_id` (admin bypass) | `nik_service.py`, `nik.py` |
| S9 | `SESSION_COOKIE_SAMESITE=Strict` em produção | `app.py` |
| S10 | `TELEMETRIA_ALLOW_NO_TOKEN=true` → `SystemExit` em prod | `app.py` |
| S11 | `@admin_required` em `POST /api/coletor` | `coletores.py` |
| S12 | Rate limit 10/min por IP em `POST /preview/solicitar-coletor` (cache memória) | `preview.py` |
| S13 | Erros 500 prospecção sem `str(e)` ao cliente | `prospeccao.py` |

## Detalhes técnicos

### S7 — Escopo parceiro

- **Coletas:** `parceiro_id` na query e no histórico passam por `escopo_parceiro_id()`.
- **Relatórios:** `@login_required` adicionado ao GET `/api/relatorios`; PDF e JSON usam escopo.
- **Contratos:** listagem e GET por ID filtram via `Coletor.parceiro_id`; `coletor_id` de outro parceiro retorna lista vazia / 404.
- **Comercial:** todos os endpoints passam de `@login_required` para `@admin_required` (dashboard global, sem filtro por parceiro na API).

### S8 — IDOR Maiara

`obter_relatorio_maiara(..., usuario_id=, admin=)` retorna `None` se o relatório pertence a outro usuário (exceto admin).

### S12 — Rate limit solicitar-coletor

Blueprint preview permanece isento do Flask-Limiter global; limite aplicado via cache in-memory (`10 req / 60s / IP`) para não afetar navegação SSR autenticada.

## Testes adicionados/atualizados

- `tests/test_rbac_parceiro.py` — coletas escopo, POST coletor 403, comercial 403
- `tests/test_api_blueprints_auth_smoke.py` — `/api/relatorios` protegido
- `tests/test_estatisticas_relatorios.py`, `test_api_lixeiras.py`, `test_geocodificacao.py`, `test_robustez.py` — auth admin onde necessário

## Validação

```bash
python -m ruff check .          # OK
python -m pytest tests/ -q      # 493 passed
```

## Deploy

- Sem migração DB.
- Produção: confirmar `TELEMETRIA_ALLOW_NO_TOKEN` **não** definido (ou `false`); `PREVIEW_PUBLIC=false`.
- SameSite Strict pode exigir que links externos de login redirecionem via GET same-site (comportamento esperado).
