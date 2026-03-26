# HubGH -- Comandos de operacion Docker
# Todos los comandos usan el .env de la raiz del repo.
# Compatible con Docker Compose v1 (docker-compose) y v2 (docker compose).

DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE = $(DOCKER_COMPOSE) -f docker/docker-compose.yml --env-file .env

.PHONY: up down restart logs shell init-site migrate ps destroy

## Levantar todos los servicios (primera vez: ~15 min por bench init)
up:
	$(COMPOSE) up -d

## Detener y eliminar contenedores (los volumes con datos persisten)
down:
	$(COMPOSE) down

## Reiniciar solo el backend (para aplicar cambios de codigo)
restart:
	$(COMPOSE) restart backend

## Ver logs del backend en tiempo real
logs:
	$(COMPOSE) logs -f backend

## Abrir shell dentro del contenedor backend
shell:
	$(COMPOSE) exec backend bash

## Estado de los contenedores
ps:
	$(COMPOSE) ps

## Crear sitio e instalar app hubgh (solo la primera vez, despues de "make up")
init-site:
	$(COMPOSE) exec backend bash /create-site.sh

## Correr migraciones de DB (despues de actualizar codigo con cambios de schema)
migrate:
	$(COMPOSE) exec backend bash -c 		"cd /home/frappe/frappe-bench && bench --site $$${FRAPPE_SITE_NAME:-hubgh.local} migrate"

## Destruir TODO incluyendo volumes (CUIDADO: borra la base de datos)
destroy:
	$(COMPOSE) down -v
