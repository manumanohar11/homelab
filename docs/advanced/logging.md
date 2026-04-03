# Advanced Logging

[Back to README](../../README.md)

Logging lives in the `ops` bundle through Loki and Promtail.

## Start It

```bash
make init BUNDLES="ops"
make up BUNDLES="ops"
```

That starts the base `ops` bundle, including logging plus the other always-on ops services.

If you only want the fully optional extras, add profiles on top of the same bundle command.

If you change tracked Promtail or Loki templates, run:

```bash
make sync-config
```

Use `make sync-config` when you change tracked files under `config-templates/` and need those updates copied into `${DOCKER_BASE_DIR}` runtime paths.

If you have not changed tracked templates, you do not need to run it for a normal bundle start.
