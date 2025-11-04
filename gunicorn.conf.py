# Gunicorn configuration for Dashboard-TRONIK

bind = "127.0.0.1:8000"
workers = 4
worker_class = "gthread"
threads = 8

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


