# Gunicorn configuration for Dashboard-TRONIK
# Para Render.com, use: gunicorn --bind 0.0.0.0:$PORT app:app

bind = "127.0.0.1:8000"  # Para local, use 0.0.0.0:$PORT no Render
workers = 4  # Ajuste conforme recursos disponíveis (2 para Render Starter)
worker_class = "gthread"
threads = 8  # Ajuste conforme necessário (4 para Render Starter)

# Timeouts (seconds)
timeout = 60
graceful_timeout = 30
keepalive = 5

# Reliability
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"


