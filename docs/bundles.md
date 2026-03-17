# Bundles

[Back to README](../README.md)

Bundles keep the beginner path small while leaving the full homelab available.

## Media

Adds Gluetun, the *Arr stack, downloaders, request apps, and alternate media services.

```bash
make init BUNDLES="media"
make up BUNDLES="media" PROFILES="arr jellyfin"
```

Uses `env/bundles/media.env.example`.

Common profile combinations:

- `arr`: Radarr, Sonarr, Lidarr, Readarr, Bazarr, Whisparr, Recyclarr, qBittorrent, Prowlarr, Bitmagnet, Overseerr
- `jellyfin`: Jellyfin and Jellyseerr
- `kavita`, `navidrome`, `stash`, `tdarr`, `maintainerr`, `notifiarr`

## Apps

Adds productivity, document, knowledge, file-sharing, and automation services.

```bash
make init BUNDLES="apps"
make up BUNDLES="apps"
make up BUNDLES="apps" PROFILES="files automation kasm"
```

Uses `env/bundles/apps.env.example`.

Unprofiled apps in this bundle include FreshRSS, SearXNG, Syncthing, Joplin, Paperless-ngx, Stirling PDF, Karakeep, and Docmost.

## Ops

Adds monitoring, logging, diagnostics, and advanced backup endpoints.

```bash
make init BUNDLES="ops"
make up BUNDLES="ops" PROFILES="monitoring"
make up BUNDLES="ops" PROFILES="monitoring dashboard speedtest scrutiny"
```

Uses `env/bundles/ops.env.example`.

Base ops services include Prometheus, Alertmanager, Grafana, Node Exporter, Uptime Kuma, Loki, and Promtail.

## Access

Adds Pangolin/Newt and the Jitsi private calling stack.

```bash
make init BUNDLES="access"
make up BUNDLES="access" PROFILES="jitsi"
```

Uses `env/bundles/access.env.example`.

Newt is part of the access bundle. Jitsi, coturn, and the DDNS updater remain behind the `jitsi` profile.
