#!/bin/bash
# Entrypoint del contenedor backend.
# Se ejecuta cada vez que el contenedor arranca.
set -e

BENCH_DIR="/home/frappe/frappe-bench"

if [ ! -f "$BENCH_DIR/Procfile" ]; then
  echo "==> Primera vez: inicializando bench con Frappe v15 (5-10 min)..."
  cd /home/frappe
  bench init \
    --skip-redis-config-generation \
    --frappe-branch version-15 \
    frappe-bench
  echo "==> Bench inicializado."
fi

cd "$BENCH_DIR"

bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -g webserver_port 8000

echo "==> Arrancando bench..."
exec bench start
