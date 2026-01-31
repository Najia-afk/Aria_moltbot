#!/bin/bash
# 02_build.sh - Build Docker images
# Usage: ./02_build.sh

set -e
echo "🔨 Building Aria Docker images..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DEPLOY_DIR/docker"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}[BUILD]${NC} $1"; }

cd "$DOCKER_DIR"

# Build Aria Brain image
log "Building aria-brain image..."
docker build -f Dockerfile.brain -t aria-brain:latest .

# Build Aria Bot image (OpenClaw-based)
log "Building aria-bot image..."
docker build -f Dockerfile.aria -t aria-bot:latest .

# Pull required images
log "Pulling required images..."
docker pull postgres:16-alpine
docker pull traefik:v3.1
docker pull grafana/grafana:latest
docker pull prom/prometheus:latest
docker pull nginx:alpine
docker pull dpage/pgadmin4:latest
docker pull browserless/chrome:latest

# List images
log "Built images:"
docker images | grep -E "(aria|postgres|traefik|grafana|prometheus|nginx|pgadmin|browserless)"

log "✅ All images built successfully"
