# HubGH -- Comandos de operacion Docker
# Todos los comandos usan el .env de la raiz del repo.
# Compatible con Docker Compose v1 (docker-compose) y v2 (docker compose).

# Carga .env como variables Make (evita problemas de escaping con $$ en bash -c)
-include .env
export

FRAPPE_SITE_NAME ?= hubgh.local
SITE             := $(FRAPPE_SITE_NAME)

DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE_DEV = $(DOCKER_COMPOSE) -f docker/docker-compose.dev.yml --env-file .env
COMPOSE_PROD = $(DOCKER_COMPOSE) -f docker/docker-compose.prod.yml --env-file .env

.PHONY: \
	up down restart logs shell init-site migrate build ps destroy \
	e2e-install e2e-candidato \
	dev-up dev-down dev-restart dev-logs dev-shell dev-init-site dev-migrate dev-build dev-ps dev-destroy \
	prod-up prod-down prod-restart prod-logs prod-shell prod-migrate prod-ps \
	up-deploy down-deploy restart-deploy logs-deploy shell-deploy migrate-deploy ps-deploy

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
	$(COMPOSE_PROD) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench --site $(SITE) migrate"

## Alias legacy: stack publico
migrate-deploy: prod-migrate

## Estado de contenedores de PRODUCCION
prod-ps:
	$(COMPOSE_PROD) ps

## Alias legacy: stack publico
ps-deploy: prod-ps

## Instalar navegador Firefox para Playwright E2E
e2e-install:
	npm install
	npx playwright install firefox

## Ejecutar E2E de candidato (onboarding + login + upload)
e2e-candidato:
	npm run e2e:candidato
