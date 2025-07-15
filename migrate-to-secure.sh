#!/bin/bash
# migrate-to-secure.sh - Migrate from current setup to secure configuration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Docker Media Stack Security Migration${NC}"
echo "====================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${YELLOW}Warning: Running as root. Consider using a non-root user.${NC}"
   echo ""
fi

# Function to check if service is running
check_service() {
    local service=$1
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        return 0
    else
        return 1
    fi
}

# Step 1: Check current setup
echo "Step 1: Checking current setup..."
echo "--------------------------------"

if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓ Found docker-compose.yml${NC}"
else
    echo -e "${RED}✗ docker-compose.yml not found!${NC}"
    exit 1
fi

if [ -f "docker-compose-secure.yml" ]; then
    echo -e "${GREEN}✓ Found docker-compose-secure.yml${NC}"
else
    echo -e "${RED}✗ docker-compose-secure.yml not found!${NC}"
    echo "Please ensure docker-compose-secure.yml is in the current directory."
    exit 1
fi

# Check running services
echo ""
echo "Currently running services:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|caddy|authelia|jellyfin|plex|radarr|sonarr|prowlarr|qbittorrent|portainer)" || echo "No media stack services running"

echo ""
read -p "Continue with migration? This will stop current services. (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

# Step 2: Backup current configuration
echo ""
echo "Step 2: Creating backups..."
echo "--------------------------"

backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup_dir"

# Backup important files
files_to_backup=(
    "docker-compose.yml"
    ".env"
    "media-stack/caddy/Caddyfile"
    "media-stack/authelia/configuration.yml"
    "media-stack/authelia/users_database.yml"
)

for file in "${files_to_backup[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$backup_dir/" 2>/dev/null && echo -e "${GREEN}✓ Backed up $file${NC}" || echo -e "${YELLOW}⚠ Could not backup $file${NC}"
    fi
done

echo -e "${GREEN}Backups saved to: $backup_dir/${NC}"

# Step 3: Stop current services
echo ""
echo "Step 3: Stopping current services..."
echo "-----------------------------------"

docker-compose down || echo -e "${YELLOW}Warning: Some services may not have stopped cleanly${NC}"

# Step 4: Generate secrets if needed
echo ""
echo "Step 4: Setting up secrets..."
echo "-----------------------------"

if [ ! -f ".env" ] || ! grep -q "AUTHELIA_SESSION_SECRET" .env; then
    echo "Running secret generation script..."
    if [ -f "generate-secrets.sh" ]; then
        bash generate-secrets.sh
    else
        echo -e "${RED}generate-secrets.sh not found!${NC}"
        echo "Please generate secrets manually."
    fi
else
    echo -e "${GREEN}✓ Secrets already configured${NC}"
fi

# Step 5: Update permissions
echo ""
echo "Step 5: Setting permissions..."
echo "------------------------------"

# Create necessary directories
directories=(
    "media-stack/caddy/logs"
    "media-stack/authelia"
    "media-stack/gluetun"
    "media-stack/qbittorrent"
    "media-stack/prowlarr"
    "media-stack/radarr"
    "media-stack/sonarr"
    "media-stack/lidarr"
    "media-stack/bazarr"
    "media-stack/jellyfin/cache"
    "media-stack/jellyfin/transcodes"
    "media-stack/plex/transcode"
    "media-stack/homepage"
    "media-stack/portainer"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    if [ -n "${PUID:-}" ] && [ -n "${PGID:-}" ]; then
        chown -R "${PUID}:${PGID}" "$dir" 2>/dev/null || true
    fi
done

echo -e "${GREEN}✓ Directories created and permissions set${NC}"

# Step 6: Validate configuration
echo ""
echo "Step 6: Validating configuration..."
echo "-----------------------------------"

# Check if required files exist
if [ -f ".env" ] && [ -f "docker-compose-secure.yml" ] && [ -f "media-stack/caddy/Caddyfile" ]; then
    echo -e "${GREEN}✓ All required files present${NC}"
else
    echo -e "${RED}✗ Missing required files!${NC}"
    exit 1
fi

# Validate docker-compose file
if docker-compose -f docker-compose-secure.yml config > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker Compose configuration valid${NC}"
else
    echo -e "${RED}✗ Docker Compose configuration invalid!${NC}"
    docker-compose -f docker-compose-secure.yml config
    exit 1
fi

# Step 7: Deploy secure stack
echo ""
echo "Step 7: Deploying secure stack..."
echo "---------------------------------"

echo "Starting services..."
docker-compose -f docker-compose-secure.yml up -d

# Wait for services to start
echo ""
echo "Waiting for services to start..."
sleep 10

# Check service health
echo ""
echo "Checking service status..."
services=("caddy" "authelia" "gluetun" "jellyfin" "homepage" "portainer")

all_healthy=true
for service in "${services[@]}"; do
    if check_service "$service"; then
        status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "running")
        if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
            echo -e "${GREEN}✓ $service: $status${NC}"
        else
            echo -e "${YELLOW}⚠ $service: $status${NC}"
            all_healthy=false
        fi
    else
        echo -e "${RED}✗ $service: not running${NC}"
        all_healthy=false
    fi
done

# Step 8: Post-deployment instructions
echo ""
echo "Step 8: Post-deployment steps..."
echo "--------------------------------"

if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}✓ All services deployed successfully!${NC}"
else
    echo -e "${YELLOW}⚠ Some services may need attention${NC}"
fi

# Get domain from .env
DOMAIN_NAME=$(grep "^DOMAIN_NAME=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Configure your DNS records to point to this server:"
echo "   - *.${DOMAIN_NAME} → Your server IP"
echo ""
echo "2. Access services at:"
echo "   - Authentication: https://auth.${DOMAIN_NAME}"
echo "   - Homepage: https://homepage.${DOMAIN_NAME}"
echo "   - Portainer: https://portainer.${DOMAIN_NAME}"
echo "   - Jellyfin: https://jellyfin.${DOMAIN_NAME}"
echo ""
echo "3. Set up 2FA in Authelia for enhanced security"
echo ""
echo "4. Configure API keys in each service for Homepage integration"
echo ""
echo "5. Monitor logs for any issues:"
echo "   docker-compose -f docker-compose-secure.yml logs -f"
echo ""

if [ -d "$backup_dir" ]; then
    echo -e "${YELLOW}Your old configuration is backed up in: $backup_dir/${NC}"
fi

echo ""
echo -e "${GREEN}Migration complete!${NC}"
echo ""
echo "If you encounter issues:"
echo "1. Check logs: docker logs <service-name>"
echo "2. Restore from backup if needed"
echo "3. Review SECURITY_IMPROVEMENTS.md for troubleshooting"