# AGENTS.md - AI Coding Agent Guidelines

Guidelines for AI agents working in this Docker-based homelab infrastructure repository.

## Repository Model

This repo is now starter-first:

- `docker compose up -d` starts only the beginner-friendly starter stack.
- Optional services live in bundle files and are enabled with `make up BUNDLES="..." PROFILES="..."`.
- Shared compose defaults belong in `docker-compose.common.yml`, not duplicated across bundle files.

Starter services:

- `docker-socket-proxy`
- `plex`
- `immich-server`
- `immich-machine-learning`
- `database`
- `redis`
- `homarr`
- `portainer`
- `dozzle`
- `watchtower`
- `duplicati`
- `tautulli`

Optional bundles:

- `media`: Gluetun, *Arr, downloaders, requests, and alternate media apps
- `apps`: productivity, documents, files, and automation
- `ops`: monitoring, logging, diagnostics, and advanced backups
- `access`: Pangolin/Newt, Jitsi, coturn, and DDNS helpers

## Commands Reference

```bash
# Beginner path
make init
docker compose up -d

# Bundle-aware workflow
make init BUNDLES="media apps"
make up BUNDLES="media" PROFILES="arr jellyfin"
make config BUNDLES="ops" PROFILES="monitoring"
make logs BUNDLES="access" PROFILES="jitsi" SERVICE=jitsi-web

# Starter-only debugging
docker compose config
docker compose logs -f <service>
docker inspect --format='{{.State.Health.Status}}' <container>
docker exec -it <container> /bin/bash
docker stats

# Maintainer validation
python3 scripts/validate-stack.py
python3 scripts/build-docmost-space.py --check
```

## Project Structure

```text
docker-compose.yml               # Starter stack only
docker-compose.common.yml        # Shared anchors and helper services
docker-compose.media.yml         # Optional media bundle
docker-compose.apps.yml          # Optional apps bundle
docker-compose.ops.yml           # Optional ops bundle
docker-compose.access.yml        # Optional access bundle
docker-compose.local.example.yml # Host-specific local overrides template
hwaccel.transcoding.yml          # Hardware acceleration for transcoding
hwaccel.ml.yml                   # Hardware acceleration for ML
env/bundles/                     # Optional bundle env fragments
docs/advanced/                   # Maintainer and advanced operator docs
configs/                         # Tracked app config templates
.env.example                     # Starter env template
```

## Compose Conventions

### Optionality

- Tracked optionality is handled with bundle files plus service profiles.
- Do not reintroduce commented include toggles or hidden compose generation layers.
- `docker-compose.yml` must remain starter-only.

### Shared Defaults

- `docker-compose.common.yml` is the only tracked source for shared `x-*` defaults.
- Prefer `extends` from helper services instead of repeating standard `restart`, `security_opt`, `logging`, standard resources, or VPN wiring.
- Use the helper that matches the service shape before overriding specifics.

Available helpers:

- `_service-tiny`, `_service-small`, `_service-medium`, `_service-large`
- `_lsio-small`, `_lsio-medium`, `_lsio-large`
- `_vpn-service-small`, `_vpn-service-medium`, `_vpn-service-large`
- `_vpn-lsio-small`, `_vpn-lsio-medium`, `_vpn-lsio-large`
- `_arr-lsio-small`, `_arr-lsio-medium`, `_arr-lsio-large`

Available anchors:

- `*common-env`
- `*lsio-env`
- `*security-opts`
- `*default-logging`
- `*healthcheck-defaults`
- `*resources-tiny`
- `*resources-small`
- `*resources-medium`
- `*resources-large`
- `*vpn-depends-on`
- `*arr-depends-on`

### Property Order

Use this service property order when practical:

```text
extends → image → container_name → restart → init → security_opt →
network_mode → environment → env_file → volumes → user → group_add →
networks → ports → healthcheck → depends_on → logging → deploy →
labels → profiles
```

### Naming and Environment Variables

- Containers: lowercase, hyphen-separated
- Networks: use the shared `media-stack` network unless the service intentionally uses host or service network mode
- Volumes: prefer env-backed paths such as `${DOCKER_BASE_DIR}/service:/config`
- Defaults: use `${VAR:-default}` where a safe default exists
- Common variables: `PUID`, `PGID`, `TZ`, `DOCKER_BASE_DIR`, `DOCKER_MEDIA_DIR`, `DOMAIN_NAME`

## Service Patterns

### Standard LinuxServer.io Service

```yaml
service-name:
  extends:
    file: docker-compose.common.yml
    service: _lsio-medium
  image: lscr.io/linuxserver/app:latest
  container_name: service-name
  volumes:
    - ${DOCKER_BASE_DIR}/service-name:/config
  networks:
    - media-stack
  ports:
    - "8080:8080"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  labels:
    - "com.centurylinklabs.watchtower.enable=true"
```

### VPN-Routed Service

```yaml
service-name:
  extends:
    file: docker-compose.common.yml
    service: _vpn-service-medium
  image: ghcr.io/example/app:latest
  container_name: service-name
```

### *Arr Service

```yaml
service-name:
  extends:
    file: docker-compose.common.yml
    service: _arr-lsio-large
  image: lscr.io/linuxserver/radarr:latest
  container_name: radarr
```

### GPU-Enabled Service

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

## Security Guidelines

1. Never commit secrets. `.env` remains gitignored.
2. Use environment variables for all sensitive data.
3. Prefer read-only mounts when write access is not required.
4. Mount the Docker socket read-only unless a tool explicitly requires otherwise.
5. Add `no-new-privileges:true` to every service.
6. Set resource limits and reservations on every service.
7. Only use `privileged: true` when there is a real service requirement.

## Testing Changes

1. Starter validation: `docker compose config`
2. Bundle validation: `make config BUNDLES="media" PROFILES="arr jellyfin"`
3. Service startup: `make up BUNDLES="ops" PROFILES="monitoring" SERVICE=grafana`
4. Logs: `make logs BUNDLES="access" PROFILES="jitsi" SERVICE=jitsi-web`
5. Full repo validation: `python3 scripts/validate-stack.py`

## Maintainer Scripts

- `scripts/init-env.py`: user-facing bootstrap behind `make init`
- `scripts/validate-stack.py`: validates starter, bundles, docs, and Docmost output
- `scripts/build-docmost-space.py`: builds import-ready content under `build/docmost-space/`
- `scripts/sync-monitoring-config.sh`: syncs tracked monitoring and logging templates
- `scripts/homarr_seed.py`: seeds the Homarr board from the resolved starter or bundle-aware compose config

## Backup Strategy

1. Back up `${DOCKER_BASE_DIR}` configuration directories.
2. Include `.env` in the backup plan.
3. Use `db-backup` for PostgreSQL dumps where configured.
4. Treat large media libraries as a separate backup problem.
5. Prefer daily config backups and at least weekly database backups.
