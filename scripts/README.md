# Repository Scripts

Shared maintenance scripts for the homelab stack.

## Available Scripts

- `scripts/init-env.py` - Create `.env` from `.env.example` when needed and generate any missing required secrets for first-time startup.
- `scripts/sync-monitoring-config.sh` - Sync tracked monitoring and logging templates from `config-templates/` into `${DOCKER_BASE_DIR}` and create the required runtime directories.
- `scripts/setup-logging.sh` - Backward-compatible wrapper for `scripts/sync-monitoring-config.sh`.
- `scripts/build-docmost-space.py` - Generate the import-ready `docs/docmost-space/` wiki bundle for Docmost.
- `scripts/validate-stack.py` - Validate compose modules, documented profiles, markdown links, Docmost bundle freshness, stale doc references, and accidentally tracked local artifacts.

## Common Usage

```bash
# Bootstrap .env for first-time setup
python3 scripts/init-env.py

# Sync monitoring and logging templates into runtime config directories
./scripts/sync-monitoring-config.sh

# Check whether runtime configs drifted from tracked templates
./scripts/sync-monitoring-config.sh --check

# Rebuild the import-ready Docmost bundle
python3 scripts/build-docmost-space.py

# Validate compose and documentation consistency
python3 scripts/validate-stack.py
```
