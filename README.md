<div align="center">

# 🏠 Media Stack

### Self-Hosted Homelab Infrastructure

[![Docker](https://img.shields.io/badge/Docker-27+-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-v2-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Maintained](https://img.shields.io/badge/Maintained-Yes-brightgreen?style=for-the-badge)](https://github.com)

*A complete, modular, production-ready Docker Compose setup for running your own media, photo, productivity, monitoring, and automation services.*

[Quick Start](#-quick-start) •
[Documentation](#-documentation) •
[Services](#-whats-included) •
[Support](#-getting-help)

---

</div>

## 🎯 Overview

```mermaid
graph LR
    subgraph INTERNET["🌐 Internet"]
        Users["Users"]
    end

    subgraph GATEWAY["🔐 Gateway"]
        Tunnel["Pangolin/Newt"]
        VPN["Gluetun VPN"]
    end

    subgraph SERVICES["🏠 Media Stack"]
        Media["🎬 Media<br/>Plex, Jellyfin"]
        Photos["📷 Photos<br/>Immich"]
        Arr["📺 *Arr Stack<br/>Radarr, Sonarr"]
        Monitor["📊 Monitoring<br/>Grafana"]
    end

    Users --> Tunnel
    Tunnel --> Media
    Tunnel --> Photos
    Tunnel --> Monitor
    VPN --> Arr

    style SERVICES fill:#1a1a2e,color:#fff
    style GATEWAY fill:#16213e,color:#fff
```

## ✨ What's Included

<table>
<tr>
<td width="33%">

### 🎬 Media
- Plex & Jellyfin
- *Arr Stack (Radarr, Sonarr, etc.)
- Immich (Photos)
- Kavita & Navidrome

</td>
<td width="33%">

### 🧠 Productivity
- FreshRSS & SearXNG
- Syncthing
- Joplin Server
- Optional Kasm

</td>
<td width="33%">

### 🔧 Operations
- Portainer
- Prometheus + Grafana
- Watchtower
- Homarr Dashboard
- Duplicati Backups

</td>
</tr>
</table>

> **50+ services** organized into modular compose files. Enable only what you need.

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/media-stack.git /opt/media-stack
cd /opt/media-stack

# 2. Bootstrap environment
make init-env
nano .env  # Edit host paths, domain, API keys, and optional settings

# `make init-env` copies `.env.example` to `.env` when needed
# and generates any missing required secrets automatically.

# 3. Create directories
sudo mkdir -p /opt/media-stack/data /mnt/media/{Movies,TV,Music,Photos,Sync}
sudo chown -R $USER:$USER /opt/media-stack /mnt/media

# 4. Launch!
docker compose up -d
```

The stack now fails fast during `docker compose config` and `docker compose up -d` if required secrets are unset, and `make init-env` fills those required secrets for first-time setup.

```bash
# Optional: discover the repo's common operator shortcuts
make help
```

> [!TIP]
> First-time setup? See the [Quick Start Guide](docs/quickstart.md) for detailed instructions.

---

## 📚 Documentation

| Document | Description |
|:---------|:------------|
| [🚀 Quick Start Guide](docs/quickstart.md) | First-time setup, prerequisites, installation |
| [🏗️ Architecture](docs/architecture.md) | System diagrams, data flows, design decisions |
| [📦 Services Catalog](docs/services.md) | Complete list of services with ports and status |
| [⚙️ Configuration](docs/configuration.md) | Module system, profiles, environment variables |
| [🌐 Networking](docs/networking.md) | Network topology, VPN routing, port reference |
| [📊 Monitoring](docs/monitoring.md) | Prometheus, Grafana, alerting setup |
| [📋 Logging](docs/logging.md) | Simple container logging with Loki and Promtail |
| [💾 Backup & Recovery](docs/backup.md) | Backup strategy, schedules, restore procedures |
| [🔧 Troubleshooting](docs/troubleshooting.md) | Common issues, FAQ, debugging commands |
| [🛠️ Utility Scripts](docs/scripts.md) | Template sync and repo validation utilities |

---

## 🗂️ Project Structure

```
.
├── docker-compose.yml          # Main orchestration (includes modules)
├── docker-compose.*.yml        # Service modules
├── docker-compose.local.example.yml # Host-specific override example
├── hwaccel.*.yml               # Hardware acceleration configs
├── .env.example                # Configuration template
├── docs/                       # 📚 Documentation
├── config-templates/           # Git-tracked config templates
└── data/                       # Runtime data (gitignored)
```

---

## 🎯 Common Tasks

<details>
<summary><strong>Start/Stop Services</strong></summary>

```bash
# Start all services
docker compose up -d

# Start with optional profiles
docker compose --profile speedtest --profile scrutiny up -d

# Start optional Kasm workspaces
docker compose --profile kasm up -d

# Stop everything
docker compose down

# Restart a service
docker compose restart plex
```

```bash
# Or use the Makefile wrappers
make up PROFILES="speedtest scrutiny"
make restart SERVICE=plex
make logs SERVICE=plex
```

</details>

<details>
<summary><strong>Update Containers</strong></summary>

```bash
# Update all
docker compose pull && docker compose up -d

# Update specific service
docker compose pull plex && docker compose up -d plex

# Validate stack consistency and config drift
make check
```

LinuxServer.io containers are intentionally opted out of Watchtower in this repo. Update those with `docker compose pull <service> && docker compose up -d <service>` after reviewing release notes.

</details>

<details>
<summary><strong>View Logs</strong></summary>

```bash
# Follow all logs
docker compose logs -f

# Specific service
docker compose logs -f plex

# Or use Dozzle UI at http://your-server:8889
```

</details>

<details>
<summary><strong>Access Services</strong></summary>

| Service | URL |
|:--------|:----|
| Homarr | `http://your-server:3002` |
| Plex | `http://your-server:32400/web` |
| Immich | `http://your-server:2283` |
| FreshRSS | `http://your-server:8081` |
| Joplin | `http://your-server:22300` |
| Grafana | `http://your-server:3000` |
| Portainer | `https://your-server:9443` |

See [Services Catalog](docs/services.md) for complete list.

</details>

---

## 🔒 Security Highlights

```mermaid
graph LR
    subgraph SECURITY["Security Layers"]
        VPN["🔒 VPN Routing<br/>Download traffic"]
        Proxy["🛡️ Socket Proxy<br/>Docker API"]
        Priv["🔐 No-New-Privileges<br/>All containers"]
        Tunnel["🚇 Secure Tunnel<br/>External access"]
    end

    style SECURITY fill:#27ae60,color:#fff
```

- **VPN Routing** - Download traffic through Gluetun (Mullvad/NordVPN)
- **Docker Socket Proxy** - Secure API access for containers
- **No-New-Privileges** - Applied to all containers
- **Pangolin/Newt** - Secure external tunneling

See [Configuration Guide](docs/configuration.md#security) for security best practices.

---

## 📋 Requirements

| Component | Minimum | Recommended |
|:----------|:-------:|:-----------:|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 50 GB SSD | 100+ GB NVMe |
| OS | Ubuntu 22.04 | Ubuntu 24.04 LTS |

> [!NOTE]
> **Optional:** NVIDIA GPU for hardware transcoding & Immich ML acceleration.

---

## 🆘 Getting Help

1. **Check the docs** - Start with [Troubleshooting](docs/troubleshooting.md)
2. **View logs** - `docker compose logs [service]` or use Dozzle
3. **Search issues** - Check existing GitHub issues

### Useful Resources

- [LinuxServer.io Docs](https://docs.linuxserver.io/) - Container documentation
- [Trash Guides](https://trash-guides.info/) - *Arr best practices
- [Servarr Wiki](https://wiki.servarr.com/) - *Arr suite documentation
- [r/selfhosted](https://reddit.com/r/selfhosted) - Community support

---

<div align="center">

## 📜 License

This project is provided as-is for personal use.
Individual services have their own licenses.

---

**Made with ❤️ for the self-hosting community**

</div>
