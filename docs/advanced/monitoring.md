# Advanced Monitoring

[Back to README](../../README.md)

Monitoring lives in the `ops` bundle.

## Start It

```bash
make init BUNDLES="ops"
make up BUNDLES="ops" PROFILES="monitoring"
```

Base ops services already include Prometheus, Alertmanager, Grafana, Node Exporter, Uptime Kuma, Loki, and Promtail.

`monitoring` adds Glances.

`dashboard` adds Glance.

If you need to sync tracked monitoring config into runtime paths, use:

```bash
make sync-config
```

Use that only after changing tracked monitoring or logging templates that need copying into `${DOCKER_BASE_DIR}`.

That is a maintainer/operator task, not part of the beginner path or a normal day-to-day restart.
