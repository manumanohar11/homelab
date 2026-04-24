# Media Stack

Starter-first Docker Compose homelab for Plex, Immich, Linkwarden, FreshRSS, and a handful of operator tools.

The default path is intentionally small:

```bash
make init
nano .env
make prep-dirs
docker compose up -d
```

That starts only the starter stack:

- `plex`
- `immich-server`
- `immich-machine-learning`
- `database`
- `redis`
- `linkwarden-db`
- `linkwarden-meilisearch`
- `linkwarden`
- `freshrss`
- `copyparty`
- `homarr`
- `portainer`
- `dozzle`
- `watchtower`
- `duplicati`
- `tautulli`
- `docker-socket-proxy`

Everything else lives behind optional bundle entrypoints.

## Starter Quick Start

```bash
git clone https://github.com/manumanohar11/homelab.git /opt/media-stack
cd /opt/media-stack

make init
nano .env
make prep-dirs

docker compose up -d
```

For the default starter paths, `make bootstrap` runs `make init` and `make prep-dirs` together.

Starter URLs:

| Service | URL |
|:--------|:----|
| Homarr | `http://your-server:3002` |
| Plex | `http://your-server:32400/web` |
| Immich | `http://your-server:2283` |
| Linkwarden | `http://your-server:3006` |
| FreshRSS | `http://your-server:8083` |
| Copyparty | `http://localhost:3923` |
| Portainer | `https://your-server:9443` |
| Dozzle | `http://your-server:8889` |
| Duplicati | `http://your-server:8200` |
| Tautulli | `http://your-server:8181` |

## Optional Bundles

Add advanced parts of the homelab with `make`:

```bash
# Media automation and alternate media apps
make init BUNDLES="media"
make up BUNDLES="media" PROFILES="arr jellyfin"

# Productivity, documents, file sharing, automation
make init BUNDLES="apps"
make up BUNDLES="apps"

# Monitoring, logging, diagnostics, advanced backups
make init BUNDLES="ops"
make up BUNDLES="ops" PROFILES="monitoring"

# Pangolin/Newt remote access
make init BUNDLES="access"
make up BUNDLES="access"
```

## Docs

- [Quick Start](docs/quickstart.md)
- [Bundles](docs/bundles.md)
- [Configuration](docs/configuration.md)
- [Services](docs/services.md)
- [ERPNext Business Setup](docs/erpnext.md)
- [Backup & Recovery](docs/backup.md)
- [Networking](docs/networking.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Advanced Architecture](docs/advanced/architecture.md)
- [Advanced Monitoring](docs/advanced/monitoring.md)
- [Advanced Logging](docs/advanced/logging.md)
- [Advanced Docmost Publishing](docs/advanced/docmost.md)
- [Maintainer Scripts](docs/advanced/scripts.md)
