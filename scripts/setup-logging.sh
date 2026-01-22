#!/bin/bash
# =============================================================================
# Logging Stack Setup Script
# Copies configuration templates to the appropriate directories and starts
# the logging services (Loki, Promtail, Grafana with dashboards)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env file if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
fi

# Set default base directory
DOCKER_BASE_DIR="${DOCKER_BASE_DIR:-/opt/docker}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Logging Stack Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Project directory: ${GREEN}$PROJECT_DIR${NC}"
echo -e "Docker base directory: ${GREEN}$DOCKER_BASE_DIR${NC}"
echo ""

# Function to create directory if it doesn't exist
create_dir() {
    if [ ! -d "$1" ]; then
        echo -e "Creating directory: ${YELLOW}$1${NC}"
        mkdir -p "$1"
    fi
}

# Function to copy files with backup
copy_config() {
    local src="$1"
    local dest="$2"
    
    if [ -f "$dest" ]; then
        echo -e "  ${YELLOW}Backing up existing:${NC} $dest"
        cp "$dest" "${dest}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    echo -e "  ${GREEN}Copying:${NC} $src -> $dest"
    cp "$src" "$dest"
}

# =============================================================================
# Create required directories
# =============================================================================
echo -e "${BLUE}Creating directories...${NC}"

create_dir "$DOCKER_BASE_DIR/loki/config"
create_dir "$DOCKER_BASE_DIR/loki/data"
create_dir "$DOCKER_BASE_DIR/loki/rules/homelab"
create_dir "$DOCKER_BASE_DIR/promtail/config"
create_dir "$DOCKER_BASE_DIR/vector/config"
create_dir "$DOCKER_BASE_DIR/grafana/data"
create_dir "$DOCKER_BASE_DIR/grafana/provisioning/datasources"
create_dir "$DOCKER_BASE_DIR/grafana/provisioning/dashboards"
create_dir "$DOCKER_BASE_DIR/prometheus/config"
create_dir "$DOCKER_BASE_DIR/prometheus/config/rules"
create_dir "$DOCKER_BASE_DIR/prometheus/data"
create_dir "$DOCKER_BASE_DIR/alertmanager/config"
create_dir "$DOCKER_BASE_DIR/alertmanager/data"

echo ""

# =============================================================================
# Copy Loki configuration
# =============================================================================
echo -e "${BLUE}Setting up Loki...${NC}"

copy_config "$PROJECT_DIR/config-templates/loki/local-config.yaml" \
            "$DOCKER_BASE_DIR/loki/config/local-config.yaml"

# Copy alerting rules
if [ -d "$PROJECT_DIR/config-templates/loki/rules/homelab" ]; then
    for rule_file in "$PROJECT_DIR/config-templates/loki/rules/homelab"/*.yml; do
        if [ -f "$rule_file" ]; then
            copy_config "$rule_file" \
                        "$DOCKER_BASE_DIR/loki/rules/homelab/$(basename "$rule_file")"
        fi
    done
fi

echo ""

# =============================================================================
# Copy Promtail configuration
# =============================================================================
echo -e "${BLUE}Setting up Promtail...${NC}"

copy_config "$PROJECT_DIR/config-templates/promtail/config.yml" \
            "$DOCKER_BASE_DIR/promtail/config/config.yml"

echo ""

# =============================================================================
# Copy Vector configuration (optional)
# =============================================================================
echo -e "${BLUE}Setting up Vector (optional)...${NC}"

if [ -f "$PROJECT_DIR/config-templates/vector/vector.yaml" ]; then
    copy_config "$PROJECT_DIR/config-templates/vector/vector.yaml" \
                "$DOCKER_BASE_DIR/vector/config/vector.yaml"
fi

echo ""

# =============================================================================
# Copy Grafana provisioning
# =============================================================================
echo -e "${BLUE}Setting up Grafana provisioning...${NC}"

# Copy datasources
if [ -d "$PROJECT_DIR/config-templates/grafana/provisioning/datasources" ]; then
    for ds_file in "$PROJECT_DIR/config-templates/grafana/provisioning/datasources"/*.yml; do
        if [ -f "$ds_file" ]; then
            copy_config "$ds_file" \
                        "$DOCKER_BASE_DIR/grafana/provisioning/datasources/$(basename "$ds_file")"
        fi
    done
fi

# Copy dashboard provisioning config
if [ -d "$PROJECT_DIR/config-templates/grafana/provisioning/dashboards" ]; then
    for dash_file in "$PROJECT_DIR/config-templates/grafana/provisioning/dashboards"/*.yml; do
        if [ -f "$dash_file" ]; then
            copy_config "$dash_file" \
                        "$DOCKER_BASE_DIR/grafana/provisioning/dashboards/$(basename "$dash_file")"
        fi
    done
    
    # Copy dashboard JSON files
    for dash_json in "$PROJECT_DIR/config-templates/grafana/provisioning/dashboards"/*.json; do
        if [ -f "$dash_json" ]; then
            copy_config "$dash_json" \
                        "$DOCKER_BASE_DIR/grafana/provisioning/dashboards/$(basename "$dash_json")"
        fi
    done
fi

echo ""

# =============================================================================
# Copy Prometheus configuration
# =============================================================================
echo -e "${BLUE}Setting up Prometheus...${NC}"

if [ -f "$PROJECT_DIR/config-templates/prometheus/prometheus.yml" ]; then
    copy_config "$PROJECT_DIR/config-templates/prometheus/prometheus.yml" \
                "$DOCKER_BASE_DIR/prometheus/config/prometheus.yml"
fi

# Copy Prometheus rules
if [ -d "$PROJECT_DIR/config-templates/prometheus/rules" ]; then
    for rule_file in "$PROJECT_DIR/config-templates/prometheus/rules"/*.yml; do
        if [ -f "$rule_file" ]; then
            copy_config "$rule_file" \
                        "$DOCKER_BASE_DIR/prometheus/config/rules/$(basename "$rule_file")"
        fi
    done
fi

echo ""

# =============================================================================
# Copy Alertmanager configuration
# =============================================================================
echo -e "${BLUE}Setting up Alertmanager...${NC}"

if [ -f "$PROJECT_DIR/config-templates/alertmanager/alertmanager.yml" ]; then
    copy_config "$PROJECT_DIR/config-templates/alertmanager/alertmanager.yml" \
                "$DOCKER_BASE_DIR/alertmanager/config/alertmanager.yml"
fi

echo ""

# =============================================================================
# Set permissions
# =============================================================================
echo -e "${BLUE}Setting permissions...${NC}"

# Grafana needs specific permissions
if [ -d "$DOCKER_BASE_DIR/grafana" ]; then
    echo -e "  Setting Grafana data ownership (UID 472)"
    chown -R 472:472 "$DOCKER_BASE_DIR/grafana/data" 2>/dev/null || \
        echo -e "  ${YELLOW}Warning: Could not set Grafana permissions (run as root)${NC}"
fi

# Loki and Promtail
if [ -d "$DOCKER_BASE_DIR/loki" ]; then
    chmod -R 755 "$DOCKER_BASE_DIR/loki"
fi

if [ -d "$DOCKER_BASE_DIR/promtail" ]; then
    chmod -R 755 "$DOCKER_BASE_DIR/promtail"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Configuration files have been copied to: ${BLUE}$DOCKER_BASE_DIR${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Ensure the logging module is enabled in docker-compose.yml:"
echo "   Uncomment: - docker-compose.logging.yml"
echo ""
echo "2. Start the logging stack:"
echo "   docker compose up -d loki promtail grafana"
echo ""
echo "3. Access Grafana at: http://localhost:3000"
echo "   Default credentials: admin / admin (change on first login)"
echo ""
echo "4. Dashboards are auto-provisioned in the 'Homelab' folder:"
echo "   - Logs Overview: Overall log statistics and errors"
echo "   - Container Logs: Deep dive into individual containers"
echo "   - Security & Auth: SSH and auth log monitoring"
echo "   - Media Stack Logs: *Arr suite, VPN, and media servers"
echo ""
echo "5. Alerts will be sent to Alertmanager at: http://localhost:9093"
echo "   Configure receivers in: $DOCKER_BASE_DIR/alertmanager/config/alertmanager.yml"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  docker compose logs -f loki        # View Loki logs"
echo "  docker compose logs -f promtail    # View Promtail logs"
echo "  docker compose restart grafana     # Reload dashboards"
echo ""
echo "  # Check Loki is receiving logs:"
echo "  curl -s http://localhost:3100/loki/api/v1/labels | jq"
echo ""
