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

# Validar que el origen tenga los 4 archivos clave (acepta .tar o .tgz)
ls "$SRC"/*-database.sql.gz        >/dev/null 2>&1 || fail "Falta *-database.sql.gz en $SRC"
ls "$SRC"/*-site_config_backup.json >/dev/null 2>&1 || fail "Falta *-site_config_backup.json en $SRC"
ls "$SRC"/*-files.t*               2>/dev/null | grep -v 'private-files' | grep -q . || fail "Falta *-files.{tar,tgz} en $SRC"
ls "$SRC"/*-private-files.t*       >/dev/null 2>&1 || fail "Falta *-private-files.{tar,tgz} en $SRC"

log "Sincronizando $SRC → $DST"
log "(rsync incremental — podés re-correrlo, solo manda los cambios)"

rsync -avz --partial --progress --human-readable \
    --rsync-path="mkdir -p $(dirname "${DST#*:}") && rsync" \
    "$SRC/" \
    "$DST/"

log "✓ Transferencia completa."
log ""
log "Próximo paso (en la VM destino): ./restore.sh"
