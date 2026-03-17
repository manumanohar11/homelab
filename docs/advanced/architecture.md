# Advanced Architecture

[Back to README](../../README.md)

The repo is organized around one starter entrypoint plus four optional bundles.

## Mental Model

- `docker-compose.yml` is the smallest useful homelab.
- `media` adds VPN-routed automation and alternate media apps.
- `apps` adds productivity, documents, files, and automation.
- `ops` adds observability and advanced backup tooling.
- `access` adds Pangolin/Newt and Jitsi.

## Key Dependencies

- Starter services depend only on local Docker networking and the starter `.env`.
- Media services depend on `gluetun` and, for *Arr, `prowlarr` and `qbittorrent`.
- Ops services depend on starter services such as `docker-socket-proxy` and the tracked config templates.
- Access services depend on bundle-specific credentials and DNS/networking outside the repo.
