# Backup & Recovery Guide

[← Back to README](../README.md)

Simple backup guidance for this homelab.

---

## Overview

This repo now treats backups in three layers:

- `Duplicati` is the main backup tool and is enabled by default
- `db-backup` is an optional PostgreSQL dump worker for the starter Immich database
- `scripts/erpnext-backup.sh` is the host-side ERPNext backup entrypoint for the apps bundle
- `restic-rest-server` is an optional advanced endpoint, not the default workflow

For a beginner setup, the easiest mental model is:

1. Duplicati backs up `${DOCKER_BASE_DIR}`
2. `db-backup` writes SQL dumps into `${DOCKER_BASE_DIR}/db-backup`
3. `scripts/erpnext-backup.sh` writes ERPNext site backups under `${DOCKER_BASE_DIR}/erpnext/sites`
4. That means both Immich dumps and ERPNext backups are automatically included in your main Duplicati backups once they exist

---

## What Gets Backed Up

### Default Duplicati Sources

The `duplicati` service mounts these sources:

| Source in Duplicati | What it contains |
|:--------------------|:-----------------|
| `/source/docker-configs` | All service data under `${DOCKER_BASE_DIR}` |
| `/source/project/.env` | Your main stack secrets and environment config |

### Important Notes

- `${DOCKER_BASE_DIR}` already includes service config for Grafana, Prometheus, Homarr, Uptime Kuma, Plex, Immich, and the rest of the stack
- Homarr customizations live under `${DOCKER_BASE_DIR}/homarr/appdata`; keep that directory and the matching `HOMARR_SECRET_ENCRYPTION_KEY` together when moving to a new server
- if you enable `db-backup`, its dumps appear under `${DOCKER_BASE_DIR}/db-backup`, so they are already covered by `/source/docker-configs`
- ERPNext backup artifacts live under `${DOCKER_BASE_DIR}/erpnext/sites/<site>/private/backups`, so they are also already covered by `/source/docker-configs`
- `karakeep/data`, `karakeep/meilisearch`, `docmost/storage`, `paperless/media`, and the rest of the application files already live under `${DOCKER_BASE_DIR}` and are included in the main Duplicati source tree
- media libraries and original photo libraries should use a separate large-data backup strategy

---

## Recommended Setup

### Duplicati

Duplicati is the primary backup path for this repo.

Start it with the normal stack:

```bash
docker compose up -d duplicati
```

Open `http://your-server:8200` and create one main job first.

### Recommended First Job

| Setting | Value |
|:--------|:------|
| Name | `Homelab Config Backup` |
| Sources | `/source/docker-configs`, `/source/project/.env` |
| Destination | `/backups` or your cloud destination |
| Encryption | Enabled |
| Schedule | Daily |

> Always encrypt backups that include `.env` because that file contains secrets.

### Backup Destination Variables

Relevant variables in `.env`:

```bash
BACKUP_DESTINATION=/mnt/backup
DUPLICATI_ENCRYPTION_KEY=your_generated_key
```

---

## Database Backups

### db-backup Profile

Enable SQL dumps with:

```bash
make up BUNDLES="ops" PROFILES="db-backup"
```

What it does:

- connects to the starter Immich PostgreSQL service
- creates compressed dumps on a schedule
- stores them in `${DOCKER_BASE_DIR}/db-backup`

That output is already inside the main Duplicati source tree.

### Verify It Works

```bash
docker compose ps db-backup
docker compose logs db-backup --tail 50
ls -la ${DOCKER_BASE_DIR}/db-backup
find ${DOCKER_BASE_DIR}/db-backup -maxdepth 2 -type f | grep immich
```

### ERPNext Host Cron Backup

ERPNext uses the tracked host-side helper instead of widening Docker socket permissions for a scheduler sidecar.

Run a manual backup with:

```bash
/bin/bash ./scripts/erpnext-backup.sh
```

Install this crontab entry for the daily backup:

```cron
0 4 * * * cd /mnt/g/docker && /bin/bash ./scripts/erpnext-backup.sh >> /mnt/g/docker/data/erpnext/backup-cron.log 2>&1
```

Verify ERPNext backups with:

```bash
find ${DOCKER_BASE_DIR}/erpnext/sites -path '*/private/backups/*' -type f | sort
```

---

## Restic Server

The `restic` profile only starts a Restic repository server in the `ops` bundle:

```bash
make up BUNDLES="ops" PROFILES="restic"
```

This is for advanced setups where you already use Restic clients elsewhere. It is not required for the default backup workflow.

---

## Manual Safety Copies

Even with Duplicati enabled, keep a separate copy of your most important secrets.

### Back Up `.env` Manually

```bash
cp /opt/media-stack/.env /opt/media-stack/.env.backup.$(date +%Y%m%d)
```

### Back Up All Config Data Manually

```bash
tar -czvf media-stack-configs-$(date +%Y%m%d).tar.gz /opt/media-stack/data
```

---

## Restore Basics

### Restore from Duplicati

1. Open Duplicati
2. Choose the backup job
3. Restore `${DOCKER_BASE_DIR}` contents first
4. Restore `.env`
5. Start the stack again with `docker compose up -d`

### Restore Immich Database Dump

```bash
gunzip -c immich_backup_YYYYMMDD.sql.gz | docker exec -i immich_postgres psql -U postgres immich
```

### Restore Joplin Database Dump

```bash
gunzip -c joplin_backup_YYYYMMDD.sql.gz | docker exec -i joplin-postgres psql -U joplin joplin
```

### Restore ERPNext Backup Files

ERPNext backups are generated by bench and stored inside the ERPNext sites tree. Restore them from the relevant site backup directory after the ERPNext stack is running again.

---

## Beginner Checklist

- Duplicati opens at `http://your-server:8200`
- one encrypted backup job exists for `/source/docker-configs` and `/source/project/.env`
- `db-backup` is enabled if you want scheduled Immich PostgreSQL dumps
- `scripts/erpnext-backup.sh` runs successfully if ERPNext is enabled
- `${BACKUP_DESTINATION}` has enough free space
- media files follow a separate backup plan

This keeps the backup story simple: one main backup tool, one optional database dump helper, and one advanced Restic endpoint only if you need it.
