#!/bin/bash
# Crea el sitio hubgh.local e instala la app.
# Ejecutar UNA SOLA VEZ después de que los contenedores estén arriba.
#
# Uso:
#   cd docker/
#   docker-compose exec backend bash /home/frappe/frappe-bench/apps/hubgh/docker/create-site.sh
#
# O desde la raíz del repo:
#   docker exec -it hubgh-backend-1 bash /home/frappe/frappe-bench/apps/hubgh/docker/create-site.sh

set -e

SITE_NAME="${FRAPPE_SITE_NAME:-hubgh.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
DB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-frappe}"

BENCH_DIR="/home/frappe/frappe-bench"

echo "==> Directorio bench: $BENCH_DIR"
cd "$BENCH_DIR"

# Configurar conexiones a Redis y MariaDB
bench set-config -g db_host mariadb
bench set-config -g redis_cache "redis://redis-cache:6379"
bench set-config -g redis_queue "redis://redis-queue:6379"
bench set-config -g redis_socketio "redis://redis-queue:6379"
bench set-config -g webserver_port 8000

# Si el sitio ya existe, omitir creación
if bench --site "$SITE_NAME" show-config > /dev/null 2>&1; then
  echo "==> Sitio $SITE_NAME ya existe, salteando creación."
else
  echo "==> Creando sitio $SITE_NAME ..."
  bench new-site "$SITE_NAME" \
    --mariadb-root-password "$DB_ROOT_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --no-mariadb-socket
  echo "==> Sitio creado."
fi

# Instalar app si no está instalada
if bench --site "$SITE_NAME" list-apps | grep -q "^hubgh$"; then
  echo "==> App hubgh ya está instalada."
else
  echo "==> Instalando app hubgh ..."
  bench --site "$SITE_NAME" install-app hubgh
  echo "==> App instalada."
fi

# Configurar como sitio por defecto
bench use "$SITE_NAME"

echo ""
echo "✓ Listo. Reiniciá los contenedores para aplicar cambios:"
echo "  docker-compose restart backend"
