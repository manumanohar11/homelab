# Repository Scripts

These scripts are maintainer-facing unless noted otherwise.

## User-Facing

- `scripts/init-env.py`
  - Wrapped by `make init`
  - Creates `.env` from `.env.example`
  - Optionally appends bundle settings from `env/bundles/*.env.example`
  - Generates starter or bundle secrets when they are missing
- `scripts/bootstrap-host.py`
  - Wrapped by `make prep-dirs`
  - Resolves the current starter or bundle-aware compose config
  - Creates missing bind-mount directories for the selected bundles and profiles

## Maintainer-Facing

- `scripts/validate-stack.py`
  - Validates the starter stack, each bundle, the full stack, markdown links, and Docmost output
- `scripts/build-docmost-space.py`
  - Builds the import-ready Docmost bundle under `build/docmost-space/`
- `scripts/sync-monitoring-config.sh`
  - Syncs tracked monitoring/logging templates into `${DOCKER_BASE_DIR}`
- `scripts/setup-logging.sh`
  - Compatibility wrapper around `scripts/sync-monitoring-config.sh`
- `scripts/homarr_seed.py`
  - Applies the curated Homarr board to the resolved starter or bundle-aware compose config
  - Supports `--bundle`, `--profile`, and `--dry-run` for previewing advanced layouts
