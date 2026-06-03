# Onda 3 — Prospecção & CRM profundo (2026-06-02)

| ID | Entrega |
|----|---------|
| P15 | Percentil via `ROW_NUMBER/COUNT` window SQL; filtro por IDs retornados |
| P16 | Busca CRM por empresa: `empresa_candidata` indexada → scores filtrados |
| P17 | `with_for_update()` + revalidação pós-lock em `criar_pipeline_de_candidato` |
| P18 | `_sql_like_contains()` escapa `%` e `_` em pipelines CRM |

## Validação

```
ruff check .  → OK
pytest tests/ → 489 passed
```
