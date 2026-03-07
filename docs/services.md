# 📦 Services Catalog

[← Back to README](../README.md)

Complete catalog of all 45+ services available in the Media Stack.

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
- [Backup Services](#backup-services)
- [Automation](#automation)
- [File Sharing](#file-sharing)

---

## Status Legend

| Symbol | Meaning | How to Enable |
|:------:|:--------|:--------------|
| ✅ | Enabled by default | Already running |
| 📦 | Optional profile | `--profile <name>` |
| ⚪ | Disabled module | Uncomment in `docker-compose.yml` |

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
| **Radarr** | 7878 | Movie collection manager | `linuxserver/radarr` | ⚪ |
| **Sonarr** | 8989 | TV show collection manager | `linuxserver/sonarr` | ⚪ |
| **Lidarr** | 8686 | Music collection manager | `linuxserver/lidarr` | ⚪ |
| **Readarr** | 8787 | Book collection manager | `linuxserver/readarr` | ⚪ |
| **Bazarr** | 6767 | Subtitle manager | `linuxserver/bazarr` | ⚪ |
| **Whisparr** | 6969 | Adult content manager | `ghcr.io/hotio/whisparr` | ⚪ |
| **Recyclarr** | - | TRaSH Guide sync | `ghcr.io/recyclarr/recyclarr` | ⚪ |

### Enable *Arr Stack

1. Uncomment `docker-compose.arr.yml` in main compose file
2. Configure VPN credentials in `.env`
3. Run `docker compose up -d`

All *Arr services route through Gluetun VPN for privacy.

### Recyclarr

Automatically syncs quality profiles and custom formats from [TRaSH Guides](https://trash-guides.info/).

---

## Downloaders

Content acquisition services (VPN-routed).

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **qBittorrent** | 8080 | Torrent client | `linuxserver/qbittorrent` | ⚪ |
| **Prowlarr** | 9696 | Indexer manager | `linuxserver/prowlarr` | ⚪ |
| **FlareSolverr** | 8191 | Cloudflare bypass | `ghcr.io/flaresolverr/flaresolverr` | ⚪ |
| **Bitmagnet** | 3333 | DHT crawler | `ghcr.io/bitmagnet-io/bitmagnet` | ⚪ |

### Enable Downloaders

1. Uncomment `docker-compose.downloaders.yml`
2. Configure VPN in `.env`:
   ```bash
   VPN_SERVICE_PROVIDER=mullvad
   OPENVPN_USER=your_account
   ```
3. Run `docker compose up -d`

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
| **AlertManager** | 9093 | Alert routing & management | `prom/alertmanager` | ✅ |
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
| **Homepage** | 3002 | Customizable dashboard | `ghcr.io/gethomepage/homepage` | ✅ |
| **Dozzle** | 8889 | Real-time log viewer | `amir20/dozzle` | ✅ |
| **Glance** | 8080 | Alternative dashboard | `glanceapp/glance` | 📦 `dashboard` |

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

### Homepage

Customizable dashboard with:
- Docker integration (auto-discovery)
- Service widgets (stats, status)
- Bookmarks and search

---

## Backup Services

Data protection and recovery.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Duplicati** | 8200 | Cloud backup | `lscr.io/linuxserver/duplicati` | ✅ |
| **Restic Server** | 8000 | REST backup repository | `restic/rest-server` | 📦 `restic` |
| **DB Backup** | - | PostgreSQL backup | `tiredofit/db-backup` | 📦 `db-backup` |

### Duplicati

Backup to cloud storage:
- Google Drive
- Backblaze B2
- Amazon S3
- Local NAS

**Default URL:** `http://your-server:8200`

### Database Backups

Automated daily backups:
- **PostgreSQL:** 3:00 AM, 6-day retention
- **SQLite:** Daily, 7-day retention

---

## Automation

Workflow automation services.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **n8n** | 5678 | Workflow automation | `n8nio/n8n` | ⚪ |

### n8n

Low-code automation platform:
- Connect services with triggers
- Create complex workflows
- Self-hosted alternative to Zapier

**Enable:** Uncomment `docker-compose.automation.yml`

---

## File Sharing

File sync and sharing services.

| Service | Port | Description | Image | Status |
|:--------|:----:|:------------|:------|:------:|
| **Nextcloud** | 8080 | File sync & sharing | `nextcloud` | ⚪ |

### Nextcloud

Self-hosted cloud storage:
- File sync across devices
- Calendar & contacts
- Collaborative editing
- Mobile apps

**Enable:** Uncomment `docker-compose.files.yml`

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
| 3000 | Grafana | Dashboards |
| 3002 | Homepage | Dashboard |
| 9443 | Portainer | Container management |
| 8889 | Dozzle | Log viewer |

### Enable Common Profiles

```bash
# Media extras
docker compose --profile kavita --profile navidrome up -d

# Monitoring extras
docker compose --profile speedtest --profile scrutiny up -d

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
