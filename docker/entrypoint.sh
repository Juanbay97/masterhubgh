#!/bin/bash
set -euo pipefail
# Entrypoint del contenedor backend.

BENCH_DIR="/home/frappe/frappe-bench"

# ── Inicialización del bench (solo primera vez) ──────────────────────────────
# Docker pre-crea $BENCH_DIR como named volume antes de que este script corra,
# así que bench init siempre ve un directorio existente y falla.
# Solución: inicializar en /tmp (directorio limpio) y copiar al volume.
if [ ! -f "$BENCH_DIR/Procfile" ]; then
  echo "==> Inicializando bench (primera vez, ~10-15 min)..."

  # El volumen bench_data es creado por Docker con owner root.
  # Lo corregimos antes de intentar escribir como usuario frappe.
  sudo chown -R frappe:frappe "$BENCH_DIR"

  cd /tmp
  rm -rf frappe-bench-tmp

  bench init \
    --skip-redis-config-generation \
    --frappe-branch version-15 \
    frappe-bench-tmp || { echo "ERROR: bench init falló"; exit 1; }

  # Copiar al volume. apps/hubgh y sites ya están montados como sub-volumes:
  # cp los ignora si no hay conflicto, y agrega los archivos del bench (frappe,
  # Procfile, env/, etc.) sin pisar los mounts existentes.
  cp -a frappe-bench-tmp/. "$BENCH_DIR/"
  rm -rf frappe-bench-tmp

  # ── Registrar app hubgh en el entorno Python del bench ───────────────────
  # bench init crea apps.txt con solo "frappe". El app hubgh está bind-montada
  # en apps/hubgh pero bench no la conoce hasta que se pip-instala y se agrega
  # a apps.txt. Sin esto, "bench install-app hubgh" falla.
  cd "$BENCH_DIR"
  echo "==> Registrando app hubgh en el bench..."
  ./env/bin/python -m pip install -q -e apps/hubgh
  echo "hubgh" >> apps.txt

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
