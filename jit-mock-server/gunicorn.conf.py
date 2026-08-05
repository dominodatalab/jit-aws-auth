import os

bind_addr = os.getenv('FLASK_HOST', '0.0.0.0')
bind_port = os.getenv('FLASK_PORT', '8080')
worker_count = int(os.getenv('FLASK_WORKERS', 6))
thread_count = int(os.getenv('FLASK_THREADS', 40))

bind = f"{bind_addr}:{bind_port}"
workers = worker_count
worker_class = 'gthread'
threads = thread_count
# Headroom above MAX_RESPONSE_JITTER_SECONDS (default 60s) so a legitimately
# slow simulated response isn't mistaken for an unresponsive worker.
timeout = int(os.getenv('GUNICORN_WORKER_TIMEOUT', 180))
keepalive = 5
