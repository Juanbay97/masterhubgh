#!/bin/bash
set -euo pipefail

BENCH_DIR="${BENCH_DIR:-/home/frappe/frappe-bench}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-}"
HUBGH_RUNTIME_MODE="${HUBGH_RUNTIME_MODE:-development}"

resolve_host_name() {
  local domain="$1"
  if [ -z "$domain" ]; then
    return 0
  fi

  case "$domain" in
    http://*|https://*)
      printf '%s' "$domain"
      ;;
    *)
      printf 'https://%s' "$domain"
      ;;
  esac
}

current_site_name() {
  local current_site_file="$BENCH_DIR/sites/currentsite.txt"

  if [ ! -f "$current_site_file" ]; then
    return 0
  fi

  tr -d '\n' < "$current_site_file"
}

sync_site_host_name() {
  local host_name="$1"
  local current_site=""

  if [ -z "$host_name" ]; then
    return
  fi

  current_site="$(current_site_name)"
  if [ -z "$current_site" ]; then
    return
  fi

  echo "==> Asegurando host_name para $current_site: $host_name"
  bench --site "$current_site" set-config host_name "$host_name"
}

sync_site_runtime_mode() {
  local current_site=""
  local developer_mode_value="$1"

  current_site="$(current_site_name)"
  if [ -z "$current_site" ]; then
    return
  fi

  echo "==> Asegurando developer_mode=$developer_mode_value para $current_site"
  bench --site "$current_site" set-config developer_mode "$developer_mode_value"
}

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

initialize_bench_if_needed() {
  if [ -f "$BENCH_DIR/Procfile" ]; then
    return
  fi

  echo "==> Inicializando bench ($HUBGH_RUNTIME_MODE, primera vez, ~10-15 min)..."

  sudo chown -R frappe:frappe "$BENCH_DIR"

  cd /tmp
  rm -rf frappe-bench-tmp

  bench init \
    --skip-redis-config-generation \
    --frappe-branch version-15 \
    frappe-bench-tmp || { echo "ERROR: bench init falló"; exit 1; }

  cp -a frappe-bench-tmp/. "$BENCH_DIR/"
  rm -rf frappe-bench-tmp

  cd "$BENCH_DIR"
  echo "==> Reparando entorno Python (editable install paths post-cp)..."
  ./env/bin/python -m pip install -q -e apps/frappe
  echo "==> Registrando app hubgh en el bench..."
  ./env/bin/python -m pip install -q -e apps/hubgh

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
  echo "==> sites/apps.txt: $(tr '\n' ' ' < sites/apps.txt)"
  rebuild_asset_links

  echo "==> Bench inicializado."
}

configure_bench_runtime() {
  cd "$BENCH_DIR" || { echo "ERROR: no se pudo entrar a $BENCH_DIR"; exit 1; }

  bench set-config -g db_host mariadb
  bench set-config -g redis_cache redis://redis-cache:6379
  bench set-config -g redis_queue redis://redis-queue:6379
  bench set-config -g redis_socketio redis://redis-queue:6379
  bench set-config -g webserver_port 8000
  sync_site_host_name "$(resolve_host_name "$PUBLIC_DOMAIN")"
  rebuild_asset_links
}
