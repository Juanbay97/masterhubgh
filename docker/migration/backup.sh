#!/usr/bin/env bash
#
# backup.sh — Fase 1 y 3.1 del plan de migración.
# Corre en la VM ORIGEN. Genera un backup de Frappe (DB + archivos públicos +
# privados + site_config con encryption_key) y lo copia al host.
#
# Uso:
#   ./backup.sh                  # backup en caliente, sin downtime (Fase 1)
#   ./backup.sh --maintenance    # activa modo mantenimiento antes (Fase 3.1)
#
# Salida: directorio ./backup-<TIMESTAMP>/ con los 4 archivos del backup.

set -euo pipefail

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG — editar si los paths del proyecto cambian
# ───────────────────────────────────────────────────────────────────────────────
COMPOSE_FILE="${COMPOSE_FILE:-docker/docker-compose.prod.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
SITE_NAME="${SITE_NAME:-}"   # vacío = auto-detect

# ───────────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────────
log()  { printf '\033[1;36m[backup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[backup]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[backup]\033[0m %s\n' "$*" >&2; exit 1; }

dc() { docker compose -f "$COMPOSE_FILE" "$@"; }

# ───────────────────────────────────────────────────────────────────────────────
# Pre-flight
# ───────────────────────────────────────────────────────────────────────────────
[[ -f "$COMPOSE_FILE" ]] || fail "No se encontró el compose file: $COMPOSE_FILE"

if ! dc ps backend --status running --quiet | grep -q .; then
    fail "El servicio 'backend' no está corriendo. Levantalo con: dc up -d"
fi

MAINTENANCE=0
if [[ "${1:-}" == "--maintenance" ]]; then
    MAINTENANCE=1
fi

# ───────────────────────────────────────────────────────────────────────────────
# Detectar sitename
# ───────────────────────────────────────────────────────────────────────────────
if [[ -z "$SITE_NAME" ]]; then
    log "Auto-detectando nombre del sitio..."
    SITE_NAME="$(dc exec -T backend bash -c '
        ls /home/frappe/frappe-bench/sites \
        | grep -vE "^(assets|common_site_config\.json|apps\.txt|apps\.json)$" \
        | head -1
    ' | tr -d '\r')"
    [[ -n "$SITE_NAME" ]] || fail "No pude detectar el sitename. Setealo con SITE_NAME=<sitio> ./backup.sh"
fi
log "Sitio: $SITE_NAME"

# ───────────────────────────────────────────────────────────────────────────────
# Maintenance mode (opcional, solo en cutover final)
# ───────────────────────────────────────────────────────────────────────────────
if [[ "$MAINTENANCE" == "1" ]]; then
    warn "Activando modo mantenimiento — el sitio rechazará requests de usuarios."
    read -r -p "¿Continuar? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { warn "Abortado."; exit 1; }
    dc exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME set-maintenance-mode on"
fi

# ───────────────────────────────────────────────────────────────────────────────
# Backup
# ───────────────────────────────────────────────────────────────────────────────
log "Ejecutando bench backup --with-files --compress (puede tardar varios minutos según tamaño)..."
dc exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME backup --with-files --compress"

# ───────────────────────────────────────────────────────────────────────────────
# Copiar al host
# ───────────────────────────────────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DEST_DIR="$BACKUP_ROOT/backup-$TIMESTAMP"
mkdir -p "$DEST_DIR"

log "Copiando backups del container a $DEST_DIR..."
dc cp "backend:/home/frappe/frappe-bench/sites/$SITE_NAME/private/backups/." "$DEST_DIR/"

# Quedarnos solo con los 4 archivos del backup más reciente (mismo prefijo de timestamp)
LATEST_TS="$(ls "$DEST_DIR" | grep -oE '^[0-9]{8}_[0-9]{6}' | sort -u | tail -1 || true)"
[[ -n "$LATEST_TS" ]] || fail "No encontré archivos de backup en $DEST_DIR"

log "Backup más reciente: $LATEST_TS"
log "Limpiando backups viejos del directorio local..."
find "$DEST_DIR" -maxdepth 1 -type f ! -name "${LATEST_TS}*" -delete

# ───────────────────────────────────────────────────────────────────────────────
# Verificar los 4 archivos esperados
# ───────────────────────────────────────────────────────────────────────────────
expected=(database.sql.gz files.tar private-files.tar site_config_backup.json)
for suffix in "${expected[@]}"; do
    if ! ls "$DEST_DIR"/${LATEST_TS}*-${suffix} >/dev/null 2>&1; then
        fail "Falta el archivo *-${suffix} en $DEST_DIR. Backup incompleto."
    fi
done

log "✓ Backup OK en: $DEST_DIR"
log "  $(ls -lh "$DEST_DIR" | tail -n +2 | awk '{print $9, "("$5")"}' | tr '\n' ' ')"
log ""
log "Próximo paso: ./transfer.sh $DEST_DIR <user@destino>:<path-destino>"
