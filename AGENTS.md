# AGENTS.md - AI Coding Agent Guidelines

Guidelines for AI agents working in this Docker-based homelab infrastructure repository.

## Repository Overview

Modular Docker Compose infrastructure for self-hosted services: media management (*Arr suite), media servers (Plex/Jellyfin/Tdarr), photo management (Immich), monitoring (Prometheus/Grafana/Loki), tunnel proxy (Pangolin/Newt), backup (Duplicati), requests (Overseerr), and automation (n8n).

## Commands Reference

```bash
# Stack operations
docker compose up -d                      # Start full stack
docker compose up -d <service>            # Start specific service
docker compose down                       # Stop all services
docker compose restart <service>          # Restart service
docker compose ps                         # Check status

# Profile-based startup (for optional services)
docker compose --profile vpn up -d        # Start with VPN services
docker compose --profile monitoring up -d # Start with extra monitoring
docker compose --profile jellyfin up -d   # Start Jellyfin instead of Plex

# Logs and debugging
docker compose logs -f <service>          # View logs
docker compose config                     # Validate compose files
docker inspect --format='{{.State.Health.Status}}' <container>
docker exec -it <container> /bin/bash     # Shell into container
docker stats                              # Resource usage
```

## Project Structure

```
docker-compose.yml              # Main entry point (uses include directive)
docker-compose.common.yml       # YAML anchors and reusable configurations
docker-compose.core.yml         # VPN (gluetun), tunnels (newt/Pangolin)
docker-compose.arr.yml          # *Arr suite (radarr, sonarr, readarr, etc.)
docker-compose.downloaders.yml  # qBittorrent, Prowlarr, FlareSolverr, Bitmagnet
docker-compose.media-servers.yml# Plex, Jellyfin, Stash, Tdarr
docker-compose.management.yml   # Portainer, Watchtower, Glances
docker-compose.monitoring.yml   # Prometheus, Grafana, InfluxDB, Alertmanager
docker-compose.logging.yml      # Loki and Promtail
docker-compose.photos.yml       # Immich stack
docker-compose.files.yml        # Nextcloud
docker-compose.automation.yml   # n8n
docker-compose.requests.yml     # Overseerr, Jellyseerr, Notifiarr
docker-compose.backup.yml       # Duplicati, Restic, DB-Backup
hwaccel.transcoding.yml         # Hardware acceleration for transcoding
hwaccel.ml.yml                  # Hardware acceleration for ML
configs/                        # Application configs (tracked in git)
  alertmanager/                 # Alertmanager configuration
  glance-homepage/              # Glance dashboard config
  loki/                         # Loki log aggregation config
  promtail/                     # Promtail log collector config
.env                            # Environment variables (NOT tracked)
.env.example                    # Template for environment variables
```

## Service Categories

### Infrastructure
| Service | Port | Purpose |
|---------|------|---------|
| Gluetun | - | VPN container |
| Newt | - | Pangolin tunnel (auth & proxy) |

### Media Management (*Arr Suite)
| Service | Port | Purpose |
|---------|------|---------|
| Radarr | 7878 | Movie management |
| Sonarr | 8989 | TV show management |
| Lidarr | 8686 | Music management |
| Readarr | 8787 | Book management |
| Bazarr | 6767 | Subtitle management |
| Whisparr | 6969 | Adult content management |
| Recyclarr | - | TRaSH guide sync |

### Downloaders
| Service | Port | Purpose |
|---------|------|---------|
| qBittorrent | 8080 | Torrent client |
| Prowlarr | 9696 | Indexer manager |
| FlareSolverr | 8191 | Cloudflare bypass |
| Bitmagnet | 3333 | DHT crawler |

### Media Servers
| Service | Port | Purpose |
|---------|------|---------|
| Plex | 32400 | Primary media server |
| Jellyfin | 8096 | Alternative media server |
| Stash | 9998 | Adult media organizer |
| Tdarr | 8265 | Media transcoding |

### Photos
| Service | Port | Purpose |
|---------|------|---------|
| Immich Server | 2283 | Photo management |
| Immich ML | - | Machine learning |

### Monitoring
| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Visualization |
| Alertmanager | 9093 | Alert management |
| InfluxDB | 8086 | Time-series database |
| Loki | 3100 | Log aggregation |
| Uptime Kuma | 3001 | Uptime monitoring |

### Management
| Service | Port | Purpose |
|---------|------|---------|
| Portainer | 9443 | Container management |
| Watchtower | - | Auto updates |
| Duplicati | 8200 | Backup solution |
| Overseerr | 5055 | Media requests |

## Code Style Guidelines

### File Header & Service Order
Start compose files with path/purpose comment. Follow this property order:
```
image → container_name → restart → security_opt → network_mode → 
environment → volumes → user → networks → ports → healthcheck → 
depends_on → logging → deploy → labels → profiles
```

### Naming & Environment Variables
- **Containers**: lowercase, hyphen-separated (`uptime-kuma`)
- **Networks**: Use shared `media-stack` network  
- **Volumes**: Use env vars (`${DOCKER_BASE_DIR}/service:/config`)
- **Common vars**: `PUID`, `PGID`, `TZ`, `DOCKER_BASE_DIR`, `DOCKER_MEDIA_DIR`, `DOMAIN_NAME`
- **Defaults**: `${VAR:-default_value}`

### Standard Service Template
```yaml
service-name:
  image: lscr.io/linuxserver/app:latest
  container_name: service-name
  restart: unless-stopped
  security_opt:
    - no-new-privileges:true
  environment:
    PUID: ${PUID}
    PGID: ${PGID}
    TZ: ${TZ}
  volumes:
    - ${DOCKER_BASE_DIR}/service-name:/config
  networks:
    - media-stack
  ports:
    - "8080:8080"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
      reservations:
        memory: 128M
  labels:
    - "com.centurylinklabs.watchtower.enable=true"
    - "homepage.group=Category"
    - "homepage.name=Service Name"
```

### VPN-Routed Service Pattern
For services routing through VPN, use `network_mode: "service:gluetun"` and depend on gluetun health:
```yaml
service-name:
  network_mode: "service:gluetun"
  depends_on:
    gluetun:
      condition: service_healthy
```

### GPU-Enabled Service (NVIDIA)
```yaml
service-name:
  environment:
    NVIDIA_VISIBLE_DEVICES: all
    NVIDIA_DRIVER_CAPABILITIES: compute,video,utility
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Health Checks (Required)
All services MUST have healthchecks:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:PORT/health"]
  interval: 1m
  timeout: 10s
  retries: 3
  start_period: 30s
```

### Logging (Required)
All services MUST have log rotation:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

### Resource Limits (Recommended)
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      memory: 512M
```

### YAML Anchors
Use anchors from `docker-compose.common.yml`:
- `*common-env` - PUID, PGID, TZ
- `*default-logging` - Standard log rotation
- `*healthcheck-defaults` - Standard health check timing
- `*resources-small/medium/large` - Resource limits
- `*security-opts` - no-new-privileges
- `*vpn-depends-on` - VPN dependency
- `*arr-depends-on` - Full *Arr dependencies

## Security Guidelines

1. **Never commit secrets** - `.env` is gitignored
2. **Use environment variables** for all sensitive data
3. **Read-only mounts** - Use `:ro` when write not needed
4. **Docker socket** - Always mount read-only (`/var/run/docker.sock:ro`)
5. **Limit privileges** - Only use `privileged: true` when necessary (e.g., cAdvisor)
6. **Security options** - Add `no-new-privileges:true` to all services
7. **Resource limits** - Always set memory/CPU limits to prevent runaway containers

## Image Sources

- **LinuxServer.io**: `lscr.io/linuxserver/` (preferred for media apps)
- **Hotio**: `ghcr.io/hotio/` (alternative media images)
- **Official**: Docker Hub official images for databases/monitoring
- **GitHub Container Registry**: `ghcr.io/` for community projects

## Enabling/Disabling Services

### Preferred Method: Use profiles for optional services
```yaml
# In service definition:
profiles:
  - arr

# To start:
docker compose --profile arr up -d
```

### Secondary Method: Comment includes in docker-compose.yml
```yaml
include:
  - docker-compose.core.yml
  # - docker-compose.arr.yml      # Commented = disabled
```

## Testing Changes

1. Validate: `docker compose config`
2. Check specific file: `docker compose -f docker-compose.core.yml config`
3. Start: `docker compose up -d <service>`
4. Check logs: `docker compose logs -f <service>`
5. Verify health: `docker inspect --format='{{.State.Health.Status}}' <container>`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Service won't start | `docker compose logs <service>` |
| Health check failing | Verify endpoint and container network |
| Permission issues | Check PUID/PGID match host user |
| Network issues | Ensure service on `media-stack` network |
| VPN issues | Check gluetun health first |
| Out of memory | Check `docker stats`, increase limits |
| Logs filling disk | Verify logging config with max-size |

## Git Workflow

- Commit compose changes with descriptive messages
- Never commit `.env` or gitignored files
- Keep sensitive configs out of `configs/` directory
- Use `.env.example` as template for required variables

## Backup Strategy

1. **Config backup**: All `${DOCKER_BASE_DIR}` directories
2. **Secrets backup**: Keep `.env` in your backup plan
3. **Database backup**: Use db-backup service for PostgreSQL dumps into `${DOCKER_BASE_DIR}/db-backup`
4. **Media backup**: Separate strategy for large media files
5. **Recommended schedule**: Daily for configs, weekly for databases
