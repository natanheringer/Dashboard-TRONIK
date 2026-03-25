# 🐘 PostgreSQL - Dashboard-TRONIK

Este documento explica como usar PostgreSQL no Dashboard-TRONIK.

---

## 📋 Por que PostgreSQL?

- ✅ **Persistência garantida**: Dados não são perdidos
- ✅ **Melhor para produção**: Suporta múltiplas conexões simultâneas
- ✅ **Performance**: Melhor que SQLite em alta carga
- ✅ **Escalabilidade**: Suporta crescimento do banco de dados
- ✅ **Recursos avançados**: Transações, triggers, views, etc.

---

## 🚀 Configuração Rápida

### 1. Instalar Driver PostgreSQL

O driver já está no `requirements.txt`:
```bash
pip install psycopg2-binary
```

### 2. Configurar DATABASE_URL

**SQLite (desenvolvimento):**
```env
DATABASE_URL=sqlite:///tronik.db
```

**PostgreSQL (produção):**
```env
DATABASE_URL=postgresql://usuario:senha@host:porta/database
```

**Exemplo Render.com:**
```env
DATABASE_URL=postgresql://tronik_user:senha@dpg-xxx.oregon-postgres.render.com/tronik
```

### 3. O Código Já Funciona!

O SQLAlchemy detecta automaticamente o tipo de banco pela URL. Não precisa mudar código!

---

## 🔄 Migração SQLite → PostgreSQL

### Opção 1: Script Automático (Recomendado)

```bash
python banco_dados/migrar_sqlite_para_postgres.py \
  --sqlite sqlite:///tronik.db \
  --postgres "postgresql://user:pass@host:port/db" \
  --backup
```

O script:
- ✅ Faz backup do SQLite (se usar `--backup`)
- ✅ Migra todas as tabelas automaticamente
- ✅ Preserva todos os dados
- ✅ Mostra progresso detalhado

### Opção 2: Manual

1. Exportar dados do SQLite:
   ```bash
   sqlite3 tronik.db .dump > backup.sql
   ```

2. Importar no PostgreSQL:
   ```bash
   psql -h host -U usuario -d database < backup.sql
   ```

---

## 🧪 Testar Conexão PostgreSQL

```python
from sqlalchemy import create_engine, text

# Testar conexão
engine = create_engine("postgresql://user:pass@host:port/db")
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    print(result.fetchone())
```

---

## 📊 Verificar Dados Migrados

```python
from sqlalchemy import create_engine, inspect

engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

# Listar tabelas
tabelas = inspector.get_table_names()
print(f"Tabelas: {tabelas}")

# Contar registros
for tabela in tabelas:
    count = engine.execute(f"SELECT COUNT(*) FROM {tabela}").scalar()
    print(f"{tabela}: {count} registros")
```

---

## ⚠️ Diferenças SQLite vs PostgreSQL

### Tipos de Dados

SQLAlchemy mapeia automaticamente, mas atenção:

- **BOOLEAN**: SQLite usa INTEGER (0/1), PostgreSQL tem BOOLEAN nativo
- **DATETIME**: Ambos suportam, mas formatos podem variar
- **TEXT**: Ambos suportam
- **INTEGER**: Ambos suportam

### Queries Específicas

Se você usar queries SQL diretas, pode precisar ajustar:

**SQLite:**
```sql
SELECT * FROM tabela LIMIT 10 OFFSET 20;
```

**PostgreSQL:**
```sql
SELECT * FROM tabela LIMIT 10 OFFSET 20;  -- Mesmo!
```

Ambos usam a mesma sintaxe para LIMIT/OFFSET.

---

## 🔧 Troubleshooting

### Erro: "psycopg2 not found"

**Solução:**
```bash
pip install psycopg2-binary
```

### Erro: "Connection refused"

**Solução:**
- Verifique se o PostgreSQL está rodando
- Verifique host, porta, usuário e senha
- Verifique firewall/security groups

### Erro: "Database does not exist"

**Solução:**
```sql
CREATE DATABASE tronik;
```

### Erro: "Permission denied"

**Solução:**
- Verifique se o usuário tem permissões
- No Render.com, o usuário já tem permissões necessárias

---

## 📝 Exemplo Completo

```python
from sqlalchemy import create_engine
from banco_dados.modelos import Base

# PostgreSQL no Render.com
DATABASE_URL = "postgresql://user:pass@host:port/db"

# Criar engine
engine = create_engine(DATABASE_URL)

# Criar tabelas
Base.metadata.create_all(engine)

# Pronto! O código funciona igual ao SQLite
```

---

## 🎯 Próximos Passos

1. ✅ Configurar PostgreSQL no Render.com
2. ✅ Atualizar DATABASE_URL
3. ✅ Migrar dados (se necessário)
4. ✅ Testar aplicação
5. ✅ Verificar persistência dos dados

---

**Última Atualização:** 24 de Novembro de 2025

