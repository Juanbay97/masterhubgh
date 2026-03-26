#!/bin/bash
# Entrypoint del contenedor backend.
# Se ejecuta cada vez que el contenedor arranca.

BENCH_DIR="/home/frappe/frappe-bench"

# ── Inicialización del bench (solo primera vez) ──────────────────────────────
# El bench vive en un named volume. Si Procfile no existe, el bench
# está incompleto o nunca se inicializó — hay que hacerlo ahora.
if [ ! -f "$BENCH_DIR/Procfile" ]; then
  echo "==> Bench incompleto o no inicializado. Limpiando y arrancando de cero..."

  # Vaciar la carpeta si quedó a medias (bench init falla si el dir existe y no está vacío)
  if [ -d "$BENCH_DIR" ]; then
    rm -rf "${BENCH_DIR:?}"/*
  fi

  echo "==> Inicializando bench con Frappe v15 (5-10 min la primera vez)..."
  cd /home/frappe
  bench init \
    --skip-redis-config-generation \
    --frappe-branch version-15 \
    frappe-bench
  echo "==> Bench inicializado."
fi

# ── Configuración del bench ──────────────────────────────────────────────────
# IMPORTANTE: bench set-config requiere ejecutarse DENTRO del bench dir.
cd "$BENCH_DIR" || { echo "ERROR: no se pudo entrar a $BENCH_DIR"; exit 1; }

bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -g webserver_port 8000

echo "==> Arrancando bench..."
exec bench start
