# ❓ FAQ Railway - Dashboard-TRONIK

## 🔄 Como Fazer Deploy Novamente?

### Deploy Automático (Recomendado)

Sim! Basta fazer commit e push:

```bash
# Fazer suas alterações
git add .
git commit -m "sua mensagem"
git push origin main
```

O Railway detecta automaticamente o push e faz deploy. Você pode acompanhar no painel Railway em **"Deployments"**.

### Deploy Manual

Se quiser forçar um deploy sem fazer commit:

1. No painel Railway, vá em **"Deployments"**
2. Clique em **"Redeploy"** → **"Deploy latest commit"**

### Forçar Deploy Após Mudar Builder

Se você acabou de mudar o Builder para NIXPACKS e quer forçar um novo deploy:

```bash
# Commit vazio para triggerar deploy
git commit --allow-empty -m "trigger: forçar deploy com NIXPACKS"
git push
```

---

## 🌐 Qual Porta Colocar para Domínio Customizado?

### Resposta Rápida: **DEIXE EM BRANCO** ✅

Quando configurar domínio customizado no Railway:

1. **Domínio:** Coloque seu domínio (ex: `dashboard-tronik.com`)
2. **Porta:** **DEIXE EM BRANCO** ou deixe o padrão que aparecer

### Por quê?

- O Railway **rotea automaticamente** para a porta correta
- A porta é definida automaticamente via variável `PORT`
- Você não precisa especificar manualmente
- O Railway detecta qual porta sua aplicação está ouvindo

### Se o Campo for Obrigatório

Se o Railway exigir uma porta (raro):

1. **Deixe o padrão** que aparecer (geralmente 8080 ou vazio)
2. Ou **deixe em branco** se permitir
3. O Railway ajustará automaticamente

**Importante:** A porta que você coloca aqui **não precisa** ser a mesma que está no código. O Railway faz o roteamento automaticamente.

---

## 🔍 Como Ver Qual Porta Está Sendo Usada?

Se quiser verificar qual porta o Railway definiu:

1. No painel Railway, vá em **"Variables"**
2. Procure pela variável `PORT` (pode não aparecer, pois é interna)
3. Ou veja os logs do deploy - geralmente mostra algo como:
   ```
   Starting on port 3000
   ```

Mas **não precisa** dessa informação para configurar domínio customizado!

---

## ✅ Checklist Domínio Customizado

1. [ ] Adicionar domínio no Railway (Settings → Domains)
2. [ ] **Porta: deixar em branco ou padrão**
3. [ ] Configurar DNS conforme instruções do Railway
4. [ ] Aguardar propagação DNS (pode levar alguns minutos)
5. [ ] Atualizar `CORS_ORIGINS` com novo domínio
6. [ ] Testar acesso via novo domínio

---

## 🚨 Problemas Comuns com Domínio

### Domínio não carrega

- Verifique se DNS está configurado corretamente
- Aguarde propagação DNS (até 24h, geralmente alguns minutos)
- Verifique se o domínio está apontando para o Railway

### CORS bloqueado após adicionar domínio

- Atualize `CORS_ORIGINS` no Railway:
  ```env
  CORS_ORIGINS=https://seu-dominio.com,https://seu-projeto.railway.app
  ```
- Faça novo deploy após atualizar

---

**Última Atualização:** 2025-01-XX

