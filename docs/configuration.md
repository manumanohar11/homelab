# Configuration

[Back to README](../README.md)

The repo now has one default entrypoint and four optional bundles.

## Compose Entry Points

| File | Purpose |
|:-----|:--------|
| `docker-compose.yml` | Starter stack only |
| `docker-compose.media.yml` | VPN, *Arr, downloaders, requests, alternate media apps |
| `docker-compose.apps.yml` | Productivity, documents, files, automation |
| `docker-compose.ops.yml` | Monitoring, logging, diagnostics, advanced backups |
| `docker-compose.access.yml` | Pangolin/Newt remote access |
| `docker-compose.common.yml` | Shared helper definitions used by compose services |
| `docker-compose.local.example.yml` | Host-specific override example |

## Starter Path

The supported beginner path is:

```bash
make init
docker compose up -d
```

Do not comment compose includes to enable features. Add bundles instead.

## Bundle-Aware Commands

```bash
make init BUNDLES="media apps"
make up BUNDLES="media apps" PROFILES="arr jellyfin"
make config BUNDLES="ops" PROFILES="monitoring"
make pull BUNDLES="access"
```

## Environment Files

| File | Scope |
|:-----|:------|
| `.env.example` | Starter-only variables |
| `env/bundles/media.env.example` | Media bundle variables |
| `env/bundles/apps.env.example` | Apps bundle variables |
| `env/bundles/ops.env.example` | Ops bundle variables |
| `env/bundles/access.env.example` | Access bundle variables |

`make init` creates `.env` from `.env.example`.

`make init BUNDLES="..."` appends any missing variables from the selected bundle templates and initializes that bundle's generated secrets.

## Validation

Use the resolved config before every first start or major bundle change:

```bash
docker compose config
make config BUNDLES="media" PROFILES="arr jellyfin"
make validate
```

`make validate` is the maintainer-grade check that exercises starter and bundle scenarios.

## Update Policy

`watchtower` now updates only services that explicitly keep `com.centurylinklabs.watchtower.enable=true`.

Sensitive services stay label-disabled by default so upgrades happen intentionally, after release-note review and backups.

## Docker API Access

Most starter and ops dashboards use the filtered `docker-socket-proxy` service.

Direct Docker socket mounts remain only where the upstream app needs broader Docker API access, such as `portainer`, `watchtower`, `newt`, and `promtail`.

## Profiles

Profiles still exist, but only inside the bundle that owns them.

| Bundle | Profiles |
|:-------|:---------|
| `media` | `arr`, `downloaders`, `requests`, `jellyfin`, `stash`, `kavita`, `navidrome`, `tdarr`, `maintainerr`, `notifiarr` |
| `apps` | `kasm`, `files`, `automation` |
| `ops` | `monitoring`, `dashboard`, `speedtest`, `scrutiny`, `restic`, `db-backup` |
| `access` | None |

## Host Overrides

If you need host-specific mounts or devices, copy `docker-compose.local.example.yml` to `docker-compose.local.yml` and add it to your own local compose workflow. The tracked repo no longer uses commented include toggles for this.
