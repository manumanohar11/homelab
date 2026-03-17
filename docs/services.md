# Services

[Back to README](../README.md)

This is a bundle-oriented service catalog.

## Starter Services

| Service | Port | Notes |
|:--------|:----:|:------|
| Plex | 32400 | Starter media server |
| Immich Server | 2283 | Starter photo UI and API |
| Immich ML | - | Face/object processing |
| Immich PostgreSQL | 5432 | Immich database |
| Immich Redis | 6379 | Immich cache |
| Homarr | 3002 | Starter dashboard |
| Portainer | 9443 | Container management |
| Dozzle | 8889 | Live logs |
| Watchtower | - | Image update automation |
| Duplicati | 8200 | Starter backups |
| Tautulli | 8181 | Plex stats |
| Docker Socket Proxy | - | Filtered Docker API for starter tools |

## Media Bundle

| Group | Services |
|:------|:---------|
| VPN | Gluetun |
| *Arr | Radarr, Sonarr, Lidarr, Readarr, Bazarr, Whisparr, Recyclarr |
| Downloaders | qBittorrent, Prowlarr, FlareSolverr, Bitmagnet |
| Requests | Overseerr, Jellyseerr, Notifiarr |
| Alternate Media Apps | Jellyfin, Stash, Kavita, Navidrome, Tdarr, Maintainerr |

## Apps Bundle

| Group | Services |
|:------|:---------|
| Productivity | FreshRSS, SearXNG, Syncthing, Joplin, Kasm |
| Documents | Paperless-ngx, Stirling PDF |
| Knowledge | Karakeep, Docmost |
| Files & Automation | Nextcloud, n8n |

## Ops Bundle

| Group | Services |
|:------|:---------|
| Monitoring | Prometheus, Alertmanager, Grafana, Node Exporter, Uptime Kuma |
| Logging | Loki, Promtail |
| Diagnostics | Glances, Glance, Speedtest Tracker, Scrutiny |
| Advanced Backups | Restic REST Server, DB Backup |

## Access Bundle

| Group | Services |
|:------|:---------|
| Remote Access | Newt |
| Private Calling | Jitsi Web, Prosody, Jicofo, JVB, coturn, jitsi-ddns |
