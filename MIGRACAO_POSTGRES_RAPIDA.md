# ⚡ Migração PostgreSQL: Guia Rápido

## 🎯 Resumo em 3 Passos

### 1️⃣ Obter URLs

**Render:**
- Painel Render → PostgreSQL → **Connections** → **External Database URL**
- Copie a URL completa

**Railway:**
- Painel Railway → PostgreSQL → **Connect** → **Postgres URL**
- Copie a URL completa

### 2️⃣ Executar Script

```bash
cd scripts
./migrar_para_railway.sh \
  "postgresql://user:pass@render-host/db" \
  "postgresql://user:pass@railway-host/db"
```

### 3️⃣ Verificar

O script faz tudo automaticamente:
- ✅ Backup do Render
- ✅ Import no Railway
- ✅ Verificação de dados

---

## 📝 Exemplo Prático

```bash
# 1. Ir para pasta do script
cd /home/natanheringer/Documents/GitHub/dashboard-Tronik/scripts

# 2. Executar migração (substitua pelas suas URLs reais)
./migrar_para_railway.sh \
  "postgresql://tronik_user:senha@dpg-xxxxx.oregon-postgres.render.com:5432/tronik" \
  "postgresql://postgres:senha@containers-us-west-xxx.railway.app:5432/railway"
```

---

## ⚠️ Se Não Tiver pg_dump Instalado

### Linux
```bash
sudo apt-get install postgresql-client
```

### macOS
```bash
brew install postgresql
```

---

## 📚 Guia Completo

Para mais detalhes, consulte: [`GUIA_MIGRACAO_POSTGRES.md`](GUIA_MIGRACAO_POSTGRES.md)

