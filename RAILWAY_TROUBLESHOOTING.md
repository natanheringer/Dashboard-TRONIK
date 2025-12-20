# 🔧 Troubleshooting Railway - Dashboard-TRONIK

## ❌ Erro: `'$PORT' is not a valid port number`

### Problema

O Railway está usando o `Dockerfile` ao invés do `railway.json` ou `Procfile`, e o Dockerfile não está configurado corretamente para usar a variável `PORT`.

### Solução 1: Usar NIXPACKS (Recomendado) ✅

O Railway está priorizando o Dockerfile. Para forçar o uso do NIXPACKS:

1. **No painel Railway:**
   - Vá em **Settings** → **Build**
   - Em **Builder**, selecione **NIXPACKS**
   - Salve as configurações
   - Faça um novo deploy

2. **Ou renomear Dockerfile temporariamente:**
   ```bash
   git mv Dockerfile Dockerfile.backup
   git commit -m "fix: renomear Dockerfile para usar NIXPACKS"
   git push
   ```

3. **Após deploy funcionar, pode restaurar:**
   ```bash
   git mv Dockerfile.backup Dockerfile
   git commit -m "restore: restaurar Dockerfile"
   git push
   ```

### Solução 2: Corrigir Dockerfile ✅

O Dockerfile já foi corrigido para usar gunicorn com `$PORT`. Se ainda houver problemas:

**Verificar se o Dockerfile está correto:**

```dockerfile
# Deve usar shell form (não JSON form) para expandir $PORT
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - app:app
```

**Se ainda não funcionar, usar forma explícita:**

```dockerfile
# Usar sh -c para garantir expansão de variável
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - app:app"]
```

### Solução 3: Usar Procfile ✅

Criar/verificar `Procfile` na raiz:

```
web: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - app:app
```

O Railway deve detectar automaticamente o Procfile.

---

## ❌ Health Check Falhando

### Problema

Health check retorna "service unavailable" mesmo após vários minutos.

### Soluções

1. **Verificar se a aplicação está iniciando:**
   - Ver logs no Railway
   - Verificar se há erros de importação
   - Verificar se `DATABASE_URL` está configurada

2. **Aumentar timeout do health check:**
   - No `railway.json`, aumentar `healthcheckTimeout`:
   ```json
   {
     "deploy": {
       "healthcheckTimeout": 300
     }
   }
   ```

3. **Verificar endpoint de health check:**
   - O endpoint `/api/configuracoes` deve retornar 200 OK
   - Testar localmente: `curl http://localhost:5000/api/configuracoes`

4. **Verificar variável PORT:**
   - No Railway, verificar se `PORT` está sendo definida automaticamente
   - Não é necessário configurar manualmente

---

## ❌ Build Falha

### Problema

Build falha com erros de dependências ou comandos.

### Soluções

1. **Verificar `requirements.txt`:**
   ```bash
   # Testar localmente
   pip install -r requirements.txt
   ```

2. **Verificar Python version:**
   - Railway detecta automaticamente via `runtime.txt`
   - Ou especificar em `railway.json`:
   ```json
   {
     "build": {
       "builder": "NIXPACKS",
       "buildCommand": "pip install -r requirements.txt"
     }
   }
   ```

3. **Limpar cache do Railway:**
   - No painel, Settings → Build → Clear Build Cache
   - Fazer novo deploy

---

## ❌ Banco de Dados Não Conecta

### Problema

Aplicação não consegue conectar ao PostgreSQL.

### Soluções

1. **Verificar `DATABASE_URL`:**
   - No Railway, verificar se PostgreSQL está criado
   - Verificar se `DATABASE_URL` está preenchida automaticamente
   - Se não estiver, copiar manualmente do serviço PostgreSQL

2. **Verificar SSL:**
   - Railway requer SSL para PostgreSQL
   - O código já está configurado para usar SSL automaticamente
   - Verificar logs para erros de SSL

3. **Testar conexão manualmente:**
   ```bash
   # Usar Railway CLI
   railway run psql $DATABASE_URL -c "SELECT version();"
   ```

---

## ✅ Checklist de Verificação

Antes de reportar problemas, verificar:

- [ ] `railway.json` existe e está correto
- [ ] `Procfile` existe (alternativa)
- [ ] `Dockerfile` usa gunicorn com `$PORT` (se usando Dockerfile)
- [ ] Builder configurado como NIXPACKS (se não usando Dockerfile)
- [ ] Variável `PORT` não está configurada manualmente (Railway define automaticamente)
- [ ] `DATABASE_URL` está configurada
- [ ] `SECRET_KEY` está configurada
- [ ] Logs não mostram erros críticos
- [ ] Health check endpoint responde localmente

---

## 📚 Recursos Adicionais

- [Documentação Railway](https://docs.railway.app)
- [Railway Troubleshooting](https://docs.railway.app/help/troubleshooting)
- [Railway Build Configuration](https://docs.railway.app/develop/config)

---

**Última Atualização:** 2025-01-XX

