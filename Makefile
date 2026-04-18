.PHONY: help init init-env bootstrap prep-dirs up down pull restart logs ps config validate check sync-config docs-build

BUNDLES ?=
PROFILES ?=
SERVICE ?=
TAIL ?= 200

BUNDLE_ARGS := -f docker-compose.yml $(foreach bundle,$(BUNDLES),-f docker-compose.$(bundle).yml)
PROFILE_ARGS := $(foreach profile,$(PROFILES),--profile $(profile))
INIT_BUNDLE_ARGS := $(foreach bundle,$(BUNDLES),--bundle $(bundle))
BOOTSTRAP_PROFILE_ARGS := $(foreach profile,$(PROFILES),--profile $(profile))

help:
	@printf '%s\n' \
		'Starter path:' \
		'  make init' \
		'  make prep-dirs' \
		'  make bootstrap' \
		'  docker compose up -d' \
		'' \
		'Bundle-aware commands:' \
		'  make init BUNDLES="media apps"' \
		'  make up BUNDLES="media" PROFILES="arr jellyfin"' \
		'  make config BUNDLES="ops" PROFILES="monitoring"' \
		'  make pull BUNDLES="access"' \
		'' \
		'Maintainer commands:' \
		'  make validate' \
		'  make check' \
		'  make docs-build' \
		'  make sync-config'

init:
	python3 scripts/init-env.py $(INIT_BUNDLE_ARGS)

init-env: init

prep-dirs:
	python3 scripts/bootstrap-host.py $(INIT_BUNDLE_ARGS) $(BOOTSTRAP_PROFILE_ARGS)

bootstrap: init prep-dirs

up:
	docker compose $(BUNDLE_ARGS) $(PROFILE_ARGS) up -d $(SERVICE)

down:
	docker compose $(BUNDLE_ARGS) down

pull:
	docker compose $(BUNDLE_ARGS) $(PROFILE_ARGS) pull $(SERVICE)

restart:
	docker compose $(BUNDLE_ARGS) $(PROFILE_ARGS) restart $(SERVICE)

logs:
	docker compose $(BUNDLE_ARGS) $(PROFILE_ARGS) logs -f --tail=$(TAIL) $(SERVICE)

ps:
	docker compose $(BUNDLE_ARGS) $(PROFILE_ARGS) ps

config:
	docker compose $(BUNDLE_ARGS) $(PROFILE_ARGS) config

validate:
	python3 scripts/validate-stack.py

check:
	python3 scripts/validate-stack.py

docs-build:
	python3 scripts/build-docmost-space.py

sync-config:
	./scripts/sync-monitoring-config.sh
