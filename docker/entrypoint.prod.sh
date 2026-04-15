#!/bin/bash
set -euo pipefail

source /runtime-common.sh

declare -a PIDS=()

cleanup() {
  local pid

  echo "==> Apagando runtime de PRODUCCION..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait || true
}

start_process() {
  local name="$1"
  shift

  echo "==> Iniciando $name..."
  "$@" &
  PIDS+=("$!")
}

trap cleanup EXIT INT TERM

initialize_bench_if_needed
configure_bench_runtime
sync_site_runtime_mode 0

cd "$BENCH_DIR"
export SITES_PATH="$BENCH_DIR/sites"

start_process "Gunicorn" ./env/bin/python -m gunicorn \
  --chdir "$BENCH_DIR" \
  -b 0.0.0.0:8000 \
  -w "${FRAPPE_GUNICORN_WORKERS:-2}" \
  --max-requests "${FRAPPE_GUNICORN_MAX_REQUESTS:-5000}" \
  --max-requests-jitter "${FRAPPE_GUNICORN_MAX_REQUESTS_JITTER:-500}" \
  -t "${FRAPPE_HTTP_TIMEOUT:-120}" \
  --graceful-timeout 30 \
  frappe.app:application \
  --preload
start_process "Socket.IO" node apps/frappe/socketio.js
start_process "Scheduler" bench schedule
start_process "Worker default" bench worker --queue default
start_process "Worker short" bench worker --queue short
start_process "Worker long" bench worker --queue long

echo "==> HubGH en modo PRODUCCION (Gunicorn + workers + socketio)."
wait -n
