# 🐳 Docker - Dashboard-TRONIK

Este documento explica como executar o Dashboard-TRONIK usando Docker e Docker Compose.

## 📋 Pré-requisitos

- Docker Engine 20.10+
- Docker Compose 2.0+

## 🚀 Início Rápido

### 1. Configurar Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env` e configure as variáveis necessárias:

```bash
cp deploy/env.example .env
```

Edite o arquivo `.env` e configure:
- `SECRET_KEY`: Chave secreta para sessões (gere uma chave forte)
- `MAIL_SERVER`: Servidor SMTP (opcional, para notificações)
- `MAIL_USERNAME`: Usuário do email (opcional)
- `MAIL_PASSWORD`: Senha do email (opcional)

### 2. Construir e Executar

```bash
# Construir e iniciar os containers
docker-compose up -d

# Ver logs
docker-compose logs -f app

# Parar os containers
docker-compose down
```

### 3. Acessar a Aplicação

A aplicação estará disponível em: `http://localhost:5000`

## 📦 Estrutura Docker

### Dockerfile

O `Dockerfile` cria uma imagem otimizada com:
- Python 3.11-slim (imagem leve)
- Dependências instaladas
- Health check configurado
- Porta 5000 exposta

### docker-compose.yml

O `docker-compose.yml` define:
- **app**: Container da aplicação Flask
- Volumes para persistência do banco de dados
- Variáveis de ambiente configuráveis
- Health checks automáticos

## 🔧 Comandos Úteis

### Desenvolvimento

```bash
# Reconstruir após mudanças
docker-compose build

# Executar em modo interativo (com logs)
docker-compose up

# Executar comandos dentro do container
docker-compose exec app python -c "print('Hello from container')"
```

### Produção

```bash
# Construir para produção
docker-compose -f docker-compose.yml build

# Executar em background
docker-compose -f docker-compose.yml up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f app
```

### Manutenção

```bash
# Parar e remover containers (mantém volumes)
docker-compose down

# Parar e remover tudo (incluindo volumes)
docker-compose down -v

# Limpar imagens não utilizadas
docker system prune -a
```

## 🗄️ Persistência de Dados

O banco de dados SQLite é persistido no diretório `./data` do host. Isso garante que os dados não sejam perdidos ao recriar os containers.

**Importante**: Faça backup regular do diretório `./data` em produção.

## 📧 Configuração de Email (Opcional)

Para habilitar notificações por email, configure no `.env`:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-app
MAIL_DEFAULT_SENDER=noreply@tronik.com
```

### Gmail

Para usar Gmail, você precisará:
1. Ativar "Acesso a apps menos seguros" OU
2. Criar uma "Senha de app" (recomendado)

### MailHog (Desenvolvimento)

Para testar emails localmente, descomente o serviço `mailhog` no `docker-compose.yml`:

```yaml
mailhog:
  image: mailhog/mailhog:latest
  ports:
    - "1025:1025"  # SMTP
    - "8025:8025"  # Web UI
```

Configure no `.env`:
```env
MAIL_SERVER=mailhog
MAIL_PORT=1025
MAIL_USE_TLS=false
```

Acesse a interface web do MailHog em: `http://localhost:8025`

## 🔍 Health Checks

O container possui um health check que verifica se a aplicação está respondendo:

```bash
# Verificar status de saúde
docker-compose ps

# Ver logs do health check
docker inspect dashboard-tronik-app | grep -A 10 Health
```

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker-compose logs app

# Verificar se a porta está em uso
lsof -i :5000

# Reconstruir do zero
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Banco de dados não persiste

Verifique se o volume está montado corretamente:

```bash
docker-compose exec app ls -la /app/data
```

### Erro de permissões

```bash
# Ajustar permissões do diretório data
sudo chown -R $USER:$USER ./data
```

## 📚 Recursos Adicionais

- [Documentação Docker](https://docs.docker.com/)
- [Documentação Docker Compose](https://docs.docker.com/compose/)
- [Flask-Mail Documentation](https://pythonhosted.org/Flask-Mail/)



