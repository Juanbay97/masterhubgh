#!/bin/bash
set -euo pipefail
# Entrypoint del contenedor backend.

BENCH_DIR="/home/frappe/frappe-bench"

ensure_asset_link() {
  local app="$1"
  local public_dir="$BENCH_DIR/apps/$app/$app/public"
  local asset_path="$BENCH_DIR/sites/assets/$app"
  local current_target=""

  if [ ! -d "$public_dir" ]; then
    return
  fi

  mkdir -p "$BENCH_DIR/sites/assets"

  if [ -L "$asset_path" ]; then
    current_target="$(readlink "$asset_path" || true)"
  fi

  if [ "$current_target" = "$public_dir" ]; then
    return
  fi

  if [ -L "$asset_path" ]; then
    rm -f "$asset_path"
  elif [ -e "$asset_path" ]; then
    echo "==> WARNING: $asset_path existe y no es un symlink; se preserva."
    return
  fi

  ln -s "$public_dir" "$asset_path"
  echo "==> Asset link reparado: $asset_path -> $public_dir"
}

rebuild_asset_links() {
  local app

  if [ -f "$BENCH_DIR/sites/apps.txt" ]; then
    while read -r app; do
      [ -n "$app" ] || continue
      ensure_asset_link "$app"
    done < "$BENCH_DIR/sites/apps.txt"
  fi
}

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

  # ── Reparar el venv y registrar apps ────────────────────────────────────
  # bench init usa "pip install -e" con paths absolutos a /tmp/frappe-bench-tmp.
  # Después del cp esos paths quedan rotos en los .pth del venv.
  # Solución: reinstalar frappe y hubgh con los paths correctos del destino.
  cd "$BENCH_DIR"
  echo "==> Reparando entorno Python (editable install paths post-cp)..."
  ./env/bin/python -m pip install -q -e apps/frappe
  echo "==> Registrando app hubgh en el bench..."
  ./env/bin/python -m pip install -q -e apps/hubgh

  # Frappe v15 lee el registro de apps desde sites/apps.txt y sites/apps.json
  # (NO desde el apps.txt raíz del bench). Los actualizamos explícitamente.
  printf "frappe\nhubgh\n" > apps.txt
  printf "frappe\nhubgh\n" > sites/apps.txt
  ./env/bin/python -c "
import json, os
path = 'sites/apps.json'
apps = {}
if os.path.exists(path):
    with open(path) as f:
        apps = json.load(f)
if 'hubgh' not in apps:
    apps['hubgh'] = {
        'resolution': {'commit_hash': None, 'branch': None},
        'required': [],
        'idx': len(apps) + 1,
        'version': '0.0.1'
    }
    with open(path, 'w') as f:
        json.dump(apps, f, indent=4)
    print('==> hubgh agregado a sites/apps.json')
"
  echo "==> sites/apps.txt: $(cat sites/apps.txt | tr '\n' ' ')"
  rebuild_asset_links

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
rebuild_asset_links

echo "==> Arrancando bench..."
exec bench start
