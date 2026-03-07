# ⚙️ Configuration Guide

[← Back to README](../README.md)

Detailed guide to configuring the Media Stack, including modules, profiles, environment variables, and security.

---

## Table of Contents

- [Module System](#module-system)
- [Profiles](#profiles)
- [Environment Variables](#environment-variables)
- [VPN Setup](#vpn-setup)
- [Hardware Acceleration](#hardware-acceleration)
- [Service Configuration](#service-configuration)
- [Security](#security)
- [Directory Structure](#directory-structure)

---

## Module System

The stack uses a modular design with separate compose files for each service group.

### Main Compose File

```yaml
# docker-compose.yml
include:
  # Core (always required)
  - docker-compose.common.yml      # Shared templates
  - docker-compose.core.yml        # VPN, proxy, tunnels

  # Standard modules
  - docker-compose.photos.yml
  - docker-compose.media-servers.yml
  - docker-compose.arr.yml
  - docker-compose.downloaders.yml
  - docker-compose.media-extras.yml
  - docker-compose.requests.yml
  - docker-compose.management.yml
  - docker-compose.monitoring.yml
  - docker-compose.logging.yml
  - docker-compose.files.yml
  - docker-compose.automation.yml
  - docker-compose.utilities.yml
  - docker-compose.backup.yml

  # Host-specific overrides only
  # - docker-compose.local.yml
```

### Module Reference

| File | Description | Services |
|:-----|:------------|:---------|
| `common.yml` | YAML anchors, shared configs | Templates only |
| `core.yml` | Core infrastructure | Docker Proxy, Gluetun, Newt |
| `photos.yml` | Photo management | Immich, PostgreSQL, Redis |
| `media-servers.yml` | Media streaming | Plex, Jellyfin, Stash, Kavita, Navidrome |
| `media-extras.yml` | Media utilities | Tautulli, Maintainerr, Tdarr |
| `arr.yml` | Media automation | Radarr, Sonarr, Lidarr, Readarr, Bazarr |
| `downloaders.yml` | Download clients | qBittorrent, Prowlarr, FlareSolverr |
| `requests.yml` | Request portals | Overseerr, Jellyseerr |
| `management.yml` | Container management | Portainer, Watchtower, Glances, Glance |
| `monitoring.yml` | Monitoring stack | Prometheus, Grafana, AlertManager |
| `logging.yml` | Container log aggregation | Loki, Promtail |
| `utilities.yml` | Utility services | Homepage, Dozzle, Scrutiny, Speedtest |
| `backup.yml` | Backup services | Duplicati, Restic, DB Backup |
| `automation.yml` | Workflow automation | n8n |
| `files.yml` | File sharing | Nextcloud |

### Enable/Disable Modules

The normal way to turn optional parts of the stack on is with profiles, not by editing `docker-compose.yml`.

```bash
# *Arr apps plus downloader stack
docker compose --profile arr up -d

# Downloaders only
docker compose --profile downloaders up -d

# Nextcloud
docker compose --profile files up -d

# n8n
docker compose --profile automation up -d
```

Comment an include line only if you want to permanently remove an entire module from your personal install.

---

## Profiles

Profiles allow optional services within modules to be enabled on-demand.

### Using Profiles

```bash
# Enable single profile
docker compose --profile speedtest up -d

# Enable multiple profiles
docker compose --profile speedtest --profile scrutiny --profile kavita up -d

# Disable profile (just don't include it)
docker compose up -d
```

### Available Profiles

| Profile | Services | Compose File |
|:--------|:---------|:-------------|
| `monitoring` | Glances | management.yml |
| `dashboard` | Glance | management.yml |
| `arr` | *Arr apps plus downloader stack | arr.yml, downloaders.yml |
| `downloaders` | qBittorrent, Prowlarr, FlareSolverr, Bitmagnet | downloaders.yml |
| `jellyfin` | Jellyfin, Jellyseerr | media-servers.yml, requests.yml |
| `kavita` | Kavita | media-servers.yml |
| `stash` | Stash | media-servers.yml |
| `tdarr` | Tdarr | media-extras.yml |
| `automation` | n8n | automation.yml |
| `requests` | Overseerr | requests.yml |
| `maintainerr` | Maintainerr | media-extras.yml |
| `notifiarr` | Notifiarr | requests.yml |
| `restic` | Restic Server | backup.yml |
| `db-backup` | DB Backup | backup.yml |
| `files` | Nextcloud | files.yml |
| `scrutiny` | Scrutiny | utilities.yml |
| `speedtest` | Speedtest Tracker | utilities.yml |
| `navidrome` | Navidrome | media-servers.yml |
### Profile Examples

**Full monitoring setup:**
```bash
docker compose --profile monitoring --profile speedtest --profile scrutiny up -d
```

**Full media automation:**
```bash
docker compose --profile arr --profile requests up -d
```

**Jellyfin with requests:**
```bash
docker compose --profile jellyfin up -d
```

**Optional apps:**
```bash
docker compose --profile automation --profile files --profile kavita up -d
```

---

## Environment Variables

### Core Settings

```bash
# ============================================
# SYSTEM
# ============================================

# User/Group IDs (from 'id' command)
PUID=1000
PGID=1000

# Timezone
TZ=America/New_York

# Domain name (for reverse proxy/tunnels)
DOMAIN_NAME=example.com

# ============================================
# PATHS
# ============================================

# Project directory (where compose files live)
DOCKER_PROJECT_DIR=/opt/media-stack

# Data directory (container configs)
DOCKER_BASE_DIR=/opt/media-stack/data

# SSD config directory (for databases)
DOCKER_SSD_CONFIG_DIR=/opt/media-stack/data

# Git-tracked config templates
DOCKER_GIT_CONFIG_DIR=/opt/media-stack/config-templates

# Media storage
DOCKER_MEDIA_DIR=/mnt/media

# Backup destination
BACKUP_DESTINATION=/mnt/backup
```

### Database Settings

```bash
# ============================================
# IMMICH DATABASE (PostgreSQL)
# ============================================

DB_PASSWORD=your_secure_password_here
DB_USERNAME=postgres
DB_DATABASE_NAME=immich
DB_HOSTNAME=immich_postgres

# ============================================
# BITMAGNET DATABASE (Optional)
# ============================================

BITMAGNET_POSTGRES_PASSWORD=another_secure_password
```

### Photo Storage

```bash
# ============================================
# IMMICH STORAGE
# ============================================

UPLOAD_LOCATION=/mnt/photos/upload
THUMB_LOCATION=/mnt/photos/thumbs
ENCODED_VIDEO_LOCATION=/mnt/photos/encoded-video
PROFILE_LOCATION=/mnt/photos/profile
BACKUP_LOCATION=/mnt/photos/backups
DB_DATA_LOCATION=/opt/media-stack/data/immich-db
```

### VPN Settings

```bash
# ============================================
# VPN (Gluetun)
# ============================================

VPN_SERVICE_PROVIDER=mullvad
OPENVPN_USER=your_account_number
OPENVPN_PASSWORD=
SERVER_REGIONS=us
FIREWALL_OUTBOUND_SUBNETS=172.16.0.0/12,192.168.0.0/16
```

### API Keys

```bash
# ============================================
# API KEYS (shared with Homepage widgets)
# ============================================

PLEX_API_KEY=your_plex_token
JELLYFIN_API_KEY=your_jellyfin_key
TAUTULLI_API_KEY=your_tautulli_key
OVERSEERR_API_KEY=your_overseerr_key
RADARR_API_KEY=your_radarr_key
SONARR_API_KEY=your_sonarr_key
IMMICH_API_KEY=your_immich_key
PORTAINER_API_KEY=your_portainer_key
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=change_me

# ============================================
# NOTIFICATIONS
# ============================================

WATCHTOWER_NOTIFICATION_URL=discord://token@id
```

### Tunnel Settings

```bash
# ============================================
# PANGOLIN/NEWT TUNNEL
# ============================================

NEWT_ID=your_newt_id
NEWT_SECRET=your_newt_secret
PANGOLIN_ENDPOINT=https://pangolin.example.com
```

---

## VPN Setup

### Supported Providers

Gluetun supports many VPN providers:
- **Mullvad** (recommended)
- NordVPN
- Private Internet Access
- Surfshark
- ExpressVPN
- [And many more](https://github.com/qdm12/gluetun-wiki)

### Mullvad Configuration

```bash
# .env
VPN_SERVICE_PROVIDER=mullvad
OPENVPN_USER=your_account_number  # 16-digit number
SERVER_REGIONS=us                  # or specific city
```

### NordVPN Configuration

```bash
# .env
VPN_SERVICE_PROVIDER=nordvpn
OPENVPN_USER=your_email
OPENVPN_PASSWORD=your_password
SERVER_REGIONS=United_States
```

### Private Internet Access

```bash
# .env
VPN_SERVICE_PROVIDER=private internet access
OPENVPN_USER=pXXXXXXX
OPENVPN_PASSWORD=your_password
SERVER_REGIONS=US East
```

### Verify VPN Connection

```bash
# Check Gluetun logs
docker compose logs gluetun

# Verify VPN IP
docker exec gluetun curl ifconfig.me

# Should show VPN IP, not your real IP
```

### VPN Regions

<details>
<summary>Click to expand region list</summary>

**US Regions:**
- US East, US West
- US California, US New York
- US Florida, US Texas
- US Chicago, US Seattle

**Europe:**
- UK London, UK Manchester
- DE Berlin, DE Frankfurt
- France, Netherlands
- Switzerland, Sweden

**Asia Pacific:**
- AU Sydney, AU Melbourne
- Japan Tokyo, Singapore
- Hong Kong, South Korea

</details>

---

## Hardware Acceleration

### Transcoding (Plex/Jellyfin)

#### NVIDIA GPU

```yaml
# In docker-compose.media-servers.yml
plex:
  extends:
    file: hwaccel.transcoding.yml
    service: nvenc
```

#### Intel Quick Sync

```yaml
plex:
  extends:
    file: hwaccel.transcoding.yml
    service: quicksync
```

#### AMD VAAPI

```yaml
plex:
  extends:
    file: hwaccel.transcoding.yml
    service: vaapi
```

### Machine Learning (Immich)

#### NVIDIA CUDA

```yaml
# In docker-compose.photos.yml
immich_machine_learning:
  extends:
    file: hwaccel.ml.yml
    service: cuda
```

#### Intel OpenVINO

```yaml
immich_machine_learning:
  extends:
    file: hwaccel.ml.yml
    service: openvino
```

---

## Service Configuration

### Homepage Dashboard

Homepage auto-discovers services via Docker labels. Customize in:

```
/opt/media-stack/data/homepage/
├── settings.yaml     # Theme, layout, background
├── services.yaml     # Service widgets
├── widgets.yaml      # Top bar widgets
└── bookmarks.yaml    # Quick links
```

**Example services.yaml:**
```yaml
- Media:
    - Plex:
        icon: plex.png
        href: http://plex:32400/web
        widget:
          type: plex
          url: http://plex:32400
          key: {{HOMEPAGE_VAR_PLEX_API_KEY}}
```

### Prometheus

Configure scrape targets in:
```
/opt/media-stack/data/prometheus/prometheus.yml
```

**Default targets:**
- Node Exporter (system metrics)
- Prometheus itself
- Uptime Kuma (service availability)

### Grafana

Dashboards location:
```
/opt/media-stack/data/grafana/dashboards/
```

Provisioning:
```
/opt/media-stack/data/grafana/provisioning/
```

### AlertManager

Alert configuration:
```
/opt/media-stack/data/alertmanager/config/alertmanager.yml
```

---

## Security

### Best Practices

1. **Change default passwords**
   ```bash
   # In .env
   DB_PASSWORD=use_a_strong_random_password
   ```

2. **Never expose ports directly to internet**
   - Use Pangolin/Newt tunnel
   - Or Cloudflare Tunnel
   - Or reverse proxy with auth

3. **Use VPN for downloads**
   - All *Arr traffic routes through Gluetun
   - Verify with: `docker exec gluetun curl ifconfig.me`

4. **Keep services updated**
   - Watchtower handles automatic updates
   - Immich excluded (update manually)

5. **Regular backups**
   - Configure Duplicati for cloud backup
   - Enable database backups

### Docker Socket Proxy

The socket proxy provides secure Docker API access:

```yaml
docker-socket-proxy:
  environment:
    CONTAINERS: 1     # Read container info
    SERVICES: 0       # No swarm services
    TASKS: 0          # No swarm tasks
    POST: 0           # No write operations
```

### Container Security

All containers run with:
- `no-new-privileges: true`
- PUID/PGID for proper file ownership
- Resource limits where appropriate

### Secrets Management

```bash
# .env is gitignored - never commit it!
# Store sensitive values here:
DB_PASSWORD=xxx
PLEX_API_KEY=xxx
VPN_CREDENTIALS=xxx
```

### Network Security

- Single bridge network isolates services
- VPN routing for sensitive traffic
- No direct internet exposure

---

## Directory Structure

### Project Layout

```
/opt/media-stack/                   # Project root
├── docker-compose.yml              # Main compose file
├── docker-compose.*.yml            # Service modules
├── hwaccel.*.yml                   # Hardware acceleration
├── .env                            # Configuration (gitignored)
├── .env.example                    # Template
│
├── config-templates/               # Git-tracked templates
│   ├── alertmanager/
│   ├── prometheus/
│   └── ...
│
└── data/                           # Runtime data (gitignored)
    ├── plex/
    ├── immich/
    ├── grafana/
    └── ...
```

### Media Layout

```
/mnt/media/
├── Movies/
├── TV/
├── Music/
├── Books/
├── Comics/
├── Downloads/
│   ├── complete/
│   └── incomplete/
└── Photos/
```

### Photo Storage

```
/mnt/photos/
├── upload/           # Original uploads
├── thumbs/           # Generated thumbnails
├── encoded-video/    # Transcoded videos
├── profile/          # User profiles
└── backups/          # Immich backups
```

---

## Related Documentation

- [Services Catalog](services.md) - All available services
- [Networking](networking.md) - Network configuration
- [Architecture](architecture.md) - System design

---

[← Back to README](../README.md)
