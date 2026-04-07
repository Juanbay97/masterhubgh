# HubGH -- Comandos de operacion Docker
# Todos los comandos usan el .env de la raiz del repo.
# Compatible con Docker Compose v1 (docker-compose) y v2 (docker compose).

# Carga .env como variables Make (evita problemas de escaping con $$ en bash -c)
-include .env
export

FRAPPE_SITE_NAME ?= hubgh.local
SITE             := $(FRAPPE_SITE_NAME)

DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE = $(DOCKER_COMPOSE) -f docker/docker-compose.yml --env-file .env
COMPOSE_DEPLOY = $(DOCKER_COMPOSE) -f docker/docker-compose.deploy.yml --env-file .env

.PHONY: up down restart logs shell init-site migrate build ps destroy e2e-install e2e-candidato up-deploy down-deploy restart-deploy logs-deploy ps-deploy

## Levantar todos los servicios (primera vez: ~15 min por bench init)
up:
	$(COMPOSE) up -d

## Levantar stack publico con Caddy al frente (HTTPS)
up-deploy:
	$(COMPOSE_DEPLOY) up -d

## Detener y eliminar contenedores (los volumes con datos persisten)
down:
	$(COMPOSE) down

## Bajar stack publico con Caddy
down-deploy:
	$(COMPOSE_DEPLOY) down

## Reiniciar solo el backend (para aplicar cambios de codigo)
restart:
	$(COMPOSE) restart backend

## Reiniciar backend y proxy publico
restart-deploy:
	$(COMPOSE_DEPLOY) restart backend caddy

## Ver logs del backend en tiempo real
logs:
	$(COMPOSE) logs -f backend

## Ver logs del backend y proxy publico
logs-deploy:
	$(COMPOSE_DEPLOY) logs -f backend caddy

## Abrir shell dentro del contenedor backend
shell:
	$(COMPOSE) exec backend bash

## Estado de los contenedores
ps:
	$(COMPOSE) ps

## Estado del stack publico
ps-deploy:
	$(COMPOSE_DEPLOY) ps

## Crear sitio e instalar app hubgh (solo la primera vez, despues de "make up")
init-site:
	$(COMPOSE) exec backend bash /create-site.sh

## Build assets de la app (CSS/JS — correr despues de cambios en public/)
build:
	$(COMPOSE) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench build --app hubgh"

## Correr migraciones de DB (despues de actualizar codigo con cambios de schema)
migrate:
	$(COMPOSE) exec backend bash -c \
		"cd /home/frappe/frappe-bench && bench --site $(SITE) migrate"

## Instalar navegador Firefox para Playwright E2E
e2e-install:
	npm install
	npx playwright install firefox

## Ejecutar E2E de candidato (onboarding + login + upload)
e2e-candidato:
	npm run e2e:candidato

## Destruir TODO incluyendo volumes (CUIDADO: borra la base de datos)
destroy:
	$(COMPOSE) down -v
