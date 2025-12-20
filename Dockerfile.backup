# Dockerfile - Dashboard-TRONIK
# =============================
# Imagem Docker para o projeto Dashboard-TRONIK

FROM python:3.11-slim

# Metadados
LABEL maintainer="Tronik"
LABEL description="Dashboard-TRONIK - Sistema de Monitoramento de Lixeiras Inteligentes"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivo de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretório para banco de dados (se necessário)
RUN mkdir -p /app/data

# Expor porta (Railway define PORT dinamicamente)
EXPOSE ${PORT:-5000}

# Health check (usa PORT da variável de ambiente)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, requests; port = os.getenv('PORT', '5000'); requests.get(f'http://localhost:{port}/api/configuracoes', timeout=5)" || exit 1

# Comando para executar a aplicação com gunicorn
# Railway define PORT automaticamente via variável de ambiente
# Usar sh -c para garantir expansão de variável em qualquer contexto
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile - app:app"]



