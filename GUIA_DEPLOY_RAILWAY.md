# 🚂 Guia de Deploy no Railway.app - Dashboard-TRONIK

Este guia explica passo a passo como fazer o deploy do Dashboard-TRONIK no Railway.app.

---

## 📋 Pré-requisitos

1. ✅ Conta no Railway.app (gratuita disponível com $5 créditos/mês)
2. ✅ Repositório no GitHub com o código
3. ✅ Código commitado e pushado para o GitHub
4. ✅ Railway CLI instalado (opcional, mas recomendado)

---

## 🎯 Passo 1: Preparar o Repositório

### 1.1 Verificar Arquivos Necessários

Certifique-se de que os seguintes arquivos existem:

- ✅ `requirements.txt` (com gunicorn)
- ✅ `railway.json` ou `Procfile` (configuração do Railway)
- ✅ `app.py` (aplicação Flask)
- ✅ `.gitignore` (protegendo arquivos sensíveis)

### 1.2 Fazer Push para GitHub

```bash
# Verificar status
git status

# Adicionar arquivos novos
git add railway.json Procfile GUIA_DEPLOY_RAILWAY.md
git add requirements.txt  # se foi atualizado

# Commit
git commit -m "feat: adiciona configuração para deploy no Railway.app"

# Push
git push origin main
```

---

## 🚀 Passo 2: Criar Projeto no Railway

### 2.1 Acessar Railway.app

1. Acesse [https://railway.app](https://railway.app)
2. Faça login ou crie uma conta (pode usar GitHub)
3. Clique em **"New Project"**

### 2.2 Conectar Repositório

1. Selecione **"Deploy from GitHub repo"**
2. Autorize o Railway a acessar seus repositórios
3. Selecione o repositório `dashboard-Tronik`
4. Selecione a branch `main`

O Railway detectará automaticamente que é uma aplicação Python e começará o build.

---

## 💾 Passo 3: Configurar Banco de Dados PostgreSQL

### 3.1 Adicionar Serviço PostgreSQL

1. No projeto Railway, clique em **"New"** → **"Database"** → **"PostgreSQL"**
2. Railway criará automaticamente um banco PostgreSQL
3. A variável `DATABASE_URL` será preenchida automaticamente

### 3.2 Verificar DATABASE_URL

1. Vá em **"Variables"** no serviço da aplicação
2. Verifique se `DATABASE_URL` está presente
3. Se não estiver, adicione manualmente copiando do serviço PostgreSQL

**Formato da URL:**
```
postgresql://postgres:senha@host:porta/railway
```

---

## 🔐 Passo 4: Configurar Variáveis de Ambiente

No painel Railway, vá em **"Variables"** e adicione:

### Variáveis Obrigatórias

```env
SECRET_KEY=<gere-uma-chave-forte-32-caracteres>
FLASK_ENV=production
DATABASE_URL=<preenchida automaticamente pelo Railway>
CORS_ORIGINS=https://seu-projeto.railway.app
ADMIN_USERNAME=admin
ADMIN_EMAIL=seu-email@exemplo.com
ADMIN_PASSWORD=SenhaForte123!
```

**⚠️ IMPORTANTE sobre DATABASE_URL:**
- Railway preenche automaticamente quando você adiciona PostgreSQL
- Não é necessário configurar manualmente
- A URL será algo como: `postgresql://postgres:senha@containers-us-west-xxx.railway.app:5432/railway`

### Variáveis Opcionais

```env
RATELIMIT_ENABLED=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
LOG_LEVEL=INFO
AGENDAMENTO_ENABLED=false
DEBUG=false
```

### Como Gerar SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Ou use um gerador online: [https://randomkeygen.com/](https://randomkeygen.com/)

---

## 🔄 Passo 5: Migrar Dados (Se Migrando do Render)

### 5.1 Backup do Render

```bash
# Exportar banco do Render
pg_dump $DATABASE_URL_RENDER > backup_render_$(date +%Y%m%d).sql
```

### 5.2 Importar no Railway

```bash
# Importar para Railway
psql $DATABASE_URL_RAILWAY < backup_render_$(date +%Y%m%d).sql
```

**Como obter DATABASE_URL do Railway:**
1. No painel Railway, vá no serviço PostgreSQL
2. Clique em **"Connect"** → **"Postgres URL"**
3. Copie a URL completa

### 5.3 Verificar Migração

```bash
# Verificar dados migrados
psql $DATABASE_URL_RAILWAY -c "SELECT COUNT(*) FROM usuarios;"
psql $DATABASE_URL_RAILWAY -c "SELECT COUNT(*) FROM coletas;"
```

---

## 🚀 Passo 6: Fazer Deploy

### 6.1 Deploy Automático

O Railway fará deploy automaticamente quando você:
- Conectar o repositório
- Fazer push para a branch conectada

### 6.2 Verificar Deploy

Após o build, você verá:
- ✅ **Status**: Deployed
- ✅ **URL**: `https://seu-projeto.railway.app`
- ✅ **Logs**: Sem erros críticos

### 6.3 Verificar Logs

1. No painel Railway, clique em **"Deployments"**
2. Selecione o deploy mais recente
3. Clique em **"View Logs"**
4. Verifique se não há erros

---

## ✅ Passo 7: Verificar Funcionamento

### 7.1 Testar Health Check

```bash
curl https://seu-projeto.railway.app/api/configuracoes
```

Deve retornar JSON com configurações.

### 7.2 Acessar Aplicação

1. Abra no navegador: `https://seu-projeto.railway.app`
2. Deve carregar a página de login
3. Faça login com as credenciais do admin

### 7.3 Verificar Funcionalidades

- [ ] Login funcionando
- [ ] Dashboard carregando
- [ ] APIs respondendo
- [ ] Banco de dados conectado
- [ ] WebSocket funcionando (se aplicável)

---

## 🔧 Passo 8: Configurações Adicionais

### 8.1 Domínio Customizado (Opcional)

1. No painel Railway, vá em **"Settings"** → **"Domains"**
2. Clique em **"Generate Domain"** ou **"Custom Domain"**
3. Preencha o domínio (ex: `dashboard-tronik.com`)
4. **Para a porta:** 
   - **Deixe em BRANCO** ou **deixe o padrão**
   - O Railway roteia automaticamente para a porta correta
   - Não é necessário especificar porta manualmente
   - O Railway detecta automaticamente a porta via variável `PORT`
5. Se usar domínio customizado:
   - Configure DNS conforme instruções do Railway
   - Atualize `CORS_ORIGINS` com novo domínio

### 8.2 Atualizar CORS_ORIGINS

Após configurar domínio, atualize a variável:

```env
CORS_ORIGINS=https://seu-dominio.com,https://seu-projeto.railway.app
```

### 8.3 Configurar Backups (Importante!)

Railway não faz backups automáticos. Configure manualmente:

**Opção 1: Script de Backup Automático**

Crie um script que rode periodicamente:

```bash
#!/bin/bash
# backup_railway.sh

DATABASE_URL=$1
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

pg_dump $DATABASE_URL > $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql
echo "Backup criado: $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"
```

**Opção 2: Usar Railway CLI**

```bash
# Instalar Railway CLI
npm i -g @railway/cli

# Fazer backup
railway run pg_dump $DATABASE_URL > backup.sql
```

**Opção 3: Serviço de Backup Externo**

Use serviços como:
- [Backupify](https://backupify.com)
- [Automated Backups](https://www.automatedbackups.com)

---

## ⚠️ Problemas Comuns

### Problema 0: Erro `'$PORT' is not a valid port number` ⚠️ CRÍTICO

**Erro:** Railway mostra erro `'$PORT' is not a valid port number` repetidamente.

**Causa:** Railway está usando Dockerfile ao invés de NIXPACKS, e a variável PORT não está sendo expandida corretamente.

**Solução:**

1. **Configurar Builder no Railway (Recomendado):**
   - No painel Railway, vá em **Settings** → **Build**
   - Em **Builder**, selecione **NIXPACKS** (não Dockerfile)
   - Salve e faça novo deploy

2. **Ou renomear Dockerfile temporariamente:**
   ```bash
   git mv Dockerfile Dockerfile.backup
   git commit -m "fix: usar NIXPACKS ao invés de Dockerfile"
   git push
   ```

3. **Se precisar usar Dockerfile:**
   - O Dockerfile já foi corrigido para usar `sh -c` com expansão de variável
   - Certifique-se de que está usando a versão mais recente

**Ver detalhes completos em:** [`RAILWAY_TROUBLESHOOTING.md`](RAILWAY_TROUBLESHOOTING.md)

### Problema 1: Build Falha

**Erro:** `ModuleNotFoundError: No module named 'X'`

**Solução:**
- Verifique se todas as dependências estão em `requirements.txt`
- Verifique se o `requirements.txt` está na raiz do projeto
- Verifique os logs do build no Railway

### Problema 2: Aplicação Não Inicia

**Erro:** `Application failed to respond`

**Solução:**
- Verifique os logs no painel Railway
- Verifique se `SECRET_KEY` está configurada
- Verifique se `DATABASE_URL` está correta
- Verifique se o `startCommand` está correto no `railway.json` ou `Procfile`

### Problema 3: Banco de Dados Não Conecta

**Erro:** `could not connect to server`

**Solução:**
- Verifique se o serviço PostgreSQL está rodando
- Verifique se `DATABASE_URL` está correta
- Verifique se a URL usa SSL (Railway requer SSL)
- Verifique se o código está configurado para usar SSL (já está no `app.py`)

### Problema 4: WebSocket Não Funciona

**Problema:** WebSocket não conecta

**Solução:**
- Railway suporta WebSocket nativamente
- Verifique se `Flask-SocketIO` está instalado
- Verifique os logs para erros de WebSocket
- Verifique se o domínio está configurado corretamente

### Problema 5: CORS Errors

**Erro:** `Access-Control-Allow-Origin`

**Solução:**
- Configure `CORS_ORIGINS` com o domínio correto
- Exemplo: `CORS_ORIGINS=https://seu-projeto.railway.app`
- Se usar domínio customizado, adicione também

### Problema 6: Variável PORT Não Encontrada

**Erro:** `PORT environment variable not set`

**Solução:**
- Railway define `PORT` automaticamente
- Não é necessário configurar manualmente
- Se o erro persistir, verifique o `startCommand`

---

## 📊 Monitoramento

### Logs

- Acesse **"Deployments"** → **"View Logs"** no painel Railway
- Logs são atualizados em tempo real
- Úteis para debug

### Métricas

- **"Metrics"** mostra:
  - CPU usage
  - Memory usage
  - Network usage
  - Request rate

### Alertas

Configure alertas para:
- Build failures
- Service downtime
- High error rate
- Resource usage

---

## 🔄 Atualizações

Para atualizar a aplicação:

### Deploy Automático (Recomendado) ✅

1. Faça alterações no código
2. **Commit e push para GitHub:**
   ```bash
   git add .
   git commit -m "sua mensagem de commit"
   git push origin main
   ```
3. Railway detecta automaticamente o push e faz deploy
4. Acompanhe os logs no painel Railway

### Deploy Manual

- No painel Railway, clique em **"Deployments"** → **"Redeploy"** → **"Deploy latest commit"**

**Nota:** Após mudar o Builder para NIXPACKS, você pode fazer um commit vazio ou qualquer mudança para forçar um novo deploy:
```bash
git commit --allow-empty -m "trigger: forçar deploy com NIXPACKS"
git push
```

---

## 💰 Custos

### Modelo Pay-as-You-Go

Railway usa modelo baseado em uso:
- **$5 créditos grátis/mês** (plano Hobby)
- **Uso típico:** ~$10-20/mês (depende do uso)
- **PostgreSQL:** Incluído no uso

### Estimativa de Custos

Para uma aplicação Flask típica:
- **Aplicação web:** ~$5-10/mês
- **PostgreSQL:** ~$5-10/mês
- **Total estimado:** ~$10-20/mês

**Dica:** Monitore o uso nos primeiros meses para estimar custos reais.

### Comparação com Render

- **Render Starter:** $7/mês (fixo) + PostgreSQL $7/mês = **$14/mês**
- **Railway:** ~$10-20/mês (variável, baseado em uso)

---

## 🔐 Segurança

### Variáveis de Ambiente

- Use **"Secrets"** no Railway para variáveis sensíveis
- Nunca commite secrets no código
- Use `.env` apenas para desenvolvimento local

### SSL/HTTPS

- Railway fornece HTTPS automaticamente
- Certificados SSL são gerenciados automaticamente
- Não é necessário configurar manualmente

### Backups

- Configure backups regulares (Railway não faz automaticamente)
- Teste restauração de backups periodicamente
- Mantenha backups em local seguro (não no Railway)

---

## 📝 Checklist Final

Antes de considerar o deploy completo:

- [ ] Código commitado e pushado
- [ ] `railway.json` ou `Procfile` criado
- [ ] `requirements.txt` atualizado (com gunicorn e psycopg)
- [ ] Variáveis de ambiente configuradas
- [ ] SECRET_KEY gerada e configurada
- [ ] **PostgreSQL criado e vinculado ao serviço**
- [ ] DATABASE_URL preenchida automaticamente pelo Railway
- [ ] Dados migrados (se migrando do Render)
- [ ] Build bem-sucedido
- [ ] Aplicação acessível
- [ ] Login funcionando
- [ ] Health check respondendo
- [ ] Logs sem erros críticos
- [ ] Dados persistindo corretamente (teste criar/editar algo)
- [ ] Sistema de backups configurado
- [ ] Domínio customizado configurado (se necessário)
- [ ] CORS_ORIGINS atualizado com domínio correto

---

## 🎉 Pronto!

Seu Dashboard-TRONIK está no ar no Railway! 🚂

**URL:** `https://seu-projeto.railway.app`

---

## 📚 Recursos Adicionais

- [Documentação Railway](https://docs.railway.app)
- [Railway CLI](https://docs.railway.app/develop/cli)
- [Guia de Migração do Render](https://docs.railway.com/migration/migrate-from-render)
- [Análise Completa de Migração](./ANALISE_MIGRACAO_RENDER_RAILWAY.md)

---

**Última Atualização:** 2025-01-XX  
**Versão:** 1.0


