# 📦 Services Catalog

[← Back to README](../README.md)

Complete catalog of the services available in the Media Stack.

---

## Table of Contents

- [Status Legend](#status-legend)
- [Core Services](#core-services)
- [Media Servers](#media-servers)
- [Photo Management](#photo-management)
- [Media Management (*Arr Stack)](#media-management-arr-stack)
- [Downloaders](#downloaders)
- [Request Management](#request-management)
- [Monitoring & Observability](#monitoring--observability)
- [Management & Utilities](#management--utilities)
- [Productivity](#productivity)
- [Documents & Knowledge](#documents--knowledge)
- [Backup Services](#backup-services)
- [Automation](#automation)
- [File Sharing](#file-sharing)

---

## Status Legend

| Symbol | Meaning | How to Enable |
|:------:|:--------|:--------------|
| ✅ | Enabled by default | Already running |
| 📦 | Optional profile | `--profile <name>` |

---

## Core Services

Essential infrastructure services that other services depend on.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Docker Socket Proxy** | - | Secure Docker API access | `tecnativa/docker-socket-proxy` | ✅ |
| **Gluetun** | 8888 | VPN gateway (Mullvad/NordVPN/PIA) | `qmcgaw/gluetun` | ✅ |
| **Newt** | - | Pangolin secure tunnel | `ghcr.io/fosrl/newt` | ✅ |

### Docker Socket Proxy

Provides secure, read-only access to the Docker API for services that need container information.

```yaml
# Allowed operations (read-only)
CONTAINERS: 1
SERVICES: 1
TASKS: 1
NETWORKS: 1
```

### Gluetun VPN

Routes traffic for download-related services through a VPN tunnel.

**Supported Providers:** Mullvad, NordVPN, Private Internet Access, Surfshark, and [many more](https://github.com/qdm12/gluetun-wiki).

---

## Media Servers

Stream your media to any device.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Plex** | 32400 | Premium media server with GPU transcoding | `linuxserver/plex` | ✅ |
| **Jellyfin** | 8096 | Open-source media server | `lscr.io/linuxserver/jellyfin` | 📦 `jellyfin` |
| **Kavita** | 5000 | Ebook & comic reader | `lscr.io/linuxserver/kavita` | 📦 `kavita` |
| **Navidrome** | 4533 | Music streaming (Subsonic compatible) | `deluan/navidrome` | 📦 `navidrome` |
| **Stash** | 9999 | Adult media organizer | `stashapp/stash` | 📦 `stash` |
| **Tdarr** | 8265 | Distributed media transcoding | `ghcr.io/haveagitgat/tdarr` | 📦 `tdarr` |

### Plex

The primary media server with:
- GPU hardware transcoding (NVIDIA/Intel)
- Mobile apps and smart TV support
- Plex Pass features (optional)

**Default URL:** `http://your-server:32400/web`

### Jellyfin

Free and open-source alternative to Plex:
- No subscription required
- Full feature set out of the box
- Active community development

**Enable:** `docker compose --profile jellyfin up -d`

---

## Photo Management

Self-hosted Google Photos alternative.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Immich Server** | 2283 | Photo management web UI & API | `ghcr.io/immich-app/immich-server` | ✅ |
| **Immich ML** | - | Machine learning (face/object detection) | `ghcr.io/immich-app/immich-machine-learning` | ✅ |
| **PostgreSQL** | 5432 | Immich database | `tensorchord/pgvecto-rs` | ✅ |
| **Redis** | 6379 | Immich cache | `redis:alpine` | ✅ |

### Features

- Mobile app backup (iOS/Android)
- Face recognition & clustering
- Object detection & search
- Location mapping
- Shared albums
- External library support

**Default URL:** `http://your-server:2283`

> ⚠️ **Note:** Immich is excluded from Watchtower auto-updates. Update manually to ensure database migrations complete properly.

---

## Media Management (*Arr Stack)

Automated media library management.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Radarr** | 7878 | Movie collection manager | `linuxserver/radarr` | 📦 `arr` |
| **Sonarr** | 8989 | TV show collection manager | `linuxserver/sonarr` | 📦 `arr` |
| **Lidarr** | 8686 | Music collection manager | `linuxserver/lidarr` | 📦 `arr` |
| **Readarr** | 8787 | Book collection manager | `linuxserver/readarr` | 📦 `arr` |
| **Bazarr** | 6767 | Subtitle manager | `linuxserver/bazarr` | 📦 `arr` |
| **Whisparr** | 6969 | Adult content manager | `ghcr.io/hotio/whisparr` | 📦 `arr` |
| **Recyclarr** | - | TRaSH Guide sync | `ghcr.io/recyclarr/recyclarr` | 📦 `arr` |

### Enable *Arr Stack

1. Enable the profile with `docker compose --profile arr up -d`
2. Configure VPN credentials in `.env`
3. Add `--profile requests` too if you want Overseerr at the same time

All *Arr services route through Gluetun VPN for privacy.

### Recyclarr

Automatically syncs quality profiles and custom formats from [TRaSH Guides](https://trash-guides.info/).

---

## Downloaders

Content acquisition services (VPN-routed).

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **qBittorrent** | 8080 | Torrent client | `linuxserver/qbittorrent` | 📦 `arr` / `downloaders` |
| **Prowlarr** | 9696 | Indexer manager | `linuxserver/prowlarr` | 📦 `arr` / `downloaders` |
| **FlareSolverr** | 8191 | Cloudflare bypass | `ghcr.io/flaresolverr/flaresolverr` | 📦 `arr` / `downloaders` |
| **Bitmagnet** | 3333 | DHT crawler | `ghcr.io/bitmagnet-io/bitmagnet` | 📦 `arr` / `downloaders` |

### Enable Downloaders

1. Enable downloaders with `docker compose --profile downloaders up -d`
2. Configure VPN in `.env`:
   ```bash
   VPN_SERVICE_PROVIDER=mullvad
   OPENVPN_USER=your_account
   ```
3. Or use `docker compose --profile arr up -d` to start them together with the *Arr apps

> ⚠️ **Important:** Always use VPN for downloading. All traffic routes through Gluetun.

---

## Request Management

User-facing request portals and media tools.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Overseerr** | 5055 | Media request portal (Plex) | `lscr.io/linuxserver/overseerr` | 📦 `requests` |
| **Jellyseerr** | 5056 | Media request portal (Jellyfin) | `fallenbagel/jellyseerr` | 📦 `jellyfin` |
| **Maintainerr** | 6246 | Automated media cleanup | `ghcr.io/jorenn92/maintainerr` | 📦 `maintainerr` |
| **Tautulli** | 8181 | Plex statistics & monitoring | `lscr.io/linuxserver/tautulli` | ✅ |
| **Notifiarr** | 5454 | Unified notifications | `golift/notifiarr` | 📦 `notifiarr` |

### Overseerr

Allows users to:
- Browse trending movies/shows
- Request new content
- Track request status
- Integrates with Radarr/Sonarr

**Default URL:** `http://your-server:5055`

### Maintainerr

Automated cleanup based on rules:
- Remove unwatched content after X days
- Keep content with minimum ratings
- Exclude favorited items

---

## Monitoring & Observability

Track system health and performance.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Prometheus** | 9090 | Metrics collection & storage | `prom/prometheus` | ✅ |
| **Grafana** | 3000 | Visualization dashboards | `grafana/grafana` | ✅ |
| **AlertManager** | 9093 | Alert routing scaffold | `prom/alertmanager` | ✅ |
| **Node Exporter** | 9100 | System metrics | `prom/node-exporter` | ✅ |
| **Uptime Kuma** | 3001 | Uptime monitoring | `louislam/uptime-kuma` | ✅ |
| **Speedtest Tracker** | 8765 | Internet speed history | `linuxserver/speedtest-tracker` | 📦 `speedtest` |
| **Scrutiny** | 8082 | Disk S.M.A.R.T. health | `ghcr.io/analogj/scrutiny` | 📦 `scrutiny` |
| **Glances** | 61208 | System resource monitor | `nicolargo/glances` | 📦 `monitoring` |

### Grafana Dashboards

Pre-configured dashboards for:
- Docker container overview
- System metrics (CPU, RAM, disk, network)
- Plex streaming statistics
- Immich photo metrics

**Default Login:** admin / admin

### Scrutiny

Monitor disk health with:
- S.M.A.R.T. attribute tracking
- Temperature monitoring
- Failure prediction

**Enable:** `docker compose --profile scrutiny up -d`

---

## Management & Utilities

Container management and utility tools.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Portainer** | 9443 | Container management UI | `portainer/portainer-ce` | ✅ |
| **Watchtower** | - | Auto container updates | `containrrr/watchtower` | ✅ |
| **Homarr** | 3002 | Browser-managed dashboard | `ghcr.io/homarr-labs/homarr` | ✅ |
| **Dozzle** | 8889 | Real-time log viewer | `amir20/dozzle` | ✅ |
| **Glance** | 8088 | Alternative dashboard | `glanceapp/glance` | 📦 `dashboard` |

### Portainer

Full container management:
- Start/stop/restart containers
- View logs and stats
- Manage networks and volumes
- Stack deployment

**Default URL:** `https://your-server:9443`

### Watchtower

Automatic updates:
- Daily checks at 4 AM
- Rolling restarts
- Notification support

**Excluded:** Immich (manual updates recommended)

### Homarr

Browser-managed dashboard with:
- Drag-and-drop boards and app groups
- Docker integration through the socket proxy
- Multiple boards for daily use and admin views

---

## Productivity

Daily-driver services for reading, search, sync, notes, and optional browser workspaces.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **FreshRSS** | 8081 | Self-hosted RSS reader | `lscr.io/linuxserver/freshrss` | ✅ |
| **SearXNG** | 8084 | Private metasearch engine | `searxng/searxng` | ✅ |
| **SearXNG Valkey** | 6379 | Internal cache and rate-limit backend | `valkey/valkey` | ✅ |
| **Syncthing** | 8384 / 22000 / 21027 | Sync UI plus sync/discovery traffic | `lscr.io/linuxserver/syncthing` | ✅ |
| **Joplin** | 22300 | Notes sync server and API | `joplin/server` | ✅ |
| **Joplin PostgreSQL** | 5432 | Internal database for Joplin Server | `postgres:16-alpine` | ✅ |
| **Kasm** | 3003 / 8444 | Browser workspaces and app streaming | `lscr.io/linuxserver/kasm` | 📦 `kasm` |

### FreshRSS

Runs with SQLite only for a lightweight default deployment.

**Default URL:** `http://your-server:8081`

### SearXNG

Ships as a private search instance that is ready for Pangolin exposure:
- keeps SearXNG in private mode while still setting a public base URL from `.env`
- uses a Valkey-backed limiter so remote access does not run without bot protection
- trims a few slow default general engines and lowers upstream wait time for faster everyday searches
- lets you keep Pangolin SSO on by default, with an `.env` toggle if you intentionally want unauthenticated default-search access
- exposes the limiter as an `.env` toggle in case your reverse proxy does not pass real client IP headers
- uses the tracked templates at `config-templates/searxng/settings.yml` and `config-templates/searxng/limiter.toml`

**Default URL:** `http://your-server:8084`

### Syncthing

Uses a dedicated sync root under `${SYNCTHING_DATA_DIR}` (default `${DOCKER_MEDIA_DIR}/Sync`) instead of the full media tree.

**Default URL:** `http://your-server:8384`

### Joplin

Uses PostgreSQL by default and exposes the sync server on port `22300`.

**Default URL:** `http://your-server:22300`

### Kasm

Optional profile for remote browser workspaces:
- first boot wizard at `https://your-server:3003`
- main UI at `https://your-server:8444` after setup

**Enable:** `docker compose --profile kasm up -d`

---

## Documents & Knowledge

Document workflows, PDF utilities, bookmarks, and internal wiki tools.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Paperless-ngx** | 8010 | Document archive with OCR and automation | `ghcr.io/paperless-ngx/paperless-ngx` | ✅ |
| **Paperless PostgreSQL** | 5432 | Internal database for Paperless-ngx | `postgres:18-alpine` | ✅ |
| **Paperless Redis** | 6379 | Internal broker/cache for Paperless-ngx | `redis:8-alpine` | ✅ |
| **Stirling PDF** | 8085 | Self-hosted PDF toolbox | `docker.stirlingpdf.com/stirlingtools/stirling-pdf` | ✅ |
| **Karakeep** | 3005 | Bookmarking and read-later app | `ghcr.io/karakeep-app/karakeep` | ✅ |
| **Karakeep Meilisearch** | 7700 | Internal search backend for Karakeep | `getmeili/meilisearch` | ✅ |
| **Docmost** | 3004 | Collaborative wiki and documentation space | `docmost/docmost` | ✅ |
| **Docmost PostgreSQL** | 5432 | Internal database for Docmost | `postgres:18-alpine` | ✅ |
| **Docmost Redis** | 6379 | Internal cache for Docmost | `redis:8-alpine` | ✅ |

### Paperless-ngx

Runs with PostgreSQL, Redis, Gotenberg, and Tika sidecars for OCR and Office document ingestion.

**Default URL:** `http://your-server:8010`

### Stirling PDF

Adds a local PDF toolbox for merge, split, convert, OCR, and other document utilities.

**Default URL:** `http://your-server:8085`

### Karakeep

Runs with Meilisearch and a headless Chrome sidecar to support search, screenshots, and richer captures.

**Default URL:** `http://your-server:3005`

### Docmost

Uses PostgreSQL and Redis to provide a shared internal wiki for runbooks, homelab notes, and operational docs.

**Default URL:** `http://your-server:3004`

---

## Backup Services

Data protection and recovery.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Duplicati** | 8200 | Main config backup tool | `lscr.io/linuxserver/duplicati` | ✅ |
| **Restic Server** | 8000 | Advanced REST repository endpoint | `restic/rest-server` | 📦 `restic` |
| **DB Backup** | - | PostgreSQL dump worker | `tiredofit/db-backup` | 📦 `db-backup` |

### Duplicati

Backup to cloud storage:
- Google Drive
- Backblaze B2
- Amazon S3
- Local NAS

It is the primary backup workflow for this repo and covers `${DOCKER_BASE_DIR}` by default.

**Default URL:** `http://your-server:8200`

### Database Backups

Optional SQL dump worker:
- focused on the Immich and Joplin PostgreSQL containers
- writes dumps to `${DOCKER_BASE_DIR}/db-backup`
- those dumps are then picked up by Duplicati automatically

---

## Automation

Workflow automation services.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **n8n** | 5678 | Workflow automation | `n8nio/n8n` | 📦 `automation` |

### n8n

Low-code automation platform:
- Connect services with triggers
- Create complex workflows
- Self-hosted alternative to Zapier

**Enable:** `docker compose --profile automation up -d`

---

## File Sharing

File sync and sharing services.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Nextcloud** | 8443 | File sync & sharing | `nextcloud` | 📦 `files` |

### Nextcloud

Self-hosted cloud storage:
- File sync across devices
- Calendar & contacts
- Collaborative editing
- Mobile apps

**Enable:** `docker compose --profile files up -d`

---

## Logging

Centralized log aggregation.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Loki** | 3100 | Log aggregation | `grafana/loki` | ✅ |
| **Promtail** | - | Log collector | `grafana/promtail` | ✅ |

**Default state:** Included in `docker-compose.yml`

---

## Quick Reference

### Most Used Ports

| Port | Service | Purpose |
|:----:|:--------|:--------|
| 32400 | Plex | Media streaming |
| 2283 | Immich | Photo management |
| 22300 | Joplin | Notes sync |
| 8081 | FreshRSS | RSS reading |
| 3000 | Grafana | Dashboards |
| 3002 | Homarr | Dashboard |
| 9443 | Portainer | Container management |
| 8889 | Dozzle | Log viewer |

### Enable Common Profiles

```bash
# Media extras
docker compose --profile kavita --profile navidrome up -d

# Monitoring extras
docker compose --profile speedtest --profile scrutiny up -d

# Productivity extras
docker compose --profile kasm up -d

# Jellyfin stack
docker compose --profile jellyfin up -d

# Everything
docker compose --profile speedtest --profile scrutiny --profile kavita --profile navidrome up -d
```

---

## Related Documentation

- [Configuration](configuration.md) - Module system and profiles
- [Networking](networking.md) - Port mappings and VPN routing
- [Architecture](architecture.md) - System design and dependencies

---

[← Back to README](../README.md)
