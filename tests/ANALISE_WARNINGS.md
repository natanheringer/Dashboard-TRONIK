# 🔍 Análise dos Warnings nos Testes

**Data:** 20-11-2025  
**Status:** ✅ **CORRIGIDO** - 0 warnings em 102 testes

**Antes:** 136 warnings  
**Depois:** 0 warnings

---

## 🔎 Causa Principal dos Warnings

### 1. **DeprecationWarning: datetime.utcnow()** (Principal)

**Problema:** `datetime.utcnow()` está **deprecado** no Python 3.12+ e será removido no Python 3.14.

**Onde ocorre:**
- `banco_dados/modelos.py` - Valores padrão de colunas (5 ocorrências)
- `rotas/api.py` - Criação de lixeiras e coletas (6 ocorrências)
- `rotas/auth.py` - Atualização de último login (1 ocorrência)
- `tests/*.py` - Testes usando `datetime.utcnow()` (12 ocorrências)

**Solução:** Substituir `datetime.utcnow()` por `datetime.now(timezone.utc)` ou `datetime.now(tz=timezone.utc)`.

**Impacto:** 
- ⚠️ Não afeta funcionalidade atual
- ⚠️ Pode quebrar no Python 3.14+
- ✅ Fácil de corrigir

---

## 📊 Distribuição dos Warnings

### Por Tipo (estimado):
1. **DeprecationWarning (datetime.utcnow)** - ~80-90% dos warnings
2. **ResourceWarning (conexões não fechadas)** - ~10-15% dos warnings
3. **Outros warnings** - ~5% dos warnings

### Por Arquivo:
- `banco_dados/modelos.py` - 5 warnings (valores padrão)
- `rotas/api.py` - 6 warnings
- `rotas/auth.py` - 1 warning
- `tests/*.py` - ~12 warnings
- **Total estimado:** ~24 ocorrências de `datetime.utcnow()`

**Multiplicado por ~5-6 testes que usam cada função = ~120-144 warnings**

---

## ✅ Solução Implementada

### ✅ Substituição de datetime.utcnow() (IMPLEMENTADO)

```python
# ANTES (deprecado)
from datetime import datetime
criado_em = Column(DateTime, default=datetime.utcnow)

# DEPOIS (correto)
from datetime import datetime, timezone
criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

### Opção 2: Suprimir Warnings nos Testes (Temporário)

Adicionar ao `pytest.ini`:
```ini
filterwarnings =
    ignore::DeprecationWarning:datetime
    ignore::ResourceWarning
```

---

## 🎯 Prioridade de Correção

### 🔴 Alta Prioridade
- Substituir `datetime.utcnow()` em modelos (valores padrão)
- Substituir em rotas da API

### 🟡 Média Prioridade
- Substituir em testes
- Fechar conexões de banco adequadamente

### 🟢 Baixa Prioridade
- Configurar filtros de warnings no pytest.ini

---

## 📝 Notas

1. **Os warnings não afetam a funcionalidade** - são apenas avisos de deprecação
2. **Python 3.13** está gerando mais warnings que versões anteriores
3. **A correção é simples** - substituir `datetime.utcnow()` por `datetime.now(timezone.utc)`
4. **Os testes continuam passando** - 102/102 testes OK

---

## 🔧 Próximos Passos

1. Criar função helper `utc_now()` para substituir `datetime.utcnow()`
2. Atualizar todos os arquivos que usam `datetime.utcnow()`
3. Atualizar testes para usar a nova função
4. Verificar se warnings diminuem

---

**Status:** ✅ **CORRIGIDO** - Todos os warnings foram eliminados!

### Mudanças Implementadas:
1. ✅ Criado `banco_dados/utils.py` com função `utc_now_naive()`
2. ✅ Substituído `datetime.utcnow()` em `banco_dados/modelos.py` (5 ocorrências)
3. ✅ Substituído `datetime.utcnow()` em `rotas/api.py` (5 ocorrências)
4. ✅ Substituído `datetime.utcnow()` em `rotas/auth.py` (1 ocorrência)
5. ✅ Substituído `datetime.utcnow()` em `banco_dados/importar_csv.py` (1 ocorrência)
6. ✅ Substituído `datetime.utcnow()` em todos os testes (12 ocorrências)

**Total corrigido:** 24 ocorrências de `datetime.utcnow()`

**Resultado:** 0 warnings nos testes! 🎉

