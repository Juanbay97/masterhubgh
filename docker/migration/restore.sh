#!/usr/bin/env bash
#
# restore.sh — Fase 3.3, 3.4 y parte de Fase 4 del plan de migración.
# Corre en la VM DESTINO. Levanta el stack vacío, crea el sitio y restaura
# DB + archivos + site_config (con encryption_key intacta).
#
# Pre-requisitos en la VM destino:
#   - Docker + plugin Compose v2 instalados
#   - Repo del proyecto clonado, posicionado en la raíz (donde está package.json)
#   - .env existe en la raíz y está actualizado (PUBLIC_DOMAIN, ACME_EMAIL, MARIADB_ROOT_PASSWORD)
#   - El directorio con el backup transferido por transfer.sh (default: ./restore-staging)
#
# Uso:
#   ./restore.sh                              # usa ./restore-staging y auto-detecta sitename
#   STAGING_DIR=/tmp/x SITE_NAME=foo ./restore.sh

set -euo pipefail

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────────────────────────
COMPOSE_FILE="${COMPOSE_FILE:-docker/docker-compose.prod.yml}"
STAGING_DIR="${STAGING_DIR:-./restore-staging}"
SITE_NAME="${SITE_NAME:-}"
ADMIN_PASSWORD_TMP="${ADMIN_PASSWORD_TMP:-changeme-temporal}"

# ───────────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────────
log()  { printf '\033[1;36m[restore]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[restore]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[restore]\033[0m %s\n' "$*" >&2; exit 1; }

dc() { docker compose -f "$COMPOSE_FILE" "$@"; }

# ───────────────────────────────────────────────────────────────────────────────
# Pre-flight
# ───────────────────────────────────────────────────────────────────────────────
[[ -f "$COMPOSE_FILE" ]] || fail "No se encontró el compose file: $COMPOSE_FILE"
[[ -f .env ]]            || fail "No se encontró .env en $(pwd). Copialo desde origen con scp antes de continuar."
[[ -d "$STAGING_DIR" ]]  || fail "No se encontró el directorio de backup: $STAGING_DIR"

# Detectar timestamp del backup más reciente en staging
BACKUP_TS="$(ls "$STAGING_DIR" | grep -oE '^[0-9]{8}_[0-9]{6}' | sort -u | tail -1 || true)"
[[ -n "$BACKUP_TS" ]] || fail "No encontré archivos de backup con prefijo timestamp en $STAGING_DIR"
log "Timestamp del backup a restaurar: $BACKUP_TS"

# Validar los 4 archivos
for suffix in database.sql.gz files.tar private-files.tar site_config_backup.json; do
    if ! ls "$STAGING_DIR"/${BACKUP_TS}*-${suffix} >/dev/null 2>&1; then
        fail "Falta *-${suffix} en $STAGING_DIR. Backup incompleto."
    fi
done

# ───────────────────────────────────────────────────────────────────────────────
# Cargar variables del .env (necesitamos MARIADB_ROOT_PASSWORD)
# ───────────────────────────────────────────────────────────────────────────────
# shellcheck disable=SC1091
set -a; source .env; set +a
[[ -n "${MARIADB_ROOT_PASSWORD:-}" ]] || fail "MARIADB_ROOT_PASSWORD no está en .env"

# Si no nos dieron sitename, intentamos sacarlo del nombre de archivo
if [[ -z "$SITE_NAME" ]]; then
    # Frappe nombra los backups como YYYYMMDD_HHMMSS-<sitename>-database.sql.gz
    db_file="$(ls "$STAGING_DIR"/${BACKUP_TS}*-database.sql.gz | head -1)"
    SITE_NAME="$(basename "$db_file" | sed -E "s/^${BACKUP_TS}-(.+)-database\\.sql\\.gz$/\\1/")"
    [[ -n "$SITE_NAME" && "$SITE_NAME" != "$db_file" ]] || fail "No pude extraer el sitename del backup. Setealo con SITE_NAME=<sitio>"
fi
log "Sitio: $SITE_NAME"

# ───────────────────────────────────────────────────────────────────────────────
# Confirmación — esto es destructivo si el sitio ya existe
# ───────────────────────────────────────────────────────────────────────────────
warn "El restore va a USAR --force. Si el sitio '$SITE_NAME' ya existe en destino, se sobreescribe."
read -r -p "¿Continuar? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { warn "Abortado."; exit 1; }

# ───────────────────────────────────────────────────────────────────────────────
# Levantar servicios base (sin Caddy todavía — Caddy va después del restore)
# ───────────────────────────────────────────────────────────────────────────────
log "Levantando mariadb + redis..."
dc up -d mariadb redis-cache redis-queue

log "Esperando healthcheck de mariadb..."
for i in {1..30}; do
    if dc ps mariadb --status running --quiet | grep -q .; then
        if dc exec -T mariadb mysqladmin ping -h localhost --silent 2>/dev/null; then
            log "✓ MariaDB lista."
            break
        fi
    fi
    sleep 2
    [[ "$i" == "30" ]] && fail "MariaDB no respondió en 60s. Revisá: dc logs mariadb"
done

log "Levantando backend..."
dc up -d backend
sleep 10

# ───────────────────────────────────────────────────────────────────────────────
# Crear sitio si no existe
# ───────────────────────────────────────────────────────────────────────────────
if dc exec -T backend bash -c "test -f /home/frappe/frappe-bench/sites/$SITE_NAME/site_config.json"; then
    log "El sitio '$SITE_NAME' ya existe en destino. Se restaura encima con --force."
else
    log "Creando sitio vacío '$SITE_NAME'..."
    dc exec -T backend bash -c "
        cd /home/frappe/frappe-bench &&
        bench new-site $SITE_NAME \
            --admin-password '$ADMIN_PASSWORD_TMP' \
            --mariadb-root-password '$MARIADB_ROOT_PASSWORD' \
            --no-mariadb-socket
    "
fi

# ───────────────────────────────────────────────────────────────────────────────
# Copiar backups dentro del container
# ───────────────────────────────────────────────────────────────────────────────
log "Copiando backups dentro del container backend..."
dc exec -T backend bash -c "mkdir -p /home/frappe/frappe-bench/sites/$SITE_NAME/private/backups"
dc cp "$STAGING_DIR/." "backend:/home/frappe/frappe-bench/sites/$SITE_NAME/private/backups/"

# ───────────────────────────────────────────────────────────────────────────────
# Restaurar
# ───────────────────────────────────────────────────────────────────────────────
log "Restaurando DB + archivos + site_config (con encryption_key)..."
dc exec -T backend bash -c "
    cd /home/frappe/frappe-bench &&
    bench --site $SITE_NAME --force restore \
        sites/$SITE_NAME/private/backups/${BACKUP_TS}-${SITE_NAME//./_}-database.sql.gz \
        --with-public-files sites/$SITE_NAME/private/backups/${BACKUP_TS}-${SITE_NAME//./_}-files.tar \
        --with-private-files sites/$SITE_NAME/private/backups/${BACKUP_TS}-${SITE_NAME//./_}-private-files.tar
" || {
    warn "Restore falló con nombre normalizado. Reintentando con nombre literal del archivo..."
    DB_FILE="$(ls "$STAGING_DIR"/${BACKUP_TS}*-database.sql.gz | xargs -n1 basename | head -1)"
    PUB_FILE="$(ls "$STAGING_DIR"/${BACKUP_TS}*-files.tar | grep -v 'private-files' | xargs -n1 basename | head -1)"
    PRV_FILE="$(ls "$STAGING_DIR"/${BACKUP_TS}*-private-files.tar | xargs -n1 basename | head -1)"
    dc exec -T backend bash -c "
        cd /home/frappe/frappe-bench &&
        bench --site $SITE_NAME --force restore \
            sites/$SITE_NAME/private/backups/$DB_FILE \
            --with-public-files sites/$SITE_NAME/private/backups/$PUB_FILE \
            --with-private-files sites/$SITE_NAME/private/backups/$PRV_FILE
    "
}

# ───────────────────────────────────────────────────────────────────────────────
# Migrate + clear cache + bajar maintenance mode
# ───────────────────────────────────────────────────────────────────────────────
log "Aplicando migraciones de schema..."
dc exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME migrate"

log "Limpiando cache..."
dc exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME clear-cache"

log "Desactivando modo mantenimiento..."
dc exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME set-maintenance-mode off" || true

# ───────────────────────────────────────────────────────────────────────────────
# Levantar Caddy
# ───────────────────────────────────────────────────────────────────────────────
log "Levantando Caddy (TLS automático)..."
dc up -d caddy

log ""
log "✓ Restore completo."
log ""
log "Próximos pasos manuales:"
log "  1. Cambiá el DNS del PUBLIC_DOMAIN a la IP de esta VM."
log "  2. Esperá ~30s a que Caddy emita el cert Let's Encrypt."
log "  3. Verificá:"
log "       curl -I https://\$PUBLIC_DOMAIN/"
log "       dc exec backend bash -c 'bench --site $SITE_NAME doctor'"
log "  4. Login + abrí un documento con adjuntos + creá un registro de prueba."
log "  5. Mandá un email de prueba (valida que la encryption_key se preservó)."
