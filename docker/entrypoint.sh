#!/bin/bash
# Entrypoint del contenedor backend.
# Se ejecuta cada vez que el contenedor arranca.

BENCH_DIR="/home/frappe/frappe-bench"

# ── Inicialización del bench (solo primera vez) ──────────────────────────────
# Docker pre-crea el directorio (es un named volume), así que bench init
# siempre ve una carpeta existente. --force bypasea ese chequeo.
# Solo corremos init si Procfile no existe (bench incompleto o primera vez).
if [ ! -f "$BENCH_DIR/Procfile" ]; then
  echo "==> Inicializando bench con Frappe v15 (primera vez, ~10 min)..."
  cd /home/frappe
  bench init \
    --skip-redis-config-generation \
    --frappe-branch version-15 \
    --force \
    frappe-bench
  echo "==> Bench inicializado."
fi

# ── Configuración ────────────────────────────────────────────────────────────
# bench set-config requiere CWD dentro del bench dir.
cd "$BENCH_DIR" || { echo "ERROR: no se pudo entrar a $BENCH_DIR"; exit 1; }

bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -g webserver_port 8000

echo "==> Arrancando bench..."
exec bench start
