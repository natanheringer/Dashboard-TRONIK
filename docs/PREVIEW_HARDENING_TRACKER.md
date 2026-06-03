# Preview v2 — Hardening & Performance Tracker

Operacional: auditoria 2026-06-02 · orquestração multi-agente sequencial.

**Legenda:** `[ ]` pendente · `[~]` em progresso · `[x]` feito · `[—]` descartado

---

## Onda 1 — Quick wins + segurança crítica (prioridade imediata)

| ID | Área | Tarefa | Arquivos-alvo | Status |
|----|------|--------|---------------|--------|
| P1 | Perf | `estatisticas_resumo`: `func.avg` em vez de `Coletor.all()` | `preview_service.py` | [x] |
| P2 | Perf | Cache TTL 60s em `estatisticas_resumo` | `preview_service.py`, `auxiliares.py` (padrão cache) | [x] |
| P3 | Perf | Remover `carregarFunil()` redundante | `crm.js` | [x] |
| P4 | Perf | Remover Chart.js não usado do CRM preview | `crm.html` | [x] |
| P5 | Perf | Lucide com `defer` + init após DOM | `base_v2.html`, `preview.js` | [x] |
| P6 | Perf | Socket.IO só em monit/mapa | `base_v2.html`, páginas | [x] |
| P7 | Perf | Fix N+1 ranking ML (`joinedload`) | `ml_score.py` | [x] |
| P8 | Perf | Home: LIMIT 4 coletores atenção (SQL) | `preview_service.py`, `preview.py` | [x] |
| S1 | Sec | Validar `next` no login (anti open-redirect) | `auth.py` | [x] |
| S2 | Sec | `@admin_required` em rotas CRM API | `rotas/api/crm.py` | [x] |
| S3 | Sec | `@admin_required` em prospecção GET | `rotas/api/prospeccao.py` | [x] |
| S4 | Sec | `@admin_required` em Nik `/ops/conversa` | `rotas/api/nik.py` | [x] |
| S5 | Sec | Falhar startup se `PREVIEW_PUBLIC=true` em prod | `app.py` | [x] |
| S6 | Sec | `@admin_required` em ML recalc + simular-niveis | `ml.py`, `auxiliares.py` | [x] |

---

## Onda 2 — Performance média

| ID | Tarefa | Status |
|----|--------|--------|
| P9 | Parar HTMX full reload no WebSocket (patch card) | [x] |
| P10 | Relatórios: agregação SQL vs `.all()` | [x] |
| P11 | Mapa: fetch geo API vs JSON inline | [x] |
| P12 | CRM endpoint agregado + pipeline paginado | [x] |
| P13 | Cap/warning limite prospecção >200 | [x] |
| P14 | Parceiro page: batch narrativas | [x] |

---

## Onda 3 — Prospecção & CRM profundo

| ID | Tarefa | Status |
|----|--------|--------|
| P15 | Percentil pré-computado / window SQL | [x] |
| P16 | `buscar_candidatos_por_nome_empresa` sem full scan | [x] |
| P17 | Race lock criar pipeline (`FOR UPDATE` / unique) | [x] |
| P18 | Escape `%` `_` em LIKE CRM | [x] |

---

## Onda 4 — AuthZ & hardening

| ID | Tarefa | Status |
|----|--------|--------|
| S7 | `escopo_parceiro_id` em coletas/relatórios/comercial/contratos | [x] |
| S8 | IDOR Maiara report por `usuario_id` | [x] |
| S9 | CSRF ou SameSite=Strict + header mutações | [x] |
| S10 | Telemetria: fail-fast prod sem token | [x] |
| S11 | `@admin_required` POST coletor | [x] |
| S12 | Rate limit `solicitar-coletor` | [x] |
| S13 | Erros 500 genéricos (sem `str(e)` ao cliente) | [x] |

---

## Pipeline de agentes (sequencial)

```
Implementador → Supervisor → Validador (pytest/ruff) → Orquestrador final
```

| Etapa | Agente | Entrada | Saída |
|-------|--------|---------|-------|
| 1 | Implementador | Onda 1 IDs acima | Diff + checklist atualizado |
| 2 | Supervisor | Diff onda 1 | Aprovação / lista de correções |
| 3 | Validador | Código pós-fix | pytest + ruff + regressões |
| 4 | Orquestrador | Relatórios 1–3 | Go/no-go deploy |

---

## Comandos de validação

```bash
cd "/run/media/natanheringer/Novo volume/docs_backup/GitHub/Dashboard-TRONIK"
python -m ruff check .
python -m pytest tests/ -q --tb=short
python -m pytest tests/test_preview_crm_shell.py tests/test_api_blueprints_auth_smoke.py tests/test_prospeccao_criar_pipeline.py -q
```

---

## Notas de deploy

- Onda 1 não exige migração DB.
- Após S2–S4: parceiros perdem acesso direto à API CRM/prospecção/Nik ops (alinhado ao preview admin-only).
- Verificar `PREVIEW_PUBLIC=false` no Railway antes do deploy.

---

## Changelog operacional

| Data | Etapa | Resultado |
|------|-------|-----------|
| 2026-06-02 | Auditoria | 2 subagents explore — performance + security |
| 2026-06-02 | Onda 1 kickoff | Tracker criado · pipeline sequencial iniciado |
| 2026-06-02 | Onda 1 implementação | P1–P8, S1–S6 concluídos (orquestrador direto) |
| 2026-06-02 | Validador | 487 pytest PASS · ruff OK — ver `PREVIEW_HARDENING_VALIDATOR.md` |
| 2026-06-02 | Orquestrador | **GO** onda 1 |
| 2026-06-02 | Onda 2 implementação | P9–P14 concluídos |
| 2026-06-02 | Onda 3 implementação | P15–P18 concluídos |
| 2026-06-02 | Onda 4 implementação | S7–S13 concluídos — ver `PREVIEW_HARDENING_ONDA4.md` |
| 2026-06-02 | Orquestrador final | **GO** ondas 1–4 · 493+ pytest — ver `PREVIEW_HARDENING_ORQUESTRADOR.md` |

---

## Status final

**Todas as ondas concluídas.** Pronto para PR → merge → deploy Railway com checklist do orquestrador.
