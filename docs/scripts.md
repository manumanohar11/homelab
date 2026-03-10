# Utility Scripts

[← Back to README](../README.md)

Shared utility scripts for keeping the homelab stack organized and consistent.

---

## Available Scripts

### `scripts/init-env.py`

Creates `.env` from `.env.example` if it does not exist and generates any missing required secrets needed for `docker compose up -d`.

```bash
python3 scripts/init-env.py
```

### `scripts/sync-monitoring-config.sh`

Syncs the tracked monitoring and logging templates from `config-templates/` into `${DOCKER_BASE_DIR}` and creates any missing runtime directories.

```bash
# Sync tracked templates into runtime config directories
./scripts/sync-monitoring-config.sh

# Check whether runtime configs drifted from tracked templates
./scripts/sync-monitoring-config.sh --check
```

### `scripts/setup-logging.sh`

Compatibility wrapper that forwards to `scripts/sync-monitoring-config.sh`.

### `scripts/validate-stack.py`

Runs repository validation checks for:

- duplicate service names across compose modules
- documented profile drift in `docker-compose.yml`, `docs/configuration.md`, and `.env.example`
- stale doc references to removed services or tooling
- accidentally tracked local artifacts under `scripts/`

```bash
python3 scripts/validate-stack.py
```

---

## Recommended Workflow

```bash
# 1. Bootstrap .env if this is a first-time checkout
python3 scripts/init-env.py

# 2. Update templates or compose files
$EDITOR config-templates/prometheus/prometheus.yml

# 3. Sync tracked templates into runtime directories
./scripts/sync-monitoring-config.sh

# 4. Validate compose and documentation consistency
python3 scripts/validate-stack.py

# 5. Validate the rendered stack
docker compose config --quiet
```
