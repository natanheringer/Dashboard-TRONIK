# DESIGN_SYSTEM — Tronik Dashboard

Sistema de design completo do projeto dashboard-tronik, documentando tokens visuais, componentes e inconsistências identificadas.

---

## 1. PALETA DE CORES

### Definição Oficial (tokens.css / preview.css)

#### Backgrounds — Paleta Marfim/Papel Reciclado
| Token | Valor Hex | Descrição | Uso |
|-------|-----------|-----------|-----|
| `--paper-page` | `#f4efe3` | Fundo principal, marfim quente | Background de página (preview) |
| `--paper-card` | `#faf6ea` | Cards elevados, marfim claro | Containers, cards, sidebar |
| `--paper-elevated` | `#fffdf7` | Hover e destaques | Estados hover, elevação visual |
| `--paper-muted` | `#ebe4d2` | Seções secundárias | Background de seções menos importantes |
| `--paper-sunk` | `#e8dfc9` | Fundos de input, áreas rebaixadas | Inputs, selects, áreas inativas |

#### Tipografia — Paleta Ink (Texto)
| Token | Valor Hex | Descrição | Uso |
|-------|-----------|-----------|-----|
| `--ink-primary` | `#1c1810` | Quase preto, quente | Títulos h1, h2, texto principal |
| `--ink-secondary` | `#4a423a` | Corpo de texto, labels | Body text, descrições |
| `--ink-tertiary` | `#87796a` | Metadados, hints | Subtítulos, metadados, hints |
| `--ink-muted` | `#b5a78f` | Placeholders | Placeholders de input |

#### Bordas e Divisores
| Token | Valor Hex | Descrição | Uso |
|-------|-----------|-----------|-----|
| `--line-default` | `#d8cdb2` | Bordas de card padrão | Bordas principais de containers |
| `--line-strong` | `#a89975` | Linhas decorativas | Bordas mais destacadas |
| `--line-subtle` | `#e4d9bd` | Divisores internos | Linhas internas, separadores |

#### Marca Tronik — Verde Floresta
| Token | Valor Hex | Descrição | Uso |
|-------|-----------|-----------|-----|
| `--tronik` | `#1a5d3a` | Verde-floresta profundo | Botões primary, nav ativo, accent |
| `--tronik-hover` | `#134428` | Verde mais escuro | Hover em elementos tronik |
| `--tronik-soft` | `#d8e6d8` | Fundo de badge, hover sutil | Backgrounds soft para verde |
| `--tronik-ghost` | `rgba(26, 93, 58, 0.08)` | Verde quase transparente | Hover background em nav items |

#### Sinais Semânticos — Cores de Status
| Token | Valor Hex | Descrição | Uso |
|-------|-----------|-----------|-----|
| `--signal-ok` | `#1a5d3a` | Verde (normal, sucesso) | Status OK, check positivo |
| `--signal-ok-soft` | `#d8e6d8` | Verde claro | Background soft para status OK |
| `--signal-warn` | `#b0661e` | Âmbar profundo | Warning, atenção, nível ≥80% |
| `--signal-warn-soft` | `#f3e4cc` | Âmbar claro | Background soft para warning |
| `--signal-critical` | `#9b2a1f` | Vermelho terracota | Crítico, erro, nível ≥95% |
| `--signal-critical-soft` | `#f0d6cc` | Vermelho claro | Background soft para crítico |
| `--signal-neutral` | `#6b6254` | Cinza quente | Estado neutral, desativado |
| `--signal-neutral-soft` | `#ddd3bd` | Cinza claro | Background soft para neutral |

#### Cores Editoriais — Acentos Raros
| Token | Valor Hex | Descrição | Uso |
|-------|-----------|-----------|-----|
| `--accent-clay` | `#c4663a` | Terracota/clay | Badges raros, pequenos toques |
| `--accent-indigo` | `#2e4b6b` | Indigo profundo | Contra-ponto visual, avatares |

---

### Inconsistências Críticas na Paleta Detectadas

#### Problema 1: Dois Sistemas de Cores em Conflito

**Sistema Novo (v2) — tokens.css / preview.css:**
- Verde Tronik: `#1a5d3a` (floresta profundo)
- Background page: `#f4efe3` (marfim quente)
- Paleta de papel/ink: QUENTE, vintage, minimalista

**Sistema Legado — estilo.css / index.html:**
- Verde Tronik: `#27ae60` (verde moderno/vibrante)
- Background page: `#f0f2f5` (cinza neutro)
- Paleta: FRIA, moderna, corporativa

| Propriedade | Sistema V2 (novo) | Sistema Legado | Conflito |
|------------|-------------------|-----------------|---------|
| Primary green | `#1a5d3a` | `#27ae60` | Cores completamente diferentes |
| Page BG | `#f4efe3` (marfim) | `#f0f2f5` (cinza) | Temperatura visual oposta |
| Warning | `#b0661e` (âmbar) | `#f39c12` (laranja) | Tonalidades diferentes |
| Error | `#9b2a1f` (terracota) | `#e74c3c` (vermelho) | Saturação e tom diferentes |

**Impacto:** Quando usuários navegam entre preview e outras páginas, a experiência visual é **radicalmente diferente**. A marca não é reconhecível de forma consistente.

---

## 2. TIPOGRAFIA

### Fontes Definidas

```css
--font-display: "Montserrat", system-ui, sans-serif;
--font-body: "Roboto", system-ui, sans-serif;
--font-mono: "Roboto Mono", ui-monospace, monospace;
```

| Uso | Fonte | Exemplo |
|-----|-------|---------|
| Títulos, headings, brand | Montserrat | H1, H2, logo text |
| Corpo de texto, labels | Roboto | Parágrafos, body text, descrições |
| Dados, códigos, monoespaciais | Roboto Mono | KPIs, timestamps, IDs técnicos |

### Escala Tipográfica (Tokens CSS v2)

```
--text-xs:      0.75rem   (12px)    — labels, captions
--text-sm:      0.8125rem (13px)    — secondary text, hints
--text-base:    0.9375rem (15px)    — body padrão
--text-md:      1.0625rem (17px)    — card titles, emphasis
--text-lg:      1.25rem   (20px)    — section headers
--text-xl:      1.625rem  (26px)    — medium headings
--text-2xl:     2.25rem   (36px)    — large headings
--text-3xl:     3rem      (48px)    — page titles (h1)
--text-display: 4.5rem    (72px)    — hero titles
```

### Problema de Escala Tipográfica

**Sistema Legado (estilo.css) não define escala consistente:**
- Usa valores absolutos (14px, 16px, 13px, etc.)
- Mistura em uma fonte "system-ui" genérica
- Não há hierarquia clara entre tamanhos

**Sistema V2 (tokens.css) define escala modular:**
- Baseada em proporção de 1.1x (praticamente 1:1 com escala de Fibonacci)
- Consistente com Montserrat + Roboto
- Hierarquia clara

**Impacto:** Mistura de estilos causa inconsistência visual em páginas que transitam entre sistemas.

---

## 3. ESPAÇAMENTO

### Escala de Espaçamento

```css
--space-1:  0.25rem  (4px)
--space-2:  0.5rem   (8px)
--space-3:  0.75rem  (12px)
--space-4:  1rem     (16px)
--space-5:  1.25rem  (20px)
--space-6:  1.5rem   (24px)
--space-8:  2rem     (32px)
--space-10: 2.5rem   (40px)
--space-12: 3rem     (48px)
--space-16: 4rem     (64px)
--space-20: 5rem     (80px)
```

**Proporção:** 1.25x (base 4px incremental)

### Uso em Componentes

| Componente | Padding | Gap | Aplicação |
|-----------|---------|-----|-----------|
| KPI card (preview) | `var(--space-6)` | — | 24px interno |
| Button | `var(--space-2) var(--space-4)` | — | 8px vertical, 16px horizontal |
| Monit grid | `gap: var(--space-4)` | `var(--space-4)` | 16px entre cards |
| Sidebar | `var(--space-6) var(--space-4)` | — | 24px top/bottom, 16px left/right |

**Problema Detectado:** O sistema legado (estilo.css) usa padding/margin ad-hoc sem escala modular, criando inconsistências visuais.

---

## 4. RAIOS (Border Radius)

```css
--radius-sm: 4px      — Small inputs, badges
--radius-md: 8px      — Cards, buttons médios
--radius-lg: 14px     — Large cards, containers principais
--radius-xl: 20px     — KPI cards, grandes elementos
```

---

## 5. SOMBRAS

```css
--shadow-sm: 0 1px 2px rgba(75, 56, 30, 0.06);
--shadow-md: 0 4px 14px rgba(75, 56, 30, 0.08), 0 1px 3px rgba(75, 56, 30, 0.04);
--shadow-lg: 0 18px 40px rgba(75, 56, 30, 0.1);
```

**Nota:** Sombras usam cor quente (rgb 75, 56, 30 = marrom) em vez de preto puro, mantendo harmonia com paleta de papel.

---

## 6. COMPONENTES — PADRÕES DE USO

### Botões

#### Classe `.btn` (Padrão/Secundário)
```html
<a class="btn" href="...">Atualizar</a>
```
- **Background:** `var(--paper-card)` → `#faf6ea`
- **Texto:** `var(--ink-secondary)` → `#4a423a`
- **Borda:** `1px solid var(--line-default)` → `#d8cdb2`
- **Hover:** Background `var(--paper-elevated)` + borda `var(--line-strong)`
- **Padding:** `var(--space-2) var(--space-4)` (8px 16px)
- **Border-radius:** `var(--radius-md)` (8px)
- **Tamanho font:** `var(--text-sm)` (13px)

#### Classe `.btn-primary` (Principal/CTA)
```html
<a class="btn btn-primary" href="...">Gestão de coletores</a>
```
- **Background:** `var(--tronik)` → `#1a5d3a`
- **Texto:** `var(--paper-elevated)` → `#fffdf7`
- **Borda:** `1px solid var(--tronik)`
- **Hover:** Background `var(--tronik-hover)` → `#134428`
- **Mesmo padding/tamanho que `.btn`**

#### Variações Semânticas
- `.btn-danger` / `.btn-destructive`: `--signal-critical` (#9b2a1f) + soft background
- `.btn-ghost`: Background transparent, border apenas
- `.btn-compact`: Versão menor para headers (padding reduzido)

**Problema Detectado em index.html/estilo.css:**
- Botões usam `--color-primary: #27ae60` (verde diferente)
- Classe `.btn-atualizar`, `.btn-exportar` com estilos hardcoded
- Não seguem padrão de `.btn` + `.btn-primary`

### Cards / Containers

#### Classe `.coletor-card` (Card de Coletor em Monitoramento)
```html
<article class="coletor-card ok/warn/crit">
  <!-- conteúdo -->
</article>
```

**Estilos:**
- **Background:** `var(--paper-card)` → `#faf6ea`
- **Borda:** `1px solid var(--line-default)` → `#d8cdb2`
- **Border-radius:** `var(--radius-lg)` → 14px
- **Padding:** `var(--space-5)` → 20px
- **Hover:** Background `var(--paper-elevated)` + sombra `var(--shadow-md)` + transform Y-1px
- **Barra esquerda decorativa:** `3px solid` com cor de status (verde/âmbar/vermelho)

**Variações de Status:**
```css
.coletor-card.ok::before    { background: var(--signal-ok); }       /* verde #1a5d3a */
.coletor-card.warn::before  { background: var(--signal-warn); }     /* âmbar #b0661e */
.coletor-card.crit::before  { background: var(--signal-critical); } /* vermelho #9b2a1f */
```

#### Classe `.badge` (Badges de Status)
```html
<span class="badge ok/warn/crit/neutral">Normal</span>
```

**Estilos:**
- **Tamanho font:** 10px, peso 600, UPPERCASE
- **Padding:** 3px 8px
- **Border-radius:** 20px (pill)

**Variações:**
```css
.badge.ok       { background: #d8e6d8; color: #1a5d3a; }
.badge.warn     { background: #f3e4cc; color: #b0661e; }
.badge.crit     { background: #f0d6cc; color: #9b2a1f; }
.badge.neutral  { background: #ddd3bd; color: #6b6254; }
```

#### Classe `.panel-card` (Side Panel Cards)
```html
<div class="panel-card">
  <div class="panel-head">
    <h3>Coletas recentes</h3>
  </div>
  <!-- conteúdo -->
</div>
```

**Estilos:**
- **Background:** `var(--paper-card)` → `#faf6ea`
- **Borda:** `1px solid var(--line-default)`
- **Border-radius:** `var(--radius-lg)`
- **Padding:** Varia, mas mínimo `var(--space-4)`
- **Box-shadow:** `var(--shadow-sm)` (leve)

### KPIs / Indicadores

#### Classe `.kpi` (KPI Row em Monitoramento)
```html
<div class="kpi">
  <div class="kpi-label">Total de coletores</div>
  <div class="kpi-value">{{ total }}</div>
  <div class="kpi-delta"><strong>N</strong> em nível crítico</div>
</div>
```

**Grid:** `grid-template-columns: repeat(4, 1fr); gap: var(--space-5);`

**Estilos Internos:**
- `.kpi-label`: Montserrat 11px, UPPERCASE, `--ink-tertiary`, letter-spacing 0.1em
- `.kpi-value`: Montserrat 3rem (48px), peso 500, `--ink-primary`
- `.kpi-delta`: `--text-xs`, color `--ink-tertiary`, `<strong>` em `--tronik` (ou `--signal-warn` se warn)

**Card Wrapper:**
- **Background:** `var(--paper-card)`
- **Borda:** `1px solid var(--line-default)`
- **Border-radius:** `var(--radius-lg)`
- **Padding:** `var(--space-6)`

#### Classe `.hub-kpi` (KPI Strip em Home)
```html
<article class="hub-kpi hub-kpi--warn">
  <span class="hub-kpi-label">Alerta ≥ 80%</span>
  <strong class="hub-kpi-value">N</strong>
  <span class="hub-kpi-meta">X críticos</span>
</article>
```

**Grid:** Horizontal, variável por página

**Variações:**
- `.hub-kpi--warn`: Indicador visual diferente (possivelmente borda ou fundo destacado)
- `.hub-kpi--ml`: Indicador para ML (badge "ML" adjacente)

### Inputs e Formulários

#### Classe `.filter-input`
```html
<input type="text" class="filter-input" placeholder="Buscar...">
```

**Estilos:**
- **Background:** `var(--paper-sunk)` → `#e8dfc9`
- **Borda:** `1px solid transparent` → `var(--tronik)` on focus
- **Border-radius:** `var(--radius-md)` (8px)
- **Padding:** `var(--space-2) var(--space-4)` (8px 16px)
- **Font-size:** `var(--text-sm)` (13px)
- **Placeholder color:** `var(--ink-muted)` → `#b5a78f`
- **Focus:** Outline none, background `var(--paper-elevated)`, border `var(--tronik)`

#### Classe `.filter-chip`
```html
<button type="submit" name="nivel" value="todos" class="filter-chip active">Todos</button>
```

**Estilos:**
- **Background:** `var(--paper-sunk)` → `var(--tronik)` (active)
- **Color:** `var(--ink-secondary)` → `var(--paper-elevated)` (active)
- **Borda:** `1px solid transparent` → `var(--tronik)` (active)
- **Border-radius:** `var(--radius-md)` (8px)
- **Padding:** `var(--space-2) var(--space-3)` (8px 12px)
- **Font-size:** `var(--text-xs)` (12px)
- **Font-weight:** 500

### Alerts e Notificações

#### Classe `.alert-card` (Alert Destaque em Monitoramento)
```html
<div class="alert-card">
  <div class="alert-head">
    <div class="alert-icon">!</div>
    <div class="alert-title">Atenção necessária</div>
  </div>
  <p class="alert-text">...</p>
</div>
```

**Estilos:**
- **Background:** Geralmente `var(--signal-critical-soft)` ou similar
- **Borda:** Esquerda `3px solid var(--signal-critical)` ou equivalente
- **Padding:** `var(--space-5)` ou similar
- **Alert-icon:** Background `var(--signal-critical)`, cor `var(--paper-elevated)`, 32x32px

---

## 7. COMPONENTES — PROBLEMAS DETECTADOS

### Problema 1: Inconsistência de Botões entre Páginas

**Preview (monitoramento.html, home.html, etc.):**
- Usa sistema `.btn` + `.btn-primary` moderno
- Verde: `#1a5d3a` (Tronik v2)
- Padding consistente

**Legado (index.html, comercial, relatórios, etc.):**
- Usa `.btn-atualizar`, `.btn-exportar`, estilos hardcoded
- Verde: `#27ae60` (Tronik v1)
- Padding/tamanho diferentes
- Classes não padronizadas

**Impacto:** Usuários navegando entre monitoramento (preview) e comercial/relatórios veem botões com cores e tamanhos diferentes.

### Problema 2: Ausência de Consistência em Cards

**Preview:**
- `.coletor-card` com barra de status colorida esquerda
- Hover com transform + sombra
- Border-radius `var(--radius-lg)` (14px)

**Legado:**
- `.bin-card` com border simples
- Border-radius `6px` (diferente!)
- Sem barra visual de status

### Problema 3: Hierarquia Tipográfica Quebrada

**Preview:**
- H1: Montserrat 3rem (48px), weight 500
- H2: Montserrat 1.625rem (26px), weight 500

**Legado (estilo.css):**
- Nenhuma definição consistente
- Tamanhos mixtos de 14px a 24px
- Sistema de fontes genérico

### Problema 4: KPI Display Diferente

**Preview (monitoramento.html):**
```
Total de coletores
────────────────
     VALOR
────────────────
nível crítico (visual delta)
```
Espaço vertical, hierarquia clara

**Index.html:**
```
VALOR
LABEL
```
Sem espaço de hierarquia visual, sem delta secundário

---

## 8. LANDING PAGE — DIAGNÓSTICO VISUAL

### Arquivo: `templates/landing/landing.html`

**Problemas Críticos:**

1. **Paleta não alinhada ao Design System v2**
   - Usa variáveis do tokens.css, mas em contexto visual diferente
   - Gradientes e glows (orbital animations) criam inconsistência com dashboard
   - Landing page parece produto diferente da dashboard

2. **Tipografia em Landing Page (CSS preview-landing.css)**
   - `.lp-hero h1`: `font-size: clamp(44px, 7.2vw, 88px)` — fluida, bom!
   - **MAS:** `.lp-kicker` usa Roboto Mono em vez de Montserrat
   - **MAS:** Hierarquia diferente do dashboard

3. **Cores de Hover/Interactive**
   - `.lp-pill-btn:hover`: Background `--tronik-dark` (não existe em tokens!) = `var(--tronik-hover)` provavelmente
   - Cria ambiguidade: é `--tronik-dark` ou `--tronik-hover`?

4. **Navegação diferente**
   - Navbar flutuante com backdrop-filter (vidro gelado)
   - Contra-intuitiva comparado ao sidebar do dashboard

### Problemas na Landing Page (Nik Public)

Arquivo: `templates/landing/landing.html` (nikpub-page)

1. **Hero Section Visual**
   - Animações orbitais com gradient circles — muito diferente do dashboard minimalista
   - Cria expectativa de sistema visual que **não existe no dashboard**

2. **Terminal/Stream Panel**
   - `.nikpub-terminal`, `.nikpub-terminal-body`: Styling blackbox, não documentado em design system
   - Cores possivelmente hardcoded em CSS

3. **FAQ Chips**
   - `.nikpub-chip`, `.nikpub-chip.is-active`: Não segue padrão `.filter-chip` do dashboard
   - Color scheme diferente

---

## 9. RESUMO DE INCONSISTÊNCIAS POR PÁGINA

### Páginas com Design System Novo (V2) — CORRETAS

| Página | Arquivo Template | CSS | Status |
|--------|------------------|-----|--------|
| Monitoramento | `preview/monitoramento.html` | `preview.css` | ✓ Consistente |
| Home/Hub | `preview/home.html` | `preview-home.css` | ✓ Consistente |
| Gestão | `preview/gestao.html` | inline styles + `preview-home.css` | ✓ Consistente |
| Mapa | `preview/mapa.html` | `preview-mapa.css` | ✓ Consistente |
| Relatórios | `preview/relatorios.html` | `preview-relatorios.css` | ✓ Consistente |
| Parceiro | `preview/parceiro.html` | `preview-parceiro.css` | ✓ Consistente |

**Nota:** Landing page (nikpub/public) segue v2 em paleta, mas tem styling próprio para heróis/animações.

### Páginas com Sistema Legado — INCONSISTENTES

| Página | Arquivo Template | CSS | Status | Problemas |
|--------|------------------|-----|--------|-----------|
| Dashboard v1 | `index.html` | `estilo.css` | ✗ Inconsistente | Verde #27ae60, no espaçamento modular, botões hardcoded |
| Comercial | `comercial.html` | `comercial.css` | ✗ Inconsistente | Botões inconsistentes, padding ad-hoc |
| Contratos | `contratos.html` | `contratos.css` | ✗ Inconsistente | Idem |
| Mapa v1 | `mapa.html` | `mapa.css` | ✗ Inconsistente | Idem |
| Notificações | `notificacoes.html` | `notificacoes.css` | ✗ Inconsistente | Idem |
| Relatórios v1 | `relatorios.html` | `relatorios.css` | ✗ Inconsistente | Idem |
| Sobre | `sobre.html` | `sobre.css` | ✗ Inconsistente | Idem |
| CRM | `crm.html` | `crm.css` | ✗ Inconsistente | Idem |
| Configurações | `configuracoes.html` | `configuracoes.css` | ✗ Inconsistente | Idem |

**Todas as páginas legadas (não-preview) usam:**
- Verde: `#27ae60` em vez de `#1a5d3a`
- Sistema de fonts genérico, não Montserrat/Roboto
- Espaçamento não modular
- Paleta cinza fria em vez de marfim quente

---

## 10. MATRIZ DE INCONSISTÊNCIAS

### Nível 1: Crítico (Afeta Marca)

| Aspecto | Sistema V2 | Sistema Legado | Impacto |
|---------|-----------|-----------------|--------|
| **Cor Primária** | `#1a5d3a` (floresta) | `#27ae60` (moderno) | Marca não reconhecível |
| **Temperatura Visual** | QUENTE (marfim) | FRIA (cinza) | Sensação de 2 produtos diferentes |
| **Tipografia Padrão** | Montserrat + Roboto | system-ui genérico | Falta de identidade |

### Nível 2: Alto (Afeta UX)

| Aspecto | Sistema V2 | Sistema Legado | Impacto |
|---------|-----------|-----------------|--------|
| **Espaçamento** | Modular (4px base) | Ad-hoc | Inconsistência visual |
| **Border-radius** | 8px-20px | 4px-10px | Sensação de "épocas diferentes" |
| **Botões** | `.btn` padronizado | Múltiplas classes | Confusão de comportamento |

### Nível 3: Médio (Afeta Detalhes)

| Aspecto | Sistema V2 | Sistema Legado | Impacto |
|---------|-----------|-----------------|--------|
| **Sombras** | Quentes (marrom) | Cinza padrão | Sutileza visual diferente |
| **KPI Display** | Hierarquia clara | Compacto | Legibilidade diferente |
| **Badges** | Soft colors | Cores saturadas | Peso visual diferente |

---

## 11. RECOMENDAÇÕES

### A Curto Prazo (Correção Imediata)

1. **Unificar paleta de cores**
   - Atualizar `estilo.css`: trocar `#27ae60` → `#1a5d3a`
   - Atualizar `estilo.css`: trocar `#f0f2f5` → `#f4efe3`
   - Atualizar cores de warning/danger conforme tabela do Design System

2. **Refatorar botões legados**
   - Renomear `.btn-atualizar`, `.btn-exportar` → `.btn`, `.btn-primary`
   - Aplicar mesmo padding/tamanho que preview
   - Verificar hover states

3. **Unificar tipografia**
   - Adicionar `@import` de Montserrat + Roboto em `base.html`
   - Substituir `--font-family: -apple-system...` por `var(--font-body)`
   - Criar classes `.h1`, `.h2`, etc. baseadas em escala v2

### A Médio Prazo (Consolidação)

1. **Migrar todas as páginas legadas para v2**
   - Reescrever `index.html`, `comercial.html`, etc. usando template `preview/base_v2.html`
   - Mover CSS específico de página para componentes reutilizáveis
   - Testar navegação cross-page

2. **Criar biblioteca de componentes**
   - Arquivo único `_components.css` com:
     - `.btn`, `.btn-primary`, `.btn-danger`, etc.
     - `.card`, `.panel-card`, `.kpi`
     - `.badge`, `.alert-card`
     - `.filter-input`, `.filter-chip`

3. **Documentar em Storybook ou similar**
   - Criar exemplos visuais de cada componente
   - Documentar variações (small, large, disabled, loading)
   - Manter sincronizado com CSS

### A Longo Prazo (Evolução)

1. **Considerar CSS-in-JS ou Tailwind**
   - Reduzir manutenção de múltiplos arquivos CSS
   - Melhorar DX com autocompletar de tokens

2. **Revisar Landing Page**
   - Alinhar hero visual com dashboard (menos animação, mais clareza)
   - Testar navegação landing → dashboard (transição suave)

3. **Acessibilidade**
   - Testar contraste de cores (WCAG AA minimum)
   - Verificar focus states em inputs (atualmente minimal)
   - Testar navegação por teclado

---

## 12. ARQUIVOS PRINCIPAIS

### Design System Definido Em

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `estatico/css/v2/tokens.css` | Variáveis CSS principais | ✓ Atual |
| `estatico/css/v2/preview.css` | Componentes e layout | ✓ Atual |
| `estatico/css/v2/preview-home.css` | Home/Hub específico | ✓ Atual |
| `estatico/css/v2/preview-landing.css` | Landing page | ✓ Atual |

### Sistema Legado (Obsoleto)

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `estatico/css/estilo.css` | CSS principal legado | ✗ Obsoleto |
| `estatico/css/comercial.css` | Comercial específico | ✗ Obsoleto |
| `estatico/css/relatorios.css` | Relatórios específico | ✗ Obsoleto |
| `estatico/css/crm.css` | CRM específico | ✗ Obsoleto |
| (etc.) | Múltiplos CSS por página | ✗ Obsoleto |

### Templates Modernos

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `templates/preview/base_v2.html` | Base template v2 | ✓ Referência |
| `templates/preview/monitoramento.html` | Exemplo bom | ✓ Referência |
| `templates/preview/home.html` | Exemplo bom | ✓ Referência |

### Templates Legados

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `templates/base.html` | Base legada | ✗ Obsoleto |
| `templates/index.html` | Dashboard v1 | ✗ Obsoleto |
| `templates/comercial.html` | (não migrado) | ✗ Obsoleto |
| (etc.) | Múltiplos templates | ✗ Obsoleto |

---

## 13. PRÓXIMOS PASSOS

1. **Executar Correção Imediata (Nível 1 — Cores)**
   - [ ] Atualizar verde em estilo.css
   - [ ] Atualizar backgrounds em estilo.css
   - [ ] Testar transição entre preview e legado

2. **Migrar Botões (Nível 2 — UX)**
   - [ ] Refatorar `.btn-*` em estilo.css
   - [ ] Padronizar padding/tamanho
   - [ ] Testar em todas as páginas legadas

3. **Migrar Tipografia (Nível 2 — Identidade)**
   - [ ] Importar fontes em base.html
   - [ ] Criar escala tipográfica em estilo.css
   - [ ] Aplicar em headers e body

4. **Revisar Landing Page**
   - [ ] Comparar visual landing vs dashboard
   - [ ] Simplificar hero se necessário
   - [ ] Testar navegação landing → dashboard

---

**Documento gerado em 2026-05-22 · Poseidon (Designer de Sistemas)**

**Última atualização:** Leitura completa de tokens.css, preview.css, estilo.css, monitoramento.html, home.html, landing.html, index.html

**Próxima revisão:** Após implementação de Nível 1 (Cores) e Nível 2 (UX)
