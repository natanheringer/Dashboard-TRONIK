# Preview v2 — lentidão no reload (investigação)

## Sintoma

Telemetria e WebSocket atualizam em tempo real, mas **F5 / navegação entre rotas** demora a mostrar o mapa ou painéis.

## Causas principais (ordenadas por impacto)

### 1. Mapa: segunda carga pesada após o HTML

- SSR (`/preview/mapa`) já faz `estatisticas_resumo`, parceiros, detalhe opcional.
- O browser ainda chama **`GET /api/coletores/mapa`**, que antes usava `coletores_monitoramento()` (todos os coletores + **joinedload de sensores**).
- Em paralelo: **Socket.IO polling**, Leaflet + MarkerCluster (CDN), Google Fonts.

**Correção aplicada:** `coletores_para_mapa()` + bateria agregada em SQL + cache 20s (`preview:coletores_geojson`). Socket.IO adiado ~900ms no mapa. Scripts Leaflet com `defer`.

### 2. Monitoramento: ML no servidor a cada reload

- `_obter_ranking_ml` e `_obter_predicoes_map` rodavam em todo GET da página.

**Correção aplicada:** cache 60s (`preview:ranking_ml`, `preview:predicoes_map`).

### 3. Gestão: API duplicada e sem cache frontend

- `carregarDropdowns` e `carregarListaColetores` chamavam `obterTodosColetores()` duas vezes.
- `gestao.html` não carregava `cache.js` → sem deduplicação de GET.

**Correção aplicada:** uma fetch + `cache.js` + `obterOuCalcular` com dedupe in-flight.

### 4. Navegação full page

- Sidebar usa `window.location.href` (reload completo), não SPA. Cada troca de view refaz HTML + assets + DB.

**Follow-up (não implementado):** prefetch de `/api/coletores/mapa` no hover do link Mapa; ou HTMX shell parcial.

## Como medir no Railway

1. DevTools → Network → reload em `/preview/mapa`.
2. Comparar TTFB de `mapa` (HTML) vs `coletores/mapa` (JSON).
3. Ver se `socket.io` polling inicia antes do JSON terminar (deve atrasar após o fix).

## Cache e dados frescos

| Chave | TTL | Notas |
|-------|-----|--------|
| `preview:estatisticas_resumo` | 60s | já existia |
| `preview:coletores_geojson` | 20s | nível no mapa também via WebSocket |
| `preview:parceiros_select` | 600s | dropdown mapa/relatórios |
| `preview:ranking_ml` / `preview:predicoes_map` | 60s | monitoramento |

Invalidar `preview:coletores_geojson` após CRUD de coletor é opcional (TTL curto cobre a maioria dos casos).
