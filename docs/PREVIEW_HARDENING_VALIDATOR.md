# Validador — Onda 1 (2026-06-02)

## Comandos

```bash
python -m ruff check .
python -m pytest tests/ -q --tb=line
```

## Resultado

| Check | Status |
|-------|--------|
| Ruff | PASS (1 import fix auto) |
| Pytest | PASS — 487 passed |

## Regressões corrigidas

- `test_prospeccao_saude.py` — login admin (GET `/saude` agora `@admin_required`)
- `test_api_prospeccao.py` — `admin_client` fixture
- `test_nik_conversa.py` — ops/conversa admin
- `test_crm_prospeccao_bridge.py` — CRM admin
- `test_api_endpoints_restantes.py` — simular-niveis admin

## Go / no-go

**GO** para merge da onda 1 (sem migração DB).

---

## Validação final (ondas 1–4) — 2026-06-02

| Check | Status |
|-------|--------|
| Ruff | PASS |
| Pytest suite | **495 passed** (incl. `test_preview_hardening_wave4.py`) |
| Smoke hardening | PASS |

**GO** deploy — ver `PREVIEW_HARDENING_ORQUESTRADOR.md`.
