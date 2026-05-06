# Migración de Happy Nest entre VMs

Scripts que automatizan el plan de migración descrito en `~/.claude/plans/necesito-hacer-un-back-happy-nest.md`.

## Orden de ejecución

| # | Script | Dónde corre | Qué hace |
|---|--------|-------------|----------|
| 1 | `backup.sh` | VM **origen** | Genera backup Frappe completo (DB + archivos + site_config con encryption_key) |
| 2 | `transfer.sh` | VM **origen** | Sincroniza el backup al destino vía rsync sobre SSH |
| 3 | `restore.sh` | VM **destino** | Levanta stack, crea sitio, restaura todo |

Los tres scripts son idempotentes y se pueden re-correr.

## Flujo completo

### Día -1 (preparación destino)

En la VM destino, instalar Docker, clonar el repo y copiar `.env` desde origen:

```bash
# en destino
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
git clone <repo-url> /opt/hubgh
scp ubuntu@origen:/opt/hubgh/masterhubgh/.env /opt/hubgh/masterhubgh/.env
cd /opt/hubgh/masterhubgh
docker compose -f docker/docker-compose.prod.yml pull
```

Bajar TTL del DNS (`PUBLIC_DOMAIN`) a 60–300s.

### Día 0 — backup en caliente (sin downtime)

En la VM origen, posicionado en la raíz de `masterhubgh/`:

```bash
./docker/migration/backup.sh
# → genera ./backups/backup-<TS>/ con 4 archivos
./docker/migration/transfer.sh ./backups/backup-<TS> ubuntu@destino:/opt/hubgh/masterhubgh/restore-staging
```

Este primer pase puede tardar (rsync sube todo). Si querés acortar el cutover, repetí `transfer.sh` cada hora — solo manda los cambios incrementales.

### Día 0 — cutover (downtime: minutos)

En la VM origen:

```bash
./docker/migration/backup.sh --maintenance
./docker/migration/transfer.sh ./backups/backup-<TS-nuevo> ubuntu@destino:/opt/hubgh/masterhubgh/restore-staging
```

En la VM destino:

```bash
cd /opt/hubgh/masterhubgh
./docker/migration/restore.sh
```

Cuando `restore.sh` termina, cambiar DNS al IP de la VM destino. Caddy emite el cert nuevo automáticamente en ~30s.

## Variables que podés override

Todos los scripts respetan variables de entorno. Casos comunes:

| Variable | Default | Cuándo override |
|----------|---------|-----------------|
| `COMPOSE_FILE` | `docker/docker-compose.prod.yml` | Si tenés otro nombre o path |
| `SITE_NAME` | auto-detect | Si tenés varios sitios y querés uno específico |
| `BACKUP_ROOT` | `./backups` | Si querés otra ubicación local |
| `STAGING_DIR` | `./restore-staging` | Solo en `restore.sh`, ubicación de los archivos transferidos |
| `ADMIN_PASSWORD_TMP` | `changeme-temporal` | Solo en `restore.sh`, password admin temporal antes de restore |

Ejemplo:

```bash
SITE_NAME=hubgh.miempresa.com BACKUP_ROOT=/srv/backups ./docker/migration/backup.sh
```

## Verificación post-restore

```bash
# en destino, después de restore.sh y cambio de DNS
curl -I https://<PUBLIC_DOMAIN>/                  # 200/302 + cert válido
docker compose exec backend bench --site <s> doctor
docker compose logs -f --tail=100                 # observar 10 min
```

Validaciones manuales obligatorias:
1. Login con un usuario real → entra al desk
2. Abrir un documento con adjuntos → cargan los archivos
3. Crear un registro nuevo → confirma escritura
4. Mandar email de prueba → valida que la `encryption_key` se preservó (sin ella, las credenciales SMTP guardadas son basura)

## Rollback

Si algo sale mal en destino:

1. Revertir DNS al IP de origen.
2. En origen: `docker compose exec backend bench --site <s> set-maintenance-mode off`.
3. Investigar destino sin presión.

**No borrar la VM origen hasta 7 días de uptime exitoso en destino.**
