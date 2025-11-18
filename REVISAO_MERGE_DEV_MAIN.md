# 🔍 Revisão para Merge: dev-natan → main

**Data:** 18-11-2025  
**Branch Origem:** `dev-natan`  
**Branch Destino:** `main`

---

## ✅ ARQUIVOS QUE DEVEM IR PARA MAIN

### 🔧 Código Fonte (CRÍTICO - Devem ir)

#### Backend
- ✅ `rotas/api.py` - Correção cálculo combustível + filtro de data no histórico
- ✅ `banco_dados/modelos.py` - Modelos atualizados (já estava na main)
- ✅ `banco_dados/seguranca.py` - Validações (já estava na main)
- ✅ `banco_dados/inicializar.py` - Inicialização (já estava na main)
- ✅ `banco_dados/seed_tipos.py` - Seed de tipos e parceiros (já estava na main)
- ✅ `banco_dados/importar_csv.py` - Importação CSV (já estava na main)
- ✅ `app.py` - Configurações principais (já estava na main)

#### Frontend - JavaScript
- ✅ `estatico/js/api.js` - Função `obterHistorico()` com filtro de data
- ✅ `estatico/js/dashboard.js` - Filtro de data, ordenação, verificações de elementos
- ✅ `estatico/js/relatorios.js` - Correção cálculo combustível
- ✅ `estatico/js/configuracoes.js` - **NOVO** - JavaScript da página de configurações

#### Frontend - CSS
- ✅ `estatico/css/estilo.css` - Estilos de ordenação (setas ↑↓)

#### Templates
- ✅ `templates/index.html` - Estrutura do dashboard (já estava na main)
- ✅ `templates/relatorios.html` - Layout reorganizado (já estava na main)
- ✅ `templates/configuracoes.html` - Script inline removido, usando arquivo externo
- ✅ `templates/base.html` - Template base (já estava na main)

---

## ⚠️ ARQUIVOS DE DOCUMENTAÇÃO (Decisão necessária)

### 📄 Documentação Técnica (Recomendado incluir)
- ✅ `MUDANÇAS_SESSAO_2025.md` - **NOVO** - Documentação completa das mudanças
- ✅ `ESTADO_ATUAL_PROJETO.md` - **ATUALIZADO** - Estado atual do projeto
- ⚠️ `MODELO_BANCO_DADOS.md` - Documentação do modelo (já estava?)
- ⚠️ `ANALISE_INTEGRACAO_CSV.md` - Análise do CSV (já estava?)
- ⚠️ `PLANO_REFATORACAO_COMPLETA.md` - Plano de refatoração (já estava?)

### 📄 Documentação que pode não ir (temporária/análise)
- ❓ `ANALISE_MODELO_ATUALIZADO.md` - Análise temporária?
- ❓ `RESUMO_MELHORIAS_MODELO.md` - Resumo temporário?
- ❓ `RESUMO_ANALISE_CSV.md` - Resumo temporário?

**Recomendação:** Manter apenas documentação final e útil. Remover análises temporárias.

---

## ❌ ARQUIVOS QUE NÃO DEVEM IR PARA MAIN

### 🗑️ Arquivos Temporários/Locais
- ❌ `BaseTronik v2 (1)(FatoColetas) (1).csv` - **Dados sensíveis/reais** - NÃO deve ir
- ❌ `tronik.db` - Banco de dados local (já está no .gitignore)
- ❌ `*.db` - Qualquer banco de dados local
- ❌ `.env` - Variáveis de ambiente (já está no .gitignore)
- ❌ Arquivos de backup temporários

### 📝 Arquivos de Análise Temporária (se existirem)
- ❌ Scripts de análise temporária (se houver)
- ❌ Arquivos de debug/teste temporários

---

## 📋 CHECKLIST PRÉ-MERGE

### Antes do Merge
- [ ] Verificar que não há dados sensíveis no código
- [ ] Verificar que `.env` não está commitado
- [ ] Verificar que `*.db` não está commitado
- [ ] Verificar que CSV com dados reais não está commitado
- [ ] Revisar documentação temporária (remover se necessário)
- [ ] Testar localmente que tudo funciona
- [ ] Verificar que não há erros de lint

### Arquivos a Remover do Commit (se estiverem)
```bash
# Se o CSV estiver no staging:
git reset HEAD "BaseTronik v2 (1)(FatoColetas) (1).csv"

# Se arquivos temporários estiverem:
git reset HEAD <arquivo_temporario>
```

### Arquivos a Adicionar ao .gitignore (se necessário)
```gitignore
# Dados reais (se não estiver)
*.csv
BaseTronik*.csv

# Documentação temporária (opcional)
ANALISE_*.md
RESUMO_*.md
```

---

## 🎯 RESUMO DO QUE DEVE IR

### Código (100% deve ir)
1. ✅ Todas as correções de cálculo financeiro
2. ✅ Novas funcionalidades (filtro, ordenação)
3. ✅ Correções de CSP
4. ✅ Novo arquivo `configuracoes.js`
5. ✅ Melhorias de CSS

### Documentação (Decisão)
- ✅ `MUDANÇAS_SESSAO_2025.md` - **SIM** (documentação útil)
- ✅ `ESTADO_ATUAL_PROJETO.md` - **SIM** (atualizado)
- ❓ Documentação de análise temporária - **NÃO** (remover)

### Dados (NÃO deve ir)
- ❌ CSV com dados reais
- ❌ Banco de dados local
- ❌ Arquivos `.env`

---

## 📝 COMANDOS SUGERIDOS PARA PREPARAR O MERGE

```bash
# 1. Verificar status
git status

# 2. Verificar diferenças com main
git diff main...dev-natan --name-only

# 3. Remover arquivos que não devem ir (se estiverem no staging)
git reset HEAD "BaseTronik v2 (1)(FatoColetas) (1).csv"
git reset HEAD "*.db"

# 4. Verificar arquivos que serão commitados
git diff --cached --name-only

# 5. Se tudo estiver OK, fazer commit (se ainda não fez)
git commit -m "feat: correções financeiras, filtro de data e ordenação no histórico

- Corrigido cálculo de custo de combustível (agora usa consumo real)
- Adicionado filtro por data no histórico do dashboard
- Adicionada ordenação por colunas na tabela de histórico
- Corrigidos problemas de CSP (scripts inline movidos para arquivos externos)
- Criado configuracoes.js separado
- Melhorias de UX com indicadores visuais de ordenação"

# 6. Push para dev-natan
git push origin dev-natan

# 7. Depois fazer merge na main (via PR ou direto)
```

---

## ⚠️ ATENÇÃO ESPECIAL

### Arquivos Sensíveis
- **CSV com dados reais** - NÃO deve ir para o repositório público
- Se já foi commitado acidentalmente, usar `git filter-branch` ou `git filter-repo` para remover do histórico

### Conflitos Potenciais
- Verificar se `main` tem mudanças que conflitam com `dev-natan`
- Fazer `git fetch origin main` antes do merge
- Resolver conflitos se houver

---

## ✅ VALIDAÇÃO FINAL

Antes de fazer o merge, confirmar:

1. ✅ Código funciona localmente
2. ✅ Sem erros de lint
3. ✅ Sem dados sensíveis no commit
4. ✅ Documentação útil incluída
5. ✅ Documentação temporária removida
6. ✅ CSV não está no commit
7. ✅ Banco de dados não está no commit
8. ✅ `.env` não está no commit

---

**Documento criado em:** 18-11-2025

