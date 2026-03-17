# Advanced Logging

[Back to README](../../README.md)

Logging lives in the `ops` bundle through Loki and Promtail.

## Start It

```bash
make init BUNDLES="ops"
make up BUNDLES="ops"
```

If you change tracked Promtail or Loki templates, run:

```bash
make sync-config
```

The generated runtime config belongs under `${DOCKER_BASE_DIR}`. The tracked templates stay under `config-templates/`.
