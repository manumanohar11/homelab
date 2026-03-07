# Utility Scripts

[← Back to README](../README.md)

Shared utility scripts for keeping the homelab stack organized and consistent.

---

## Available Scripts

### `scripts/setup-logging.sh`

Syncs the tracked logging and monitoring templates from `config-templates/` into `${DOCKER_BASE_DIR}` and creates any missing runtime directories.

```bash
# Sync tracked templates into runtime config directories
./scripts/setup-logging.sh

# Check whether runtime configs drifted from tracked templates
./scripts/setup-logging.sh --check
```

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
# 1. Update templates or compose files
$EDITOR config-templates/prometheus/prometheus.yml

# 2. Sync tracked templates into runtime directories
./scripts/setup-logging.sh

# 3. Validate compose and documentation consistency
python3 scripts/validate-stack.py

# 4. Validate the rendered stack
docker compose config --quiet
```
