import os
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from os import getenv, makedirs
from os.path import exists

bind_addr = os.getenv('FLASK_HOST','0.0.0.0')
bind_port = os.getenv('FLASK_PORT','5000')
worker_count = int(os.getenv('FLASK_WORKERS', 6))
# Sized with headroom above JIT_ACCESS_ENGINE_POOL_SIZE (default 32) per worker process,
# so routes like /healthz can always get a thread even when the Access Engine pool is saturated.
thread_count = int(os.getenv('FLASK_THREADS', 40))

bind = f"{bind_addr}:{bind_port}"
workers = worker_count
worker_class = 'gthread'
threads = thread_count
# A single upstream Access Engine call may legitimately take up to JIT_ACCESS_ENGINE_TIMEOUT_SECONDS
# (default 60s), with put_sessions retrying up to twice that. Give workers enough headroom above
# that worst case so a slow-but-legitimate upstream doesn't get mistaken for an unresponsive worker.
timeout = int(os.getenv('GUNICORN_WORKER_TIMEOUT', 180))
keepalive = 5
# certfile = "/ssl/tls.crt"
# keyfile = "/ssl/tls.key"
# reload_extra_files = "/ssl/tls.crt"


# Prometheus metrics config
def when_ready(server):

    prom_multip_path = getenv("PROMETHEUS_MULTIPROC_DIR", "/app/jit/pi/metrics")
    if not exists(prom_multip_path):
        makedirs(prom_multip_path)

    GunicornPrometheusMetrics.start_http_server_when_ready(
        int(getenv("PROMETHEUS_METRICS_PORT", "8080"))
    )


def child_exit(server, worker):
    GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)