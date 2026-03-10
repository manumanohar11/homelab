.PHONY: help init-env up down pull restart logs ps config validate check sync-config

PROFILES ?=
SERVICE ?=
TAIL ?= 200
PROFILE_ARGS := $(foreach profile,$(PROFILES),--profile $(profile))

help:
	@printf '%s\n' \
		'Common targets:' \
		'  make up PROFILES="arr monitoring" SERVICE=plex' \
		'  make init-env' \
		'  make down' \
		'  make pull SERVICE=plex' \
		'  make restart SERVICE=plex' \
		'  make logs SERVICE=plex TAIL=200' \
		'  make ps' \
		'  make config PROFILES="arr monitoring"' \
		'  make validate' \
		'  make check' \
		'  make sync-config'

init-env:
	python3 scripts/init-env.py

up:
	docker compose $(PROFILE_ARGS) up -d $(SERVICE)

down:
	docker compose down

pull:
	docker compose $(PROFILE_ARGS) pull $(SERVICE)

restart:
	docker compose restart $(SERVICE)

logs:
	docker compose logs -f --tail=$(TAIL) $(SERVICE)

ps:
	docker compose ps

config:
	docker compose $(PROFILE_ARGS) config

validate:
	python3 scripts/validate-stack.py

check:
	./scripts/sync-monitoring-config.sh --check
	python3 scripts/validate-stack.py

sync-config:
	./scripts/sync-monitoring-config.sh
