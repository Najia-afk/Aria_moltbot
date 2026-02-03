#!/bin/bash
# =============================================================================
# Server Rebuild Script - Clean Destroy and Redeploy
# =============================================================================
# This script destroys ALL containers and data, then rebuilds from scratch.
# Run this on the Mac server after pulling latest changes.
#
# Usage: ./server-rebuild.sh [--disable-moltbook]
#
# Options:
#   --disable-moltbook  Remove MOLTBOOK_TOKEN from .env before deploy
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[REBUILD]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
DISABLE_MOLTBOOK=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --disable-moltbook) DISABLE_MOLTBOOK=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🔄 ARIA SERVER REBUILD SCRIPT                  ║"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║  This will DESTROY all containers, volumes, and data!   ║"
echo "║  Make sure you have a backup if needed.                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

read -p "Type 'REBUILD' to confirm: " confirm
if [ "$confirm" != "REBUILD" ]; then
    log "Aborted."
    exit 0
fi

# Step 1: Stop and remove all containers
log "Step 1/5: Stopping all services..."
COMPOSE_FILE="docker-compose.yml"
[ -f "docker-compose.portable.yml" ] && COMPOSE_FILE="docker-compose.portable.yml"

docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true

# Remove any orphan containers
log "Removing orphan containers..."
docker ps -a --filter "name=aria-" -q | xargs -r docker rm -f 2>/dev/null || true
docker ps -a --filter "name=clawdbot" -q | xargs -r docker rm -f 2>/dev/null || true
docker ps -a --filter "name=litellm" -q | xargs -r docker rm -f 2>/dev/null || true
docker ps -a --filter "name=traefik" -q | xargs -r docker rm -f 2>/dev/null || true
docker ps -a --filter "name=grafana" -q | xargs -r docker rm -f 2>/dev/null || true
docker ps -a --filter "name=prometheus" -q | xargs -r docker rm -f 2>/dev/null || true

# Step 2: Remove volumes
log "Step 2/5: Removing volumes..."
docker volume ls -q --filter "name=brain_" | xargs -r docker volume rm 2>/dev/null || true

# Step 3: Clean generated files
log "Step 3/5: Cleaning generated files..."
rm -rf certs/*.pem 2>/dev/null || true
rm -rf init-scripts/* 2>/dev/null || true

# Step 4: Handle MOLTBOOK_TOKEN
if [ "$DISABLE_MOLTBOOK" = true ]; then
    log "Step 4/5: Disabling MOLTBOOK_TOKEN..."
    if [ -f ".env" ]; then
        # Comment out MOLTBOOK_TOKEN line
        sed -i.bak 's/^MOLTBOOK_TOKEN=.*/MOLTBOOK_TOKEN=/' .env
        log "MOLTBOOK_TOKEN cleared in .env"
    fi
else
    log "Step 4/5: Keeping MOLTBOOK_TOKEN as-is"
fi

# Step 5: Pull latest and redeploy
log "Step 5/5: Pulling latest and deploying..."

# Pull latest from git
cd ../..
log "Pulling latest changes from git..."
git pull origin main

# Go back to stacks/brain and deploy
cd stacks/brain

# Run deploy script
if [ -f "deploy.sh" ]; then
    chmod +x deploy.sh
    ./deploy.sh deploy
else
    # Manual deploy if deploy.sh doesn't exist
    log "Running manual deploy..."
    
    # Create directories
    mkdir -p certs grafana/provisioning/datasources init-scripts
    
    # Build and start
    docker compose -f "$COMPOSE_FILE" build
    docker compose -f "$COMPOSE_FILE" up -d
    
    sleep 15
    docker compose -f "$COMPOSE_FILE" ps
fi

echo ""
log "🎉 Server rebuild complete!"
echo ""
echo "Next steps:"
echo "  1. Check service status: docker compose ps"
echo "  2. View logs: docker compose logs -f"
echo "  3. Access dashboard: https://$(hostname -I | awk '{print $1}')/"
echo ""
