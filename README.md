# Media Stack - Self-Hosted Homelab Infrastructure

A complete, modular Docker Compose setup for running your own media server, photo management, monitoring, and automation services.

---

## What's Included?

| Category | Services |
|----------|----------|
| **Media Servers** | Plex, Jellyfin, Tdarr (transcoding), Kavita (ebooks), Navidrome (music) |
| **Media Management** | Radarr (movies), Sonarr (TV), Lidarr (music), Readarr (books), Bazarr (subtitles), Plex Meta Manager, Maintainerr |
| **Downloaders** | qBittorrent, Prowlarr (indexers), FlareSolverr, Bitmagnet |
| **Photos** | Immich (Google Photos alternative) |
| **Requests** | Overseerr, Jellyseerr (let users request media) |
| **Monitoring** | Prometheus, Grafana, Uptime Kuma, Alertmanager, Tautulli, Speedtest Tracker, Scrutiny (disk health) |
| **Logging** | Loki, Promtail, Vector (centralized logs) |
| **Management** | Portainer, Watchtower (auto-updates), Homepage (dashboard), Dozzle (log viewer) |
| **Utilities** | IT-Tools, Stirling PDF |
| **Backup** | Duplicati, Restic, database backups |
| **Automation** | n8n (workflow automation) |
| **VPN** | Gluetun (route traffic through VPN) |
| **Tunnel** | Newt/Pangolin (secure tunneling & auth) |

---

## Prerequisites

Before you start, make sure you have:

### 1. A Linux Server (or VM)
- Ubuntu 22.04+ or Debian 12+ recommended
- At least 8GB RAM (16GB+ recommended)
- At least 50GB for Docker configs (SSD recommended)
- Storage for your media files

### 2. Docker & Docker Compose

**Install Docker (Ubuntu/Debian):**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add your user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
docker compose version
```

### 3. Find Your User ID and Group ID
```bash
# Run this command and note the numbers
id

# Example output: uid=1000(youruser) gid=1000(youruser)
# You'll use 1000 for both PUID and PGID
```

### 4. (Optional) NVIDIA GPU for Hardware Transcoding
```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-535

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU is available to Docker
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## Quick Start Guide

### Step 1: Clone or Download This Repository

```bash
# Option A: Clone with git
git clone https://github.com/yourusername/media-stack.git
cd media-stack

# Option B: Or just download and extract the files to a directory
cd /opt/docker  # or wherever you want
```

### Step 2: Create Your Environment File

```bash
# Copy the example file
cp .env.example .env

# Edit it with your favorite editor
nano .env
```

**Minimum required changes in `.env`:**

```bash
# Your user/group IDs (from 'id' command)
PUID=1000
PGID=1000

# Your timezone (find yours: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
TZ=America/New_York

# Where to store Docker container configs
DOCKER_BASE_DIR=/opt/docker

# Where your media files are stored
DOCKER_MEDIA_DIR=/mnt/media

# For Immich (photo management) - set a secure password!
DB_PASSWORD=CHANGE_THIS_TO_A_SECURE_PASSWORD
```

### Step 3: Create Required Directories

```bash
# Create the base directory structure
sudo mkdir -p /opt/docker
sudo chown -R $USER:$USER /opt/docker

# Create media directories (adjust paths as needed)
sudo mkdir -p /mnt/media/{Movies,TV,Music,Books,Comics,Downloads,Photos,Songs}
sudo chown -R $USER:$USER /mnt/media

# Create config directories for new services
mkdir -p /opt/docker/{homepage,speedtest-tracker,scrutiny,tautulli,plex-meta-manager,maintainerr,kavita,navidrome,stirling-pdf}
```

### Step 4: Choose What to Run

Edit `docker-compose.yml` to enable/disable services by commenting/uncommenting lines:

```yaml
include:
  # Core (always needed)
  - docker-compose.common.yml
  - docker-compose.core.yml
  
  # Choose what you want:
  - docker-compose.photos.yml           # Immich photo management
  - docker-compose.media-servers.yml    # Plex, Jellyfin, Tdarr
  - docker-compose.media-extras.yml     # Tautulli, PMM, Maintainerr, Kavita, Navidrome
  - docker-compose.utilities.yml        # Homepage, Dozzle, IT-Tools, Stirling PDF
  # - docker-compose.arr.yml            # Radarr, Sonarr, etc.
  # - docker-compose.downloaders.yml    # qBittorrent, Prowlarr
  - docker-compose.requests.yml         # Overseerr
  - docker-compose.management.yml       # Portainer, Watchtower
  - docker-compose.monitoring.yml       # Prometheus, Grafana, Uptime Kuma
  # - docker-compose.logging.yml        # Loki (centralized logs)
  - docker-compose.backup.yml           # Duplicati
  # - docker-compose.automation.yml     # n8n
  # - docker-compose.files.yml          # Nextcloud
```

### Step 5: Start Everything!

```bash
# Validate your configuration first
docker compose config

# Start all services
docker compose up -d

# Start with optional profiles (Speedtest, Scrutiny, Kavita, Navidrome)
docker compose --profile speedtest --profile scrutiny --profile kavita --profile navidrome up -d

# Watch the logs to make sure everything starts
docker compose logs -f

# Press Ctrl+C to stop watching logs (services keep running)
```

### Step 6: Access Your Services

| Service | Port | URL | Default Login |
|---------|------|-----|---------------|
| **Dashboards** |
| Homepage | 3002 | http://your-server-ip:3002 | None |
| Portainer | 9443 | https://your-server-ip:9443 | Create on first visit |
| **Media Servers** |
| Plex | 32400 | http://your-server-ip:32400/web | Plex account |
| Jellyfin | 8096 | http://your-server-ip:8096 | Create on first visit |
| Kavita | 5000 | http://your-server-ip:5000 | Create on first visit |
| Navidrome | 4533 | http://your-server-ip:4533 | Create on first visit |
| Tautulli | 8181 | http://your-server-ip:8181 | None |
| **Photos** |
| Immich | 2283 | http://your-server-ip:2283 | Create on first visit |
| **Media Management** |
| Overseerr | 5055 | http://your-server-ip:5055 | Create on first visit |
| Maintainerr | 6246 | http://your-server-ip:6246 | None |
| Radarr | 7878 | http://your-server-ip:7878 | None |
| Sonarr | 8989 | http://your-server-ip:8989 | None |
| **Monitoring** |
| Grafana | 3000 | http://your-server-ip:3000 | admin / admin |
| Prometheus | 9090 | http://your-server-ip:9090 | None |
| Uptime Kuma | 3001 | http://your-server-ip:3001 | Create on first visit |
| Speedtest Tracker | 8765 | http://your-server-ip:8765 | admin@example.com / password |
| Scrutiny | 8082 | http://your-server-ip:8082 | None |
| **Utilities** |
| Dozzle | 8889 | http://your-server-ip:8889 | None |
| IT-Tools | 8083 | http://your-server-ip:8083 | None |
| Stirling PDF | 8084 | http://your-server-ip:8084 | None |
| Duplicati | 8200 | http://your-server-ip:8200 | None |

---

## Available Profiles

Some services are optional and enabled via profiles:

```bash
# Enable individual profiles
docker compose --profile speedtest up -d
docker compose --profile scrutiny up -d
docker compose --profile kavita up -d
docker compose --profile navidrome up -d

# Enable multiple profiles at once
docker compose --profile speedtest --profile scrutiny --profile kavita --profile navidrome up -d
```

| Profile | Services | Description |
|---------|----------|-------------|
| `monitoring` | Glances | System resource monitor |
| `dashboard` | Glance Homepage | Alternative dashboard |
| `jellyfin` | Jellyfin, Jellyseerr | Alternative to Plex |
| `stash` | Stash | Adult media organizer |
| `tdarr` | Tdarr | Media transcoding |
| `notifiarr` | Notifiarr | Unified notifications |
| `restic` | Restic Server | Backup repository |
| `db-backup` | DB Backup | Database backups |
| `scrutiny` | Scrutiny | Disk S.M.A.R.T monitoring |
| `speedtest` | Speedtest Tracker | Internet speed history |
| `kavita` | Kavita | Ebook/comic server |
| `navidrome` | Navidrome | Music streaming |
| `vector` | Vector | Log pipeline/aggregator |

---

## Post-Installation Configuration

### 1. Configure Homepage Dashboard

Homepage is pre-configured to discover services via Docker labels. To add API keys for widgets:

1. Add API keys to your `.env` file:
```bash
PLEX_API_KEY=your_plex_token
TAUTULLI_API_KEY=your_tautulli_key
OVERSEERR_API_KEY=your_overseerr_key
RADARR_API_KEY=your_radarr_key
SONARR_API_KEY=your_sonarr_key
```

2. Restart Homepage:
```bash
docker compose restart homepage
```

3. Customize settings in `/opt/docker/homepage/`:
   - `settings.yaml` - Theme, layout, background
   - `services.yaml` - Service widgets
   - `widgets.yaml` - Top bar widgets
   - `bookmarks.yaml` - Quick links

### 2. Configure Plex Meta Manager

Edit `/opt/docker/plex-meta-manager/config.yml`:

```yaml
plex:
  url: http://plex:32400
  token: YOUR_PLEX_TOKEN  # Get from: https://support.plex.tv/articles/204059436

tmdb:
  apikey: YOUR_TMDB_API_KEY  # Get from: https://www.themoviedb.org/settings/api
```

### 3. Configure Maintainerr

1. Visit http://your-server-ip:6246
2. Connect to Plex server
3. (Optional) Connect to Overseerr, Radarr, Sonarr
4. Create cleanup rules for unwatched/old media

### 4. Configure Scrutiny

Scrutiny is pre-configured with your detected disks. Access http://your-server-ip:8082 to view disk health.

To add/remove disks, edit `docker-compose.utilities.yml`:
```yaml
devices:
  - /dev/sda:/dev/sda
  - /dev/sdb:/dev/sdb
  - /dev/sdc:/dev/sdc
```

---

## Common Scenarios

### Scenario 1: "I Just Want Plex and Immich"

1. Edit `.env` with your settings
2. In `docker-compose.yml`, keep only:
   ```yaml
   include:
     - docker-compose.common.yml
     - docker-compose.core.yml
     - docker-compose.photos.yml
     - docker-compose.media-servers.yml
     - docker-compose.management.yml
   ```
3. Run `docker compose up -d`

### Scenario 2: "I Want the Full *Arr Stack for Automated Downloads"

**Important:** You need a VPN for this! Get one from Mullvad, NordVPN, etc.

1. Edit `.env` and add VPN credentials:
   ```bash
   VPN_SERVICE_PROVIDER=mullvad
   OPENVPN_USER=your_account_number
   OPENVPN_PASSWORD=not_needed_for_mullvad
   SERVER_REGIONS=us
   ```

2. In `docker-compose.yml`, enable:
   ```yaml
   include:
     - docker-compose.common.yml
     - docker-compose.core.yml
     - docker-compose.media-servers.yml
     - docker-compose.media-extras.yml
     - docker-compose.arr.yml
     - docker-compose.downloaders.yml
     - docker-compose.requests.yml
     - docker-compose.management.yml
     - docker-compose.utilities.yml
   ```

3. Run `docker compose up -d`

### Scenario 3: "Full Stack with All Monitoring"

```yaml
include:
  - docker-compose.common.yml
  - docker-compose.core.yml
  - docker-compose.photos.yml
  - docker-compose.media-servers.yml
  - docker-compose.media-extras.yml
  - docker-compose.requests.yml
  - docker-compose.management.yml
  - docker-compose.monitoring.yml
  - docker-compose.backup.yml
  - docker-compose.utilities.yml
```

Then run with profiles:
```bash
docker compose --profile speedtest --profile scrutiny --profile kavita --profile navidrome up -d
```

---

## Directory Structure Explained

```
/opt/docker/                    # Base config directory
├── plex/                       # Plex configuration
├── immich/                     # Immich configuration  
├── radarr/                     # Radarr configuration
├── sonarr/                     # Sonarr configuration
├── qbittorrent/                # qBittorrent configuration
├── homepage/                   # Homepage dashboard config
│   ├── settings.yaml           # Theme and layout
│   ├── services.yaml           # Service widgets
│   ├── widgets.yaml            # Top bar widgets
│   └── bookmarks.yaml          # Quick links
├── plex-meta-manager/          # PMM configuration
│   └── config.yml              # PMM settings
├── tautulli/                   # Tautulli (Plex stats)
├── maintainerr/                # Maintainerr (cleanup)
├── kavita/                     # Kavita (ebooks)
├── navidrome/                  # Navidrome (music)
├── scrutiny/                   # Disk health monitoring
├── speedtest-tracker/          # Internet speed history
├── stirling-pdf/               # PDF tools
├── ... (one folder per service)

/mnt/media/                     # Your media files
├── Movies/                     # Movie files
├── TV/                         # TV show files
├── Songs/                      # Music files (for Navidrome)
├── Books/                      # Ebook files (for Kavita)
├── Comics/                     # Comic files (for Kavita)
├── Downloads/                  # Download directory
│   ├── complete/               # Completed downloads
│   └── incomplete/             # In-progress downloads
├── Photos/                     # Photos for Immich
```

---

## Essential Commands

### Managing Services

```bash
# Start everything
docker compose up -d

# Start with profiles
docker compose --profile speedtest --profile scrutiny up -d

# Stop everything
docker compose down

# Restart a specific service
docker compose restart plex

# View logs for a service
docker compose logs -f plex

# View logs for all services
docker compose logs -f

# Check status of all services
docker compose ps

# Update all containers to latest versions
docker compose pull && docker compose up -d
```

### Troubleshooting

```bash
# Check if a container is healthy
docker inspect --format='{{.State.Health.Status}}' plex

# Get a shell inside a container
docker exec -it plex /bin/bash

# Check resource usage
docker stats

# View container details
docker inspect plex

# Force recreate a container
docker compose up -d --force-recreate plex

# Remove unused Docker data (careful!)
docker system prune -a
```

---

## Troubleshooting Guide

### "Container keeps restarting"

```bash
# Check the logs
docker compose logs plex

# Common causes:
# - Wrong permissions (check PUID/PGID)
# - Missing directories
# - Port already in use
```

### "Permission denied" errors

```bash
# Make sure directories are owned by your user
sudo chown -R $USER:$USER /opt/docker
sudo chown -R $USER:$USER /mnt/media

# Check PUID and PGID in .env match your user
id  # Shows your uid and gid
```

### "Port already in use"

```bash
# Find what's using the port
sudo lsof -i :8080

# Either stop that service or change the port in docker-compose
```

### "Container is unhealthy"

```bash
# Check what the health check is testing
docker inspect plex | grep -A 10 "Healthcheck"

# Usually means the service inside isn't responding yet
# Wait a minute and check again, or check logs
```

### "Can't connect to service"

1. Check the container is running: `docker compose ps`
2. Check the container is healthy: `docker inspect --format='{{.State.Health.Status}}' containername`
3. Check firewall isn't blocking: `sudo ufw status`
4. Make sure you're using the right port

### "VPN not working" (Gluetun)

```bash
# Check Gluetun logs
docker compose logs gluetun

# Verify VPN is connected
docker exec gluetun curl ifconfig.me
# Should show VPN IP, not your real IP
```

---

## Updating Services

### Update Everything

```bash
# Pull latest images and recreate containers
docker compose pull
docker compose up -d
```

### Update a Single Service

```bash
docker compose pull plex
docker compose up -d plex
```

### Automatic Updates with Watchtower

Watchtower (included in management.yml) automatically updates containers daily at 4 AM. To change the schedule, edit the `WATCHTOWER_SCHEDULE` in `docker-compose.management.yml`.

**Note:** Immich is excluded from Watchtower auto-updates to prevent issues during photo processing. Update Immich manually.

---

## Backup & Restore

### What to Backup

1. **Essential**: Your `.env` file
2. **Important**: The entire `/opt/docker` directory (all configs)
3. **Optional**: Media files (if you can't re-download them)

### Quick Backup

```bash
# Backup configs
tar -czvf docker-backup-$(date +%Y%m%d).tar.gz /opt/docker

# Backup .env separately (it has your passwords!)
cp .env .env.backup
```

### Using Duplicati (Included)

1. Enable backup in `docker-compose.yml`
2. Access Duplicati at http://your-server-ip:8200
3. Set up backup jobs to cloud storage (Google Drive, Backblaze, etc.)

### Database Backups

Enable the `db-backup` profile for automatic PostgreSQL backups:
```bash
docker compose --profile db-backup up -d
```

---

## Security Tips

1. **Change default passwords** in `.env` before starting
2. **Use a VPN** for downloading (Gluetun is included)
3. **Don't expose ports** directly to the internet - use Pangolin/Newt or Cloudflare Tunnel
4. **Keep services updated** - Watchtower does this automatically
5. **Backup regularly** - Use Duplicati to backup to cloud storage
6. **Use Pangolin** for authentication and reverse proxy (already configured)

---

## Getting Help

### Resources

- [LinuxServer.io Docs](https://docs.linuxserver.io/) - Most container documentation
- [Trash Guides](https://trash-guides.info/) - Best practices for *Arr apps
- [Immich Docs](https://immich.app/docs) - Photo management setup
- [Servarr Wiki](https://wiki.servarr.com/) - *Arr suite documentation
- [Homepage Docs](https://gethomepage.dev/) - Dashboard configuration
- [Plex Meta Manager Wiki](https://metamanager.wiki/) - PMM configuration

### Check Logs First

Before asking for help, always check the logs:

```bash
docker compose logs -f servicename
```

### Use Dozzle for Easy Log Viewing

Access http://your-server-ip:8889 to view all container logs in real-time with a nice UI.

---

## FAQ

**Q: How much disk space do I need?**
A: About 1-2GB for Docker configs. Media storage depends on your library size.

**Q: Can I run this on a Raspberry Pi?**
A: Some services yes, but Plex transcoding and Immich ML need more power. A Pi 4 with 8GB can run light services.

**Q: Do I need a domain name?**
A: No, you can access everything via IP:port. A domain is only needed for SSL/HTTPS or if using Pangolin.

**Q: Is this legal?**
A: The software is legal. What you download is your responsibility.

**Q: How do I add more storage?**
A: Mount additional drives and update paths in `.env` or create symlinks in your media directory.

**Q: Why is Immich excluded from Watchtower?**
A: Immich recommends staying on specific versions and updating manually to prevent issues during ML processing.

---

## File Reference

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Main file - controls which modules are enabled |
| `docker-compose.common.yml` | Shared settings and templates |
| `docker-compose.core.yml` | VPN (Gluetun) and tunnel (Newt) services |
| `docker-compose.photos.yml` | Immich photo management |
| `docker-compose.media-servers.yml` | Plex, Jellyfin, Stash, Tdarr |
| `docker-compose.media-extras.yml` | Tautulli, Plex Meta Manager, Maintainerr, Kavita, Navidrome |
| `docker-compose.arr.yml` | Radarr, Sonarr, Lidarr, Readarr, Bazarr, Whisparr, Recyclarr |
| `docker-compose.downloaders.yml` | qBittorrent, Prowlarr, FlareSolverr, Bitmagnet |
| `docker-compose.requests.yml` | Overseerr, Jellyseerr, Notifiarr |
| `docker-compose.monitoring.yml` | Prometheus, Grafana, Alertmanager, InfluxDB, Telegraf, Uptime Kuma, cAdvisor, Node Exporter |
| `docker-compose.logging.yml` | Loki, Promtail, Vector |
| `docker-compose.management.yml` | Portainer, Watchtower, Glances, Glance Homepage |
| `docker-compose.utilities.yml` | Homepage, Speedtest Tracker, Scrutiny, Dozzle, IT-Tools, Stirling PDF |
| `docker-compose.backup.yml` | Duplicati, Restic, DB Backup |
| `docker-compose.automation.yml` | n8n workflow automation |
| `docker-compose.files.yml` | Nextcloud |
| `hwaccel.transcoding.yml` | Hardware acceleration for video transcoding |
| `hwaccel.ml.yml` | Hardware acceleration for machine learning |
| `.env.example` | Template for environment variables |
| `.env` | Your configuration (create from .env.example) |
| `configs/` | Application configuration files |
| `AGENTS.md` | Guidelines for AI coding agents |

---

## License

This project is provided as-is for personal use. Individual services have their own licenses.

---

**Happy Self-Hosting!**
