#!/bin/bash
# Crea el sitio hubgh.local e instala la app.
#
# Ejecutar DESPUÉS de que el bench haya terminado de inicializar.
# Desde la VM:
#
#   docker-compose -f docker/docker-compose.dev.yml exec backend \
#     bash -c "$(cat docker/create-site.sh)"
#
# Variables de entorno (opcionales, tienen defaults):
#   FRAPPE_SITE_NAME   — nombre del sitio (default: hubgh.local)
#   ADMIN_PASSWORD     — contraseña del admin (default: admin)
#   MARIADB_ROOT_PASSWORD — contraseña root de MariaDB (default: frappe)

set -e

SITE_NAME="${FRAPPE_SITE_NAME:-hubgh.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
DB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-frappe}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-}"
BENCH_DIR="/home/frappe/frappe-bench"
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

echo "==> Configurando bench..."
cd "$BENCH_DIR"

bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -g webserver_port 8000

HOST_NAME="$(resolve_host_name "$PUBLIC_DOMAIN")"

# Crear sitio si no existe
if bench --site "$SITE_NAME" show-config > /dev/null 2>&1; then
  echo "==> Sitio $SITE_NAME ya existe, salteando creación."
else
  echo "==> Creando sitio $SITE_NAME..."
  bench new-site "$SITE_NAME" \
    --mariadb-root-password "$DB_ROOT_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --no-mariadb-socket
  echo "==> Sitio creado."
fi

# Instalar app si no está instalada
if bench --site "$SITE_NAME" list-apps 2>/dev/null | grep -q "^hubgh$"; then
  echo "==> App hubgh ya está instalada."
else
  echo "==> Instalando app hubgh..."
  bench --site "$SITE_NAME" install-app hubgh
  echo "==> App instalada."
fi

bench use "$SITE_NAME"

if [ -n "$HOST_NAME" ]; then
  echo "==> Configurando host_name público del sitio: $HOST_NAME"
  bench --site "$SITE_NAME" set-config host_name "$HOST_NAME"
fi

echo ""
echo "✓ Setup completo."
echo "  Sitio:      $SITE_NAME"
echo "  Usuario:    Administrator"
echo "  Contraseña: $ADMIN_PASSWORD"
echo ""
echo "Reiniciá el backend para aplicar cambios de configuración:"
if [ "$HUBGH_RUNTIME_MODE" = "production" ]; then
  echo "  make prod-restart"
else
  echo "  make dev-restart"
fi
