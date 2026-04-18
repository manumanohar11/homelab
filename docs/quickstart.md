# Quick Start

[Back to README](../README.md)

This guide covers only the starter stack. Optional bundles live in [Bundles](bundles.md).

## 1. Prerequisites

- Docker Engine 27+
- Docker Compose v2
- A Linux host with at least 8 GB RAM
- Write access to the media and photo directories you plan to mount

## 2. Clone The Repo

```bash
git clone https://github.com/manumanohar11/homelab.git /opt/media-stack
cd /opt/media-stack
```

## 3. Bootstrap `.env`

```bash
make init
nano .env
```

Starter secrets are generated automatically:

- `DB_PASSWORD`
- `DUPLICATI_ENCRYPTION_KEY`
- `HOMARR_SECRET_ENCRYPTION_KEY`
- `LINKWARDEN_NEXTAUTH_SECRET`
- `LINKWARDEN_POSTGRES_PASSWORD`
- `LINKWARDEN_MEILI_MASTER_KEY`

You still need to review the host paths and timezone in `.env`.

For the default starter paths, `make bootstrap` runs `make init` and `make prep-dirs` together.

## 4. Create Starter Directories

```bash
make prep-dirs
```

## 5. Validate The Starter Config

```bash
docker compose config
```

If you later start using bundles, validate those resolved files before starting them:

```bash
make config BUNDLES="media" PROFILES="arr jellyfin"
```

## 6. Start The Starter Stack

```bash
docker compose up -d
docker compose ps
```

Expected starter services:

- `plex`
- `immich-server`
- `immich-machine-learning`
- `database`
- `redis`
- `linkwarden-db`
- `linkwarden-meilisearch`
- `linkwarden`
- `freshrss`
- `homarr`
- `portainer`
- `dozzle`
- `watchtower`
- `duplicati`
- `tautulli`
- `docker-socket-proxy`

## 7. First URLs

| Service | URL |
|:--------|:----|
| Homarr | `http://your-server:3002` |
| Plex | `http://your-server:32400/web` |
| Immich | `http://your-server:2283` |
| Linkwarden | `http://your-server:3006` |
| FreshRSS | `http://your-server:8083` |
| Portainer | `https://your-server:9443` |
| Dozzle | `http://your-server:8889` |
| Duplicati | `http://your-server:8200` |
| Tautulli | `http://your-server:8181` |

## 8. Add More Later

When the starter stack is stable, layer on bundles instead of editing compose includes:

```bash
make init BUNDLES="media"
make up BUNDLES="media" PROFILES="arr jellyfin"
```

More examples live in [Bundles](bundles.md).
