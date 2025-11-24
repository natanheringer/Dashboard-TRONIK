# 🚀 Implementações - Dashboard-TRONIK

**Data:** 20-11-2025  
**Sessão:** Notificações, Docker e Melhorias no Mapa

---

## ✅ 1. Sistema de Notificações por Email

### Implementado

1. **Modelo de Notificação** (`banco_dados/modelos.py`)
   - Tabela `notificacoes` com campos:
     - `tipo`: Tipo da notificação (lixeira_cheia, bateria_baixa)
     - `titulo`: Título da notificação
     - `mensagem`: Mensagem detalhada
     - `coletor_id`, `sensor_id`: Relacionamentos
     - `enviada`: Status de envio
     - `enviada_em`, `criada_em`: Timestamps

2. **Módulo de Notificações** (`banco_dados/notificacoes.py`)
   - `inicializar_mail()`: Inicializa Flask-Mail
   - `verificar_alertas_lixeiras()`: Verifica coletores > 80%
   - `verificar_alertas_sensores()`: Verifica sensores com bateria < 20%
   - `criar_notificacao()`: Cria notificação no banco
   - `enviar_email_notificacao()`: Envia email via Flask-Mail
   - `processar_alertas()`: Processa todos os alertas e envia emails

3. **Configuração Flask-Mail** (`app.py`)
   - Integração com Flask-Mail
   - Configurações via variáveis de ambiente
   - Ativação condicional (só funciona se MAIL_SERVER configurado)

4. **Endpoints API** (`rotas/api.py`)
   - `GET /api/notificacoes`: Lista notificações com filtros
   - `POST /api/notificacoes/processar-alertas`: Processa alertas (admin only)

5. **Script CLI** (`scripts/processar_alertas.py`)
   - Script para processar alertas via linha de comando
   - Pode ser agendado via cron
   - Logs detalhados de processamento

### Configuração

Adicione ao `.env`:
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-app
MAIL_DEFAULT_SENDER=noreply@tronik.com
```

### Uso

```bash
# Processar alertas manualmente
python scripts/processar_alertas.py

# Ou via API (admin)
curl -X POST http://localhost:5000/api/notificacoes/processar-alertas \
  -H "Authorization: Bearer TOKEN"
```

---

## ✅ 2. Docker Setup

### Implementado

1. **Dockerfile**
   - Base: Python 3.11-slim
   - Instalação de dependências
   - Health check configurado
   - Porta 5000 exposta

2. **docker-compose.yml**
   - Serviço `app`: Aplicação Flask
   - Volumes para persistência do banco
   - Variáveis de ambiente configuráveis
   - Health checks automáticos
   - Serviço MailHog opcional (comentado)

3. **.dockerignore**
   - Ignora arquivos desnecessários no build
   - Reduz tamanho da imagem

4. **Documentação** (`DOCKER.md`)
   - Guia completo de uso
   - Comandos úteis
   - Troubleshooting
   - Configuração de email

### Uso

```bash
# Construir e executar
docker-compose up -d

# Ver logs
docker-compose logs -f app

# Parar
docker-compose down
```

---

## ✅ 3. Melhorias no Mapa

### Implementado

1. **Clusters de Marcadores** (Leaflet.markercluster)
   - Agrupamento automático de marcadores próximos
   - Melhor performance com muitas coletores
   - Zoom automático ao clicar em cluster
   - Configuração otimizada

2. **Rotas Otimizadas**
   - Algoritmo Nearest Neighbor para cálculo de rota
   - Função `calcularRotaOtimizada()`: Calcula ordem de visita
   - Função `adicionarRota()`: Adiciona rota ao mapa (Leaflet Routing Machine)
   - Função `removerRota()`: Remove rota do mapa
   - Função `calcularDistancia()`: Distância Haversine entre pontos

3. **Bibliotecas Adicionadas**
   - Leaflet.markercluster (clusters)
   - Leaflet Routing Machine (rotas)

### Uso

```javascript
// Calcular rota otimizada
const coletores = [...]; // Array de coletores
const rota = MapaTronik.calcularRotaOtimizada(coletores, {lat: -15.7942, lon: -47.8822});

// Adicionar rota ao mapa
MapaTronik.adicionarRota(rota);

// Remover rota
MapaTronik.removerRota();
```

---

## 📦 Dependências Adicionadas

### requirements.txt
- `Flask-Mail==0.9.1` - Sistema de notificações por email

### CDN (templates/base.html)
- `leaflet.markercluster@1.5.3` - Clusters de marcadores
- `leaflet-routing-machine@3.2.12` - Rotas no mapa

---

## 📝 Arquivos Criados/Modificados

### Novos Arquivos
- `banco_dados/notificacoes.py` - Módulo de notificações
- `Dockerfile` - Imagem Docker
- `docker-compose.yml` - Orquestração Docker
- `.dockerignore` - Ignorar arquivos no build
- `DOCKER.md` - Documentação Docker
- `scripts/processar_alertas.py` - Script CLI para alertas
- `IMPLEMENTACOES_2025.md` - Este documento

### Arquivos Modificados
- `banco_dados/modelos.py` - Adicionado modelo `Notificacao`
- `app.py` - Integração Flask-Mail
- `rotas/api.py` - Endpoints de notificações
- `requirements.txt` - Adicionado Flask-Mail
- `templates/base.html` - CDNs de clusters e rotas
- `estatico/js/mapa.js` - Funções de clusters e rotas
- `deploy/env.example` - Configurações de email

---

## 🎯 Próximos Passos Sugeridos

1. **Agendamento Automático de Alertas**
   - Usar APScheduler ou Celery para processar alertas periodicamente
   - Configurar intervalo (ex: a cada hora)

2. **Interface de Notificações**
   - Página para visualizar histórico de notificações
   - Filtros e busca
   - Marcar como lida

3. **Melhorias nas Rotas**
   - Integração com API de rotas real (Google Maps, OSRM)
   - Cálculo de tempo estimado
   - Otimização TSP mais sofisticada

4. **Filtros por Região no Mapa**
   - Seleção de área geográfica
   - Filtro por distância
   - Agrupamento por região

---

## ✅ Checklist de Implementação

- [x] Modelo de Notificação no banco
- [x] Módulo de notificações (Flask-Mail)
- [x] Verificação de alertas (coletor > 80%, bateria < 20%)
- [x] Envio de emails
- [x] Endpoints API de notificações
- [x] Script CLI para processar alertas
- [x] Dockerfile
- [x] docker-compose.yml
- [x] Documentação Docker
- [x] Clusters de marcadores no mapa
- [x] Cálculo de rotas otimizadas
- [x] Funções de rota no mapa

---

**Status:** ✅ Todas as implementações concluídas e testadas!



