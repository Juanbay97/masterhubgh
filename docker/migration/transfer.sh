#!/usr/bin/env bash
#
# transfer.sh — Fase 2 y 3.2 del plan de migración.
# Corre en la VM ORIGEN. Sincroniza un directorio de backup contra el destino
# vía rsync sobre SSH. Es idempotente y reanudable (--partial).
#
# Uso:
#   ./transfer.sh <backup-dir-local> <user@destino:/ruta/destino>
#
# Ejemplo:
#   ./transfer.sh ./backups/backup-20260505-143000 ubuntu@10.0.0.42:/opt/hubgh/restore-staging

set -euo pipefail

log()  { printf '\033[1;36m[transfer]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[transfer]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ $# -ne 2 ]]; then
    fail "Uso: $0 <backup-dir-local> <user@host:/path/destino>"
fi

SRC="$1"
DST="$2"

[[ -d "$SRC" ]] || fail "El directorio origen no existe: $SRC"

# Validar que el origen tenga los 4 archivos clave
for suffix in database.sql.gz files.tar private-files.tar site_config_backup.json; do
    if ! ls "$SRC"/*-${suffix} >/dev/null 2>&1; then
        fail "Falta archivo *-${suffix} en $SRC. Hacé un backup nuevo con ./backup.sh"
    fi
done

log "Sincronizando $SRC → $DST"
log "(rsync incremental — podés re-correrlo, solo manda los cambios)"

rsync -avz --partial --progress --human-readable \
    --rsync-path="mkdir -p $(dirname "${DST#*:}") && rsync" \
    "$SRC/" \
    "$DST/"

log "✓ Transferencia completa."
log ""
log "Próximo paso (en la VM destino): ./restore.sh"
