import os
from psycogreen.gevent import patch_psycopg
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from os import getenv, makedirs
from os.path import exists

bind_addr = os.getenv('FLASK_HOST','0.0.0.0')
bind_port = os.getenv('FLASK_PORT','5000')
worker_count = os.getenv('FLASK_WORKERS',1)

bind = f"{bind_addr}:{bind_port}"
workers = worker_count
# certfile = "/ssl/tls.crt"
# keyfile = "/ssl/tls.key"
# reload_extra_files = "/ssl/tls.crt"

# patch forked gevent processes for psycopg2
def post_fork(server, worker):
    # gevent.monkey.patch_all() is already called in GEventWorker for us
    worker.log.info("patching psycopg2 with psycogreen")
    patch_psycopg()

    worker.log.info("patching complete")


# Prometheus metrics config
def when_ready(server):

    prom_multip_path = getenv("PROMETHEUS_MULTIPROC_DIR", "/pi/metrics")
    if not exists(prom_multip_path):
        makedirs(prom_multip_path)

    GunicornPrometheusMetrics.start_http_server_when_ready(
        int(getenv("PROMETHEUS_METRICS_PORT", "8080"))
    )


def child_exit(server, worker):
    GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)