# 🚀 Guia de Deploy no Render.com - Dashboard-TRONIK

Este guia explica passo a passo como fazer o deploy do Dashboard-TRONIK no Render.com.

---

## 📋 Pré-requisitos

1. ✅ Conta no Render.com (gratuita disponível)
2. ✅ Repositório no GitHub com o código
3. ✅ Código commitado e pushado para o GitHub

---

## 🎯 Passo 1: Preparar o Repositório

### 1.1 Verificar Arquivos Necessários

Certifique-se de que os seguintes arquivos existem:

- ✅ `requirements.txt` (com gunicorn)
- ✅ `render.yaml` (configuração do Render)
- ✅ `app.py` (aplicação Flask)
- ✅ `.gitignore` (protegendo arquivos sensíveis)

### 1.2 Fazer Push para GitHub

```bash
# Verificar status
git status

# Adicionar arquivos novos
git add render.yaml GUIA_DEPLOY_RENDER.md
git add requirements.txt  # se foi atualizado

# Commit
git commit -m "feat: adiciona configuração para deploy no Render.com"

# Push
git push origin main
```

---

## 🚀 Passo 2: Criar Serviço no Render.com

### 2.1 Acessar Render.com

1. Acesse [https://dashboard.render.com](https://dashboard.render.com)
2. Faça login ou crie uma conta
3. Clique em **"New +"** → **"Web Service"**

### 2.2 Conectar Repositório

1. Selecione **"Connect GitHub"** ou **"Connect GitLab"**
2. Autorize o Render a acessar seus repositórios
3. Selecione o repositório `dashboard-Tronik`
4. Selecione a branch `main`

### 2.3 Configurar Serviço

**Nome do Serviço:**
```
dashboard-tronik
```

**Ambiente:**
```
Python 3
```

**Branch:**
```
main
```

**Root Directory:**
```
(Deixe em branco - raiz do projeto)
```

**Build Command:**
```
pip install -r requirements.txt
```

**Start Command:**
```
gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - app:app
```

**Plan:**
- **Free**: Para testes (pode hibernar após 15min de inatividade)
- **Starter**: $7/mês (recomendado para produção)
- **Standard**: $25/mês (mais recursos)

---

## 🔐 Passo 3: Configurar Variáveis de Ambiente

No painel do Render, vá em **"Environment"** e adicione:

### Variáveis Obrigatórias

```env
SECRET_KEY=<gere-uma-chave-forte-32-caracteres>
FLASK_ENV=production
DATABASE_URL=<será preenchido automaticamente pelo Render quando você vincular o PostgreSQL>
CORS_ORIGINS=https://dashboard-tronik.onrender.com
ADMIN_USERNAME=admin
ADMIN_EMAIL=seu-email@exemplo.com
ADMIN_PASSWORD=SenhaForte123!
```

**⚠️ IMPORTANTE sobre DATABASE_URL:**
- Se você criar o PostgreSQL **antes** do serviço web, o Render preencherá automaticamente
- Se criar depois, vá em Settings → Add Database e selecione o banco
- A URL será algo como: `postgresql://tronik_user:password@dpg-xxx.oregon-postgres.render.com/tronik`

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

## 💾 Passo 4: Configurar Banco de Dados (Opcional)

### Opção 1: SQLite (Simples, mas não persistente)

O SQLite funciona, mas **os dados serão perdidos** quando o serviço reiniciar ou hibernar (plano Free).

**Configuração:**
```env
DATABASE_URL=sqlite:///tronik.db
```

### Opção 2: PostgreSQL (Recomendado para Produção)

1. No painel do Render, clique em **"New +"** → **"PostgreSQL"**
2. Configure:
   - **Name**: `tronik-db`
   - **Database**: `tronik`
   - **User**: `tronik_user`
   - **Plan**: Free ou Starter
3. Após criar, copie a **Internal Database URL**
4. No serviço web, adicione:
   ```env
   DATABASE_URL=<Internal Database URL copiada>
   ```

**Nota:** Você precisará atualizar o código para usar PostgreSQL em vez de SQLite. O SQLAlchemy suporta ambos.

---

## 🚀 Passo 5: Fazer Deploy

1. Clique em **"Create Web Service"**
2. Render começará a fazer build automaticamente
3. Acompanhe os logs em tempo real
4. Aguarde o build completar (2-5 minutos)

### Verificar Deploy

Após o build, você verá:
- ✅ **Status**: Live
- ✅ **URL**: `https://dashboard-tronik.onrender.com`

---

## ✅ Passo 6: Verificar Funcionamento

### 6.1 Testar Health Check

```bash
curl https://dashboard-tronik.onrender.com/api/configuracoes
```

Deve retornar JSON com configurações.

### 6.2 Acessar Aplicação

1. Abra no navegador: `https://dashboard-tronik.onrender.com`
2. Deve carregar a página de login
3. Faça login com as credenciais do admin

### 6.3 Verificar Logs

No painel do Render:
- Vá em **"Logs"**
- Verifique se não há erros
- Logs devem mostrar: "Aplicação iniciada com sucesso"

---

## 🔧 Passo 7: Configurações Adicionais

### 7.1 Domínio Customizado (Opcional)

1. No painel do serviço, vá em **"Settings"**
2. Role até **"Custom Domains"**
3. Adicione seu domínio
4. Configure DNS conforme instruções

### 7.2 Auto-Deploy

Por padrão, o Render faz deploy automático quando você faz push para a branch `main`.

Para desabilitar:
- Settings → **"Auto-Deploy"** → Desligar

### 7.3 Health Checks

O Render verifica automaticamente o endpoint `/api/configuracoes`.

Se quiser mudar:
- Settings → **"Health Check Path"** → `/api/configuracoes`

---

## ⚠️ Problemas Comuns

### Problema 1: Build Falha

**Erro:** `ModuleNotFoundError: No module named 'X'`

**Solução:**
- Verifique se todas as dependências estão em `requirements.txt`
- Verifique se o `requirements.txt` está na raiz do projeto

### Problema 2: Aplicação Não Inicia

**Erro:** `Application failed to respond`

**Solução:**
- Verifique os logs no painel do Render
- Verifique se `SECRET_KEY` está configurada
- Verifique se `DATABASE_URL` está correta
- Verifique se o `startCommand` está correto

### Problema 3: Banco de Dados Perdido

**Problema:** Dados desaparecem após reiniciar

**Solução:**
- ✅ Use PostgreSQL (já configurado por padrão)
- ✅ PostgreSQL no Render é persistente e não perde dados
- ⚠️ Se ainda estiver usando SQLite, migre para PostgreSQL

### Problema 4: WebSocket Não Funciona

**Problema:** WebSocket não conecta

**Solução:**
- Render.com suporta WebSocket, mas pode precisar de configuração adicional
- Verifique se `Flask-SocketIO` está instalado
- Verifique os logs para erros de WebSocket

### Problema 5: CORS Errors

**Erro:** `Access-Control-Allow-Origin`

**Solução:**
- Configure `CORS_ORIGINS` com o domínio correto
- Exemplo: `CORS_ORIGINS=https://dashboard-tronik.onrender.com`

---

## 📊 Monitoramento

### Logs

- Acesse **"Logs"** no painel do Render
- Logs são atualizados em tempo real
- Úteis para debug

### Métricas

- **"Metrics"** mostra:
  - CPU usage
  - Memory usage
  - Request rate
  - Response time

### Alertas

Configure alertas para:
- Build failures
- Service downtime
- High error rate

---

## 🔄 Atualizações

Para atualizar a aplicação:

1. Faça alterações no código
2. Commit e push para GitHub
3. Render fará deploy automático
4. Acompanhe os logs

Ou manualmente:
- No painel do Render, clique em **"Manual Deploy"** → **"Deploy latest commit"**

---

## 💰 Custos

### Plano Free

- ✅ Grátis
- ⚠️ Hiberna após 15min de inatividade
- ⚠️ Builds podem ser lentos
- ✅ Ideal para testes

### Plano Starter ($7/mês)

- ✅ Sem hibernação
- ✅ Builds mais rápidos
- ✅ Melhor performance
- ✅ Recomendado para produção

### Plano Standard ($25/mês)

- ✅ Mais recursos
- ✅ Melhor para alta carga
- ✅ Suporte prioritário

---

## 📝 Checklist Final

Antes de considerar o deploy completo:

- [ ] Código commitado e pushado
- [ ] `render.yaml` criado
- [ ] `requirements.txt` atualizado (com gunicorn e psycopg2-binary)
- [ ] Variáveis de ambiente configuradas
- [ ] SECRET_KEY gerada e configurada
- [ ] **PostgreSQL criado e vinculado ao serviço**
- [ ] DATABASE_URL preenchida automaticamente pelo Render
- [ ] Build bem-sucedido
- [ ] Aplicação acessível
- [ ] Login funcionando
- [ ] Health check respondendo
- [ ] Logs sem erros críticos
- [ ] Dados persistindo corretamente (teste criar/editar algo)

---

## 🎉 Pronto!

Seu Dashboard-TRONIK está no ar! 🚀

**URL:** `https://dashboard-tronik.onrender.com`

---

**Última Atualização:** 24 de Novembro de 2025  
**Versão:** 1.0

