# Orquestrador final — Preview Hardening (ondas 1–4)

**Data:** 2026-06-02 · **Branch:** `feature/gestao-v2-preview`

## Veredito

**GO** para merge e deploy em produção (Railway), desde que o checklist de env abaixo seja aplicado.

Nenhuma migração de banco é necessária para as quatro ondas.

---

## Escopo entregue

| Onda | IDs | Foco |
|------|-----|------|
| 1 | P1–P8, S1–S6 | Performance quick wins + auth crítica (CRM, prospecção, Nik, ML) |
| 2 | P9–P14 | WebSocket patch, SQL agregado, mapa lazy, CRM dashboard, prospecção cap |
| 3 | P15–P18 | Percentil SQL, busca CRM sem full scan, lock pipeline, LIKE escape |
| 4 | S7–S13 | Escopo parceiro, IDOR Maiara, SameSite Strict, telemetria fail-fast, admin POST coletor, rate limit landing |

**Total:** 32 itens · todos `[x]` no tracker.

---

## Validação final

```bash
cd "/run/media/natanheringer/Novo volume/docs_backup/GitHub/Dashboard-TRONIK"
python -m ruff check .
python -m pytest tests/ -q --tb=short
python -m pytest tests/test_preview_crm_shell.py \
  tests/test_api_blueprints_auth_smoke.py \
  tests/test_prospeccao_criar_pipeline.py \
  tests/test_rbac_parceiro.py \
  tests/test_crm_prospeccao_bridge.py \
  tests/test_preview_hardening_wave4.py -q
```

| Check | Resultado |
|-------|-----------|
| Ruff | PASS |
| Pytest suite completa | **493+ passed** |
| Smoke hardening (CRM, auth, RBAC, onda 4) | PASS |

---

## Impacto operacional pós-deploy

### Administradores

- Sem regressão funcional esperada no preview v2.
- CRM, prospecção, Nik ops e comercial continuam admin-only via API.

### Usuários parceiro

- Perdem acesso direto à API de CRM, prospecção, Nik ops e comercial.
- Veem apenas coletores/coletas/relatórios/contratos do **próprio parceiro** (escopo forçado).
- Não podem criar coletores (`POST /api/coletor` → 403).

### Público (landing)

- `POST /preview/solicitar-coletor` limitado a **10 req/min/IP** (cache in-memory por worker).

### Telemetria (ESP32)

- Produção **não inicia** se `TELEMETRIA_ALLOW_NO_TOKEN=true`.
- Sensores devem ter `api_token` ou `TELEMETRY_SHARED_SECRET` configurado.

---

## Checklist Railway (obrigatório)

| Variável | Valor produção |
|----------|----------------|
| `FLASK_ENV` | `production` |
| `PREVIEW_PUBLIC` | `false` |
| `TELEMETRIA_ALLOW_NO_TOKEN` | `false` ou ausente |
| `RATELIMIT_STORAGE_URL` | `redis://...` (não `memory://`) |
| `SESSION_COOKIE_SECURE` | `true` |
| `CORS_ORIGINS` | domínio(s) real(is) |
| `SECRET_KEY` | 32+ chars aleatórios |

**Nota:** `SESSION_COOKIE_SAMESITE=Strict` é aplicado automaticamente pelo app quando `FLASK_ENV=production` (não precisa env).

---

## Smoke manual pós-deploy (15 min)

1. Login admin → `/preview/home`, `/preview/crm`, `/preview/monitoramento`
2. Login parceiro → `/preview/parceiro` OK; `/preview/gestao` → 403
3. `GET /api/coletores` como parceiro → só coletores do parceiro
4. `GET /api/comercial/dashboard` como parceiro → 403
5. Landing → enviar solicitação coletor; repetir 11× → 429 na 11ª
6. Health: `GET /api/health` → 200 sem login

---

## Riscos residuais (backlog pós-merge, não bloqueantes)

- CSRF explícito (Flask-WTF) — mitigado por SameSite Strict + JSON APIs autenticadas
- Rate limit `solicitar-coletor` in-memory — em multi-worker contador não é global (aceitável; Redis seria melhoria futura)
- `innerHTML` restante em `mapa.js` — fora do escopo deste hardening

---

## Artefatos do pipeline

| Documento | Conteúdo |
|-----------|----------|
| `PREVIEW_HARDENING_TRACKER.md` | Backlog master + changelog |
| `PREVIEW_HARDENING_SUPERVISOR.md` | Revisão onda 1 |
| `PREVIEW_HARDENING_VALIDATOR.md` | Validação onda 1 + final |
| `PREVIEW_HARDENING_ONDA2.md` | Resumo onda 2 |
| `PREVIEW_HARDENING_ONDA3.md` | Resumo onda 3 |
| `PREVIEW_HARDENING_ONDA4.md` | Resumo onda 4 |
| **Este arquivo** | Go/no-go deploy |

---

## Próximo passo sugerido

1. Revisar diff na branch `feature/gestao-v2-preview`
2. Abrir PR → `main`
3. Aplicar checklist env no Railway
4. Deploy + smoke manual acima
