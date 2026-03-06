# Repository Scripts

Shared maintenance scripts for the homelab stack.

## Available Scripts

- `scripts/setup-logging.sh` - Sync tracked logging and monitoring templates from `config-templates/` into `${DOCKER_BASE_DIR}` and create the required runtime directories.
- `scripts/validate-stack.py` - Validate compose modules, documented profiles, stale doc references, and accidentally tracked local artifacts.

## Common Usage

```bash
# Sync logging templates into runtime config directories
./scripts/setup-logging.sh

# Check whether runtime logging configs drifted from tracked templates
./scripts/setup-logging.sh --check

# Validate compose and documentation consistency
python3 scripts/validate-stack.py
```
