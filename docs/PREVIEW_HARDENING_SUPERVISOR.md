# Supervisor — Onda 1 (2026-06-02)

Revisão pós-implementação orquestrada (subagents indisponíveis; execução direta).

## Checklist P1–P8 (performance)

| ID | Status | Notas |
|----|--------|-------|
| P1 | OK | `func.avg` em `estatisticas_resumo` |
| P2 | OK | Cache 60s via `obter_cache().obter_ou_calcular` |
| P3 | OK | `carregarFunil()` removido; funil via `pipelineData` |
| P4 | OK | Chart.js removido de `crm.html` |
| P5 | OK | Lucide com `defer` |
| P6 | OK | Socket.IO só em `monitoramento.html` e `mapa.html` |
| P7 | OK | `joinedload` em `obter_ranking` |
| P8 | OK | `coletores_nomes_atencao(db)` — LIMIT 4 SQL |

## Checklist S1–S6 (segurança)

| ID | Status | Notas |
|----|--------|-------|
| S1 | OK | `_redirect_pos_login_seguro` rejeita URLs externas |
| S2 | OK | CRM API → `@decorators.admin_required` |
| S3 | OK | Prospecção GET → `@admin_required` |
| S4 | OK | Nik `/ops/conversa` → `@admin_required` |
| S5 | OK | `SystemExit` se `PREVIEW_PUBLIC=true` em prod |
| S6 | OK | ML recalc/retreinar + simular-niveis → admin |

## Riscos / follow-up

- **Socket.IO ordem de script:** carregado em `scripts_extra` após `preview.js` (defer); OK pois defer executa antes de DOMContentLoaded.
- **Parceiros perdem API CRM/prospecção:** alinhado ao preview admin-only; parceiros usam `/preview/parceiro`.
- **Onda 2+:** ver `PREVIEW_HARDENING_TRACKER.md`.

## Aprovação

- [x] Diff focado, sem refactors desnecessários
- [x] Testes atualizados (`admin_client`, simular admin)
- [ ] Validador pytest/ruff (pendente execução)
