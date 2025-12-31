# 🚀 Quick Start Guide

[← Back to README](../README.md)

Complete guide to getting your Media Stack up and running.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Install Docker](#step-1-install-docker)
- [Step 2: Clone Repository](#step-2-clone-repository)
- [Step 3: Configure Environment](#step-3-configure-environment)
- [Step 4: Create Directories](#step-4-create-directories)
- [Step 5: Choose Your Services](#step-5-choose-your-services)
- [Step 6: Launch](#step-6-launch)
- [Step 7: Initial Setup](#step-7-initial-setup)
- [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|:----------|:-------:|:-----------:|
| **CPU** | 4 cores | 8+ cores |
| **RAM** | 8 GB | 16+ GB |
| **Storage (Configs)** | 50 GB SSD | 100+ GB NVMe |
| **Storage (Media)** | As needed | RAID recommended |
| **OS** | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |

### What You'll Need

- [ ] A Linux server (physical or VM)
- [ ] Root/sudo access
- [ ] Storage for media files
- [ ] (Optional) NVIDIA GPU for transcoding
- [ ] (Optional) VPN subscription for downloads

---

## Step 1: Install Docker

### Ubuntu/Debian

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker using official script
curl -fsSL https://get.docker.com | sudo sh

# Add your user to docker group (no sudo needed for docker commands)
sudo usermod -aG docker $USER

# Apply group changes (or log out and back in)
newgrp docker

# Verify installation
docker --version
docker compose version
```

### Expected Output

```
Docker version 27.x.x, build xxxxxxx
Docker Compose version v2.x.x
```

### (Optional) NVIDIA GPU Setup

If you have an NVIDIA GPU for hardware transcoding:

```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-535

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU is accessible
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## Step 2: Clone Repository

```bash
# Clone to your preferred location
git clone https://github.com/yourusername/media-stack.git /opt/media-stack

# Navigate to directory
cd /opt/media-stack
```

Or download and extract manually:

```bash
# Create directory
sudo mkdir -p /opt/media-stack
cd /opt/media-stack

# Download and extract (if not using git)
# Place all docker-compose files here
```

---

## Step 3: Configure Environment

### Find Your User/Group IDs

```bash
# Run this command
id

# Example output:
# uid=1000(youruser) gid=1000(youruser) groups=1000(youruser),998(docker)
```

Note your `uid` and `gid` (usually both 1000).

### Create Environment File

```bash
# Copy the example file
cp .env.example .env

# Edit with your favorite editor
nano .env
```

### Required Settings

```bash
# ============================================
# REQUIRED CONFIGURATION
# ============================================

# Your user/group IDs (from 'id' command)
PUID=1000
PGID=1000

# Your timezone
# Find yours: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TZ=America/New_York

# Base directory for Docker configs
DOCKER_PROJECT_DIR=/opt/media-stack
DOCKER_BASE_DIR=/opt/media-stack/data

# Media storage location
DOCKER_MEDIA_DIR=/mnt/media

# ============================================
# IMMICH (Photo Management) - REQUIRED
# ============================================

# CRITICAL: Set a secure password!
DB_PASSWORD=change_this_to_a_secure_password_123!

# Photo storage locations
UPLOAD_LOCATION=/mnt/photos/upload
THUMB_LOCATION=/mnt/photos/thumbs
```

### Optional Settings

```bash
# ============================================
# VPN (Required for *Arr stack)
# ============================================

VPN_SERVICE_PROVIDER=mullvad
OPENVPN_USER=your_mullvad_account_number
SERVER_REGIONS=us

# ============================================
# API KEYS (For Homepage widgets)
# ============================================

PLEX_API_KEY=your_plex_token
TAUTULLI_API_KEY=your_tautulli_key
```

---

## Step 4: Create Directories

### Config Directories

```bash
# Create base config directory
sudo mkdir -p /opt/media-stack/data
sudo chown -R $USER:$USER /opt/media-stack
```

### Media Directories

```bash
# Create media library structure
sudo mkdir -p /mnt/media/{Movies,TV,Music,Books,Comics,Downloads,Photos}
sudo chown -R $USER:$USER /mnt/media

# Create photo directories for Immich
sudo mkdir -p /mnt/photos/{upload,thumbs,encoded-video,profile,backups}
sudo chown -R $USER:$USER /mnt/photos
```

### Verify Structure

```bash
tree -L 2 /mnt/media /mnt/photos 2>/dev/null || ls -la /mnt/media /mnt/photos
```

Expected:
```
/mnt/media
├── Books
├── Comics
├── Downloads
├── Movies
├── Music
├── Photos
└── TV

/mnt/photos
├── backups
├── encoded-video
├── profile
├── thumbs
└── upload
```

---

## Step 5: Choose Your Services

Edit `docker-compose.yml` to enable/disable service modules:

```yaml
include:
  # Core (always required)
  - docker-compose.common.yml
  - docker-compose.core.yml

  # Choose what you want:
  - docker-compose.photos.yml           # ✅ Immich photo management
  - docker-compose.media-servers.yml    # ✅ Plex, Jellyfin
  - docker-compose.media-extras.yml     # ✅ Tautulli, Maintainerr
  - docker-compose.requests.yml         # ✅ Overseerr
  - docker-compose.management.yml       # ✅ Portainer, Watchtower
  - docker-compose.monitoring.yml       # ✅ Prometheus, Grafana
  - docker-compose.utilities.yml        # ✅ Homepage, IT-Tools
  - docker-compose.backup.yml           # ✅ Duplicati

  # Uncomment to enable:
  # - docker-compose.arr.yml            # *Arr stack (needs VPN)
  # - docker-compose.downloaders.yml    # qBittorrent (needs VPN)
  # - docker-compose.logging.yml        # Loki log aggregation
  # - docker-compose.automation.yml     # n8n workflows
  # - docker-compose.files.yml          # Nextcloud
```

### Common Scenarios

#### Scenario 1: Just Plex and Photos

```yaml
include:
  - docker-compose.common.yml
  - docker-compose.core.yml
  - docker-compose.photos.yml
  - docker-compose.media-servers.yml
  - docker-compose.management.yml
```

#### Scenario 2: Full Media Automation

```yaml
include:
  - docker-compose.common.yml
  - docker-compose.core.yml
  - docker-compose.photos.yml
  - docker-compose.media-servers.yml
  - docker-compose.media-extras.yml
  - docker-compose.arr.yml              # Uncomment
  - docker-compose.downloaders.yml      # Uncomment
  - docker-compose.requests.yml
  - docker-compose.management.yml
  - docker-compose.utilities.yml
```

---

## Step 6: Launch

### Validate Configuration

```bash
# Check for syntax errors
docker compose config --quiet && echo "✅ Configuration valid"

# List all services
docker compose config --services
```

### Start Services

```bash
# Start all enabled services
docker compose up -d

# Start with optional profiles
docker compose --profile speedtest --profile scrutiny up -d

# Watch startup logs
docker compose logs -f
# Press Ctrl+C to stop watching (services keep running)
```

### Verify Services

```bash
# Check running containers
docker compose ps

# Check health status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected output:
```
NAMES               STATUS
plex                Up 2 minutes (healthy)
immich_server       Up 2 minutes (healthy)
homepage            Up 2 minutes (healthy)
grafana             Up 2 minutes (healthy)
...
```

---

## Step 7: Initial Setup

### Access Your Services

| Service | URL | First-Time Setup |
|:--------|:----|:-----------------|
| **Homepage** | `http://your-server:3002` | Auto-configured |
| **Plex** | `http://your-server:32400/web` | Plex account login |
| **Immich** | `http://your-server:2283` | Create admin account |
| **Portainer** | `https://your-server:9443` | Create admin account |
| **Grafana** | `http://your-server:3000` | admin / admin |

### Configure Plex

1. Open `http://your-server:32400/web`
2. Sign in with Plex account
3. Name your server
4. Add library folders:
   - Movies: `/media/Movies`
   - TV Shows: `/media/TV`
   - Music: `/media/Music`
5. Enable hardware transcoding (Settings → Transcoder)

### Configure Immich

1. Open `http://your-server:2283`
2. Create admin account
3. Download mobile app
4. Configure backup settings

### Configure Homepage

Homepage auto-discovers services via Docker labels. To add API widgets:

1. Edit `/opt/media-stack/data/homepage/services.yaml`
2. Add API keys from `.env`
3. Restart: `docker compose restart homepage`

See [Configuration Guide](configuration.md) for detailed customization.

---

## Next Steps

### Enable Additional Services

```bash
# Add Speedtest tracking
docker compose --profile speedtest up -d

# Add disk health monitoring
docker compose --profile scrutiny up -d

# Add ebook server
docker compose --profile kavita up -d
```

### Configure Backups

1. Open Duplicati: `http://your-server:8200`
2. Create backup job
3. Select source folders
4. Configure cloud destination

See [Backup Guide](backup.md) for detailed setup.

### Set Up Monitoring

1. Open Grafana: `http://your-server:3000`
2. Login: admin / admin
3. Change password
4. Explore pre-configured dashboards

See [Monitoring Guide](monitoring.md) for details.

### Enable *Arr Stack

If you want automated media downloads:

1. Get VPN subscription (Mullvad recommended)
2. Configure VPN in `.env`
3. Uncomment `docker-compose.arr.yml` and `docker-compose.downloaders.yml`
4. Run `docker compose up -d`

See [Configuration Guide](configuration.md#vpn-setup) for VPN setup.

---

## Troubleshooting First Start

### Container won't start

```bash
# Check logs
docker compose logs [service-name]

# Common issues:
# - Wrong PUID/PGID
# - Missing directories
# - Port already in use
```

### Permission denied

```bash
# Fix ownership
sudo chown -R $USER:$USER /opt/media-stack
sudo chown -R $USER:$USER /mnt/media
sudo chown -R $USER:$USER /mnt/photos
```

### Can't access services

1. Check container is running: `docker compose ps`
2. Check firewall: `sudo ufw status`
3. Verify port is correct
4. Check logs: `docker compose logs [service]`

See [Troubleshooting Guide](troubleshooting.md) for more solutions.

---

## Getting Help

- [Troubleshooting Guide](troubleshooting.md)
- [Configuration Guide](configuration.md)
- [Architecture Overview](architecture.md)

---

[← Back to README](../README.md)
