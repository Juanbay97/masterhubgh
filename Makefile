# HubGH -- Comandos de operacion Docker
# Todos los comandos usan el .env de la raiz del repo.
# Compatible con Docker Compose v1 (docker-compose) y v2 (docker compose).

# Carga .env como variables Make (evita problemas de escaping con $$ en bash -c)
-include .env
export

FRAPPE_SITE_NAME ?= hubgh.local
SITE             := $(FRAPPE_SITE_NAME)

# Site para los targets prod-*. Por defecto se resuelve dinámicamente leyendo
# `sites/currentsite.txt` dentro del container (sirve para cualquier dominio
# sin tocar .env). Override: `make prod-migrate PROD_SITE=otro.dominio.com`.
PROD_SITE ?=
PROD_ENV  = $(if $(PROD_SITE),-e PROD_SITE=$(PROD_SITE))

DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE_DEV = $(DOCKER_COMPOSE) -f docker/docker-compose.dev.yml --env-file .env
COMPOSE_PROD = $(DOCKER_COMPOSE) -f docker/docker-compose.prod.yml --env-file .env

.PHONY: \
	up down restart logs shell init-site migrate build ps destroy \
	e2e-install e2e-candidato \
	dev-up dev-down dev-restart dev-logs dev-shell dev-init-site dev-migrate dev-build dev-ps dev-destroy \
	prod-up prod-down prod-restart prod-logs prod-shell prod-migrate prod-ps \
	up-deploy down-deploy restart-deploy logs-deploy shell-deploy migrate-deploy ps-deploy \
	migrate-help migrate-check-origen migrate-check-destino \
	migrate-backup migrate-backup-cutover migrate-transfer migrate-restore migrate-test \
	dev-feature-on dev-feature-off dev-feature-status \
	prod-feature-on prod-feature-off prod-feature-status

## Alias legacy: entorno de desarrollo
up: dev-up

## Alias legacy: entorno de desarrollo
down: dev-down

## Alias legacy: entorno de desarrollo
restart: dev-restart

## Alias legacy: entorno de desarrollo
logs: dev-logs

## Alias legacy: entorno de desarrollo
shell: dev-shell

## Alias legacy: entorno de desarrollo
ps: dev-ps

## Alias legacy: entorno de desarrollo
init-site: dev-init-site

## Alias legacy: entorno de desarrollo
build: dev-build

## Alias legacy: entorno de desarrollo
migrate: dev-migrate

## Alias legacy: entorno de desarrollo
destroy: dev-destroy

## Levantar stack de DESARROLLO (bench start + hot-reload del app local)
dev-up:
	$(COMPOSE_DEV) up -d

## Detener stack de DESARROLLO
dev-down:
	$(COMPOSE_DEV) down

## Reiniciar backend de DESARROLLO
dev-restart:
	$(COMPOSE_DEV) restart backend

## Ver logs del backend de DESARROLLO
dev-logs:
	$(COMPOSE_DEV) logs -f backend

## Abrir shell dentro del backend de DESARROLLO
dev-shell:
	$(COMPOSE_DEV) exec backend bash

## Estado de contenedores de DESARROLLO
dev-ps:
	$(COMPOSE_DEV) ps

## Crear sitio e instalar hubgh en DESARROLLO
dev-init-site:
	$(COMPOSE_DEV) exec backend bash /create-site.sh

## Build assets en DESARROLLO (después de cambios en public/)
dev-build:
	$(COMPOSE_DEV) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench build --app hubgh"

## Correr migraciones de DB en DESARROLLO
dev-migrate:
	$(COMPOSE_DEV) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench --site $(SITE) migrate"

## Destruir TODO el entorno de DESARROLLO, incluyendo volumes
dev-destroy:
	$(COMPOSE_DEV) down -v

## Levantar stack de PRODUCCION (Gunicorn + workers + Caddy)
prod-up:
	$(COMPOSE_PROD) up -d

## Alias legacy: stack publico
up-deploy: prod-up

## Bajar stack de PRODUCCION
prod-down:
	$(COMPOSE_PROD) down

## Alias legacy: stack publico
down-deploy: prod-down

## Reiniciar backend y proxy de PRODUCCION
prod-restart:
	$(COMPOSE_PROD) restart backend caddy

## Alias legacy: stack publico
restart-deploy: prod-restart

## Ver logs de backend y proxy de PRODUCCION
prod-logs:
	$(COMPOSE_PROD) logs -f backend caddy

## Alias legacy: stack publico
logs-deploy: prod-logs

## Abrir shell dentro del backend de PRODUCCION
prod-shell:
	$(COMPOSE_PROD) exec backend bash

## Alias legacy: stack publico
shell-deploy: prod-shell

## Correr migraciones de DB en PRODUCCION
prod-migrate:
	$(COMPOSE_PROD) exec $(PROD_ENV) backend bash -c \
		'cd /home/frappe/frappe-bench && bench --site $${PROD_SITE:-$$(cat sites/currentsite.txt)} migrate'

## Alias legacy: stack publico
migrate-deploy: prod-migrate

## Estado de contenedores de PRODUCCION
prod-ps:
	$(COMPOSE_PROD) ps

## Alias legacy: stack publico
ps-deploy: prod-ps

# ───────────────────────────────────────────────────────────────────────────────
# FEATURE FLAGS — examen médico autogestionado
#
# El flag `hubgh_agendamiento_autogestionado_enabled` es un kill-switch en
# caliente: cuando está en 1 el dialog "Enviar a examen" en Selección
# muestra la opción "Autogestionado" (cita + correo + portal). Cuando está
# en 0 sólo aparece "Manual" y todo el flujo nuevo desaparece de la UI sin
# romper Selección — útil para apagar rápido si algo falla en producción.
#
# Uso:
#   make prod-feature-on              # encender en producción
#   make prod-feature-off             # apagar en producción
#   make prod-feature-status          # ver el estado actual
#   make dev-feature-on               # idem en desarrollo
#
# Los targets dev-feature-* usan SITE (de FRAPPE_SITE_NAME, default hubgh.local).
# Los targets prod-feature-* leen sites/currentsite.txt del container; override
# explícito con PROD_SITE=:
#   make prod-feature-on PROD_SITE=intranet.comidasvarpel.com
# ───────────────────────────────────────────────────────────────────────────────

## Encender el flujo autogestionado de examen médico en DESARROLLO
dev-feature-on:
	$(COMPOSE_DEV) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench --site $(SITE) set-config -p hubgh_agendamiento_autogestionado_enabled 1 && bench --site $(SITE) clear-cache"
	@echo "  OK autogestionado ENCENDIDO en $(SITE)"

## Apagar el flujo autogestionado de examen médico en DESARROLLO
dev-feature-off:
	$(COMPOSE_DEV) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench --site $(SITE) set-config -p hubgh_agendamiento_autogestionado_enabled 0 && bench --site $(SITE) clear-cache"
	@echo "  OK autogestionado APAGADO en $(SITE)"

## Mostrar el estado del flag en DESARROLLO (1=ON, 0/null=OFF)
dev-feature-status:
	@$(COMPOSE_DEV) exec backend bash -c \
		"cat /home/frappe/frappe-bench/sites/$(SITE)/site_config.json | grep -E 'hubgh_agendamiento_autogestionado_enabled|host_name' || echo '  (flag ausente — equivale a OFF)'"

## Encender el flujo autogestionado de examen médico en PRODUCCION
prod-feature-on:
	$(COMPOSE_PROD) exec $(PROD_ENV) backend bash -c \
		'cd /home/frappe/frappe-bench && SITE=$${PROD_SITE:-$$(cat sites/currentsite.txt)} && bench --site $$SITE set-config -p hubgh_agendamiento_autogestionado_enabled 1 && bench --site $$SITE clear-cache && echo "  OK autogestionado ENCENDIDO en $$SITE"'

## Apagar el flujo autogestionado de examen médico en PRODUCCION
prod-feature-off:
	$(COMPOSE_PROD) exec $(PROD_ENV) backend bash -c \
		'cd /home/frappe/frappe-bench && SITE=$${PROD_SITE:-$$(cat sites/currentsite.txt)} && bench --site $$SITE set-config -p hubgh_agendamiento_autogestionado_enabled 0 && bench --site $$SITE clear-cache && echo "  OK autogestionado APAGADO en $$SITE"'

## Mostrar el estado del flag en PRODUCCION (1=ON, 0/null=OFF)
prod-feature-status:
	@$(COMPOSE_PROD) exec $(PROD_ENV) backend bash -c \
		'SITE=$${PROD_SITE:-$$(cat /home/frappe/frappe-bench/sites/currentsite.txt)} && cat /home/frappe/frappe-bench/sites/$$SITE/site_config.json | grep -E "hubgh_agendamiento_autogestionado_enabled|host_name" || echo "  (flag ausente — equivale a OFF)"'

## Instalar navegador Firefox para Playwright E2E
e2e-install:
	npm install
	npx playwright install firefox

## Ejecutar E2E de candidato (onboarding + login + upload)
e2e-candidato:
	npm run e2e:candidato

# ───────────────────────────────────────────────────────────────────────────────
# MIGRACION VM -> VM (a prueba de tontos)
# Orden:
#   En VM ORIGEN:
#     1. make migrate-check-origen
#     2. make migrate-backup                       # backup en caliente, sin downtime
#     3. make migrate-transfer DEST=user@host:/p   # rsync al destino (idempotente)
#     ... (cuando estes listo para cutover)
#     4. make migrate-backup-cutover               # backup final + maintenance mode
#     5. make migrate-transfer DEST=user@host:/p   # transferir el backup final
#   En VM DESTINO:
#     6. make migrate-check-destino
#     7. make migrate-restore
#     8. (manual) cambiar DNS al IP de la VM destino
#
# Para testear localmente sin tocar prod: make migrate-test
# ───────────────────────────────────────────────────────────────────────────────

MIGRATION_DIR := docker/migration
BACKUP_ROOT   ?= ./backups
DEST          ?=

## Mostrar el orden exacto de la migracion VM -> VM
migrate-help:
	@echo ""
	@echo "  MIGRACION HAPPY NEST  (orden exacto, no te saltes pasos)"
	@echo "  ========================================================"
	@echo ""
	@echo "  EN VM ORIGEN:"
	@echo "    1. make migrate-check-origen"
	@echo "    2. make migrate-backup                            # sin downtime"
	@echo "    3. make migrate-transfer DEST=user@host:/path     # rsync al destino"
	@echo ""
	@echo "  >>> CUANDO ESTES LISTO PARA EL CUTOVER (downtime: minutos):"
	@echo ""
	@echo "    4. make migrate-backup-cutover                    # activa maintenance"
	@echo "    5. make migrate-transfer DEST=user@host:/path     # backup final"
	@echo ""
	@echo "  EN VM DESTINO:"
	@echo "    6. make migrate-check-destino"
	@echo "    7. make migrate-restore"
	@echo "    8. (manual) cambiar DNS al IP de esta VM"
	@echo ""
	@echo "  Variables override:"
	@echo "    SITE_NAME       (default: $(SITE))"
	@echo "    BACKUP_ROOT     (default: ./backups)"
	@echo "    DEST            (requerido en migrate-transfer)"
	@echo ""
	@echo "  Test local sin tocar prod:"
	@echo "    make migrate-test     # corre backup contra stack dev y valida"
	@echo ""

## Validar pre-requisitos en la VM ORIGEN antes de hacer backup
migrate-check-origen:
	@echo "[check-origen] Validando pre-requisitos..."
	@test -f docker/docker-compose.prod.yml || { echo "  X falta docker/docker-compose.prod.yml"; exit 1; }
	@test -f .env || { echo "  X falta .env en la raiz"; exit 1; }
	@command -v rsync >/dev/null 2>&1 || { echo "  X falta rsync (sudo apt install rsync)"; exit 1; }
	@$(COMPOSE_PROD) ps backend --status running --quiet | grep -q . || { echo "  X servicio backend no esta corriendo (make prod-up)"; exit 1; }
	@test -x $(MIGRATION_DIR)/backup.sh || chmod +x $(MIGRATION_DIR)/backup.sh
	@test -x $(MIGRATION_DIR)/transfer.sh || chmod +x $(MIGRATION_DIR)/transfer.sh
	@echo "  OK origen listo para backup"

## Validar pre-requisitos en la VM DESTINO antes del restore
migrate-check-destino:
	@echo "[check-destino] Validando pre-requisitos..."
	@test -f docker/docker-compose.prod.yml || { echo "  X falta docker/docker-compose.prod.yml"; exit 1; }
	@test -f .env || { echo "  X falta .env en la raiz (copialo con scp desde origen)"; exit 1; }
	@grep -q '^MARIADB_ROOT_PASSWORD=' .env || { echo "  X .env no tiene MARIADB_ROOT_PASSWORD"; exit 1; }
	@grep -q '^PUBLIC_DOMAIN=' .env || { echo "  X .env no tiene PUBLIC_DOMAIN"; exit 1; }
	@grep -q '^ACME_EMAIL=' .env || { echo "  X .env no tiene ACME_EMAIL"; exit 1; }
	@test -d restore-staging || { echo "  X falta directorio restore-staging/ (corre migrate-transfer desde origen primero)"; exit 1; }
	@test -x $(MIGRATION_DIR)/restore.sh || chmod +x $(MIGRATION_DIR)/restore.sh
	@echo "  OK destino listo para restore"

## Backup en caliente (sin downtime). Genera ./backups/backup-<TS>/
migrate-backup:
	@bash $(MIGRATION_DIR)/backup.sh

## Backup final con maintenance mode — solo en cutover
migrate-backup-cutover:
	@bash $(MIGRATION_DIR)/backup.sh --maintenance

## Sincronizar el backup mas reciente al destino. Requiere DEST=user@host:/path
migrate-transfer:
	@if [ -z "$(DEST)" ]; then \
		echo "ERROR: falta DEST."; \
		echo "Ejemplo: make migrate-transfer DEST=ubuntu@10.0.0.5:/opt/hubgh/masterhubgh/restore-staging"; \
		exit 1; \
	fi
	@LATEST=$$(ls -d $(BACKUP_ROOT)/backup-* 2>/dev/null | sort | tail -1); \
	if [ -z "$$LATEST" ]; then \
		echo "ERROR: no hay backups en $(BACKUP_ROOT)/. Corre 'make migrate-backup' primero."; \
		exit 1; \
	fi; \
	echo "[transfer] mas reciente: $$LATEST"; \
	bash $(MIGRATION_DIR)/transfer.sh "$$LATEST" "$(DEST)"

## Restaurar en VM destino. Lee ./restore-staging y levanta el stack.
migrate-restore:
	@bash $(MIGRATION_DIR)/restore.sh

## Test local NO destructivo: backup contra stack dev y valida los 4 archivos
migrate-test:
	@echo "[test] Validando que el stack dev este corriendo..."
	@$(COMPOSE_DEV) ps backend --status running --quiet | grep -q . || { \
		echo "  Levantando stack dev primero..."; \
		$(COMPOSE_DEV) up -d; \
		echo "  Esperando 30s a que arranquen los servicios..."; \
		sleep 30; \
	}
	@echo "[test] Corriendo backup contra dev (no toca prod)..."
	@COMPOSE_FILE=docker/docker-compose.dev.yml \
	 BACKUP_ROOT=./backups-test \
	 SITE_NAME=$(SITE) \
	 bash $(MIGRATION_DIR)/backup.sh
	@echo "[test] OK backup generado y validado en ./backups-test/"
