# Maintainer Scripts

[Back to README](../../README.md)

The only script in the beginner workflow is `make init`, which wraps `scripts/init-env.py`.

Everything else here is maintainer-only:

- `scripts/validate-stack.py`
- `scripts/build-docmost-space.py`
- `scripts/sync-monitoring-config.sh`
- `scripts/setup-logging.sh`
- `scripts/homarr_seed.py`

Use these only when maintaining the repo, validating docs, or publishing Docmost content.

`scripts/homarr_seed.py` now follows the same compose model as the rest of the repo:

```bash
# Preview the starter board only
python3 scripts/homarr_seed.py --dry-run

# Preview a richer board that includes media automation and Jellyfin
python3 scripts/homarr_seed.py --bundle media --profile arr --profile jellyfin --dry-run

# Apply the seeded board to Homarr after previewing it
python3 scripts/homarr_seed.py --bundle media --profile arr --profile jellyfin
```
