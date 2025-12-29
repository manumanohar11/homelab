# AGENTS.md - AI Coding Agent Guidelines

Guidelines for AI agents working in this Docker-based homelab infrastructure repository.

## Repository Overview

Modular Docker Compose infrastructure for self-hosted services: media management (*Arr suite), media servers (Plex/Jellyfin), photo management (Immich), monitoring (Prometheus/Grafana), and automation (n8n).

## Commands Reference

```bash
# Stack operations
docker compose up -d                      # Start full stack
docker compose up -d <service>            # Start specific service
docker compose down                       # Stop all services
docker compose restart <service>          # Restart service
docker compose ps                         # Check status

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
docker-compose.common.yml       # YAML anchors for reuse
docker-compose.core.yml         # VPN (gluetun), tunnels (newt)
docker-compose.arr.yml          # *Arr suite (radarr, sonarr, etc.)
docker-compose.downloaders.yml  # qBittorrent, prowlarr, flaresolverr
docker-compose.media-servers.yml# Plex, Jellyfin, Stash
docker-compose.management.yml   # Portainer, Watchtower
docker-compose.monitoring.yml   # Prometheus, Grafana, InfluxDB
docker-compose.photos.yml       # Immich stack
docker-compose.files.yml        # Nextcloud
docker-compose.automation.yml   # n8n
hwaccel.*.yml                   # Hardware acceleration configs
configs/                        # Application configs (tracked)
.env                            # Environment variables (NOT tracked)
```

## Code Style Guidelines

### File Header & Service Order
Start compose files with path/purpose comment. Follow this property order:
image → container_name → restart → network_mode → environment → volumes → user → networks → ports → healthcheck → depends_on → deploy

### Naming & Environment Variables
- **Containers**: lowercase, hyphen-separated (`uptime-kuma`)
- **Networks**: Use shared `media-stack` network  
- **Volumes**: Use env vars (`${DOCKER_BASE_DIR}/service:/config`)
- **Common vars**: `PUID`, `PGID`, `TZ`, `DOCKER_BASE_DIR`, `DOCKER_MEDIA_DIR`
- **Defaults**: `${VAR:-default_value}`

### Standard Service Template
```yaml
service-name:
  image: lscr.io/linuxserver/app:latest
  container_name: service-name
  restart: unless-stopped
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
    interval: 1m
    timeout: 10s
    retries: 3
```

### VPN-Routed Service Pattern
For services routing through VPN, use `network_mode: "service:gluetun"` and depend on gluetun health.

### GPU-Enabled Service (NVIDIA)
Add `NVIDIA_VISIBLE_DEVICES: all` env var and deploy resources with nvidia driver capability.

### Health Checks (Required)
All services should have healthchecks. Use curl to test HTTP endpoints:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:PORT/health"]
  interval: 1m
  timeout: 10s
  retries: 3
```

### Dependencies
Use conditional dependencies from `docker-compose.common.yml`:
```yaml
depends_on:
  dependency-service:
    condition: service_healthy
```

## Security Guidelines

1. **Never commit secrets** - `.env` is gitignored
2. **Use environment variables** for all sensitive data
3. **Read-only mounts** - Use `:ro` when write not needed
4. **Docker socket** - Always mount read-only (`/var/run/docker.sock:ro`)
5. **Limit privileges** - Only use `privileged: true` when necessary

## Image Sources

- **LinuxServer.io**: `lscr.io/linuxserver/` (preferred for media apps)
- **Hotio**: `ghcr.io/hotio/` (alternative media images)
- **Official**: Docker Hub official images for databases/monitoring

## Enabling/Disabling Services

Toggle in `docker-compose.yml` by commenting includes:
```yaml
include:
  - docker-compose.core.yml
  # - docker-compose.arr.yml      # Commented = disabled
```

Or comment entire service blocks within individual files.

## Testing Changes

1. Validate: `docker compose config`
2. Start: `docker compose up -d <service>`
3. Check logs: `docker compose logs -f <service>`
4. Verify health: `docker inspect --format='{{.State.Health.Status}}' <container>`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Service won't start | `docker compose logs <service>` |
| Health check failing | Verify endpoint and container network |
| Permission issues | Check PUID/PGID match host user |
| Network issues | Ensure service on `media-stack` network |
| VPN issues | Check gluetun health first |

## Git Workflow

- Commit compose changes with descriptive messages
- Never commit `.env` or gitignored files
- Keep sensitive configs out of `configs/` directory
