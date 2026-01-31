#!/bin/bash
# 03_deploy.sh - Deploy full Aria stack
# Usage: ./03_deploy.sh

set -e
echo "🚀 Deploying Aria stack..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Load environment
if [ -f "$DEPLOY_DIR/config/.env.production" ]; then
    export $(cat "$DEPLOY_DIR/config/.env.production" | grep -v '^#' | xargs)
    log "Loaded production environment"
else
    warn "No .env.production found, using defaults"
fi

cd "$DEPLOY_DIR/docker"

# Create required directories
log "Creating data directories..."
mkdir -p ~/aria_data/postgres
mkdir -p ~/aria_data/grafana
mkdir -p ~/aria_data/prometheus
mkdir -p ~/aria_logs

# Create Docker network if not exists
log "Creating Docker network..."
docker network create aria-net 2>/dev/null || log "Network aria-net already exists"

# Start the stack
log "Starting Docker Compose stack..."
docker compose -f docker-compose.yml up -d

# Wait for services to be ready
log "Waiting for services to start..."
sleep 10

# Check service health
log "Checking service health..."
docker compose ps

# Show logs summary
log "Recent logs:"
docker compose logs --tail=20

log "✅ Aria stack deployed successfully"
echo ""
echo "📊 Access points:"
echo "   Dashboard: http://$(hostname -I | awk '{print $1}')"
echo "   Grafana:   http://$(hostname -I | awk '{print $1}')/grafana"
echo "   API:       http://$(hostname -I | awk '{print $1}')/api"
echo "   Traefik:   http://$(hostname -I | awk '{print $1}'):8080"
