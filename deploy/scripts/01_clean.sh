#!/bin/bash
# 01_clean.sh - Clean server before deployment
# Usage: ./01_clean.sh

set -e
echo "🧹 Cleaning server for fresh Aria deployment..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[CLEAN]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Stop OpenClaw/Clawdbot processes
log "Stopping OpenClaw/Clawdbot processes..."
pkill -f "clawdbot" 2>/dev/null || warn "No clawdbot process found"
pkill -f "openclaw" 2>/dev/null || warn "No openclaw process found"
pkill -f "node.*clawd" 2>/dev/null || warn "No node clawd process found"

# Stop Docker containers
log "Stopping Docker containers..."
docker stop $(docker ps -aq) 2>/dev/null || warn "No containers to stop"

# Remove old containers (keep volumes for now)
log "Removing old containers..."
docker rm $(docker ps -aq) 2>/dev/null || warn "No containers to remove"

# Remove old images (optional - comment out to keep cache)
# log "Removing old images..."
# docker rmi $(docker images -q) 2>/dev/null || warn "No images to remove"

# Clean Docker system
log "Cleaning Docker system..."
docker system prune -f --volumes=false

# Remove old deployment files (but keep data)
log "Cleaning old deployment files..."
rm -rf ~/aria_deploy 2>/dev/null || true
rm -rf ~/aria_brain 2>/dev/null || true

# Create fresh directories
log "Creating fresh directories..."
mkdir -p ~/aria_deploy
mkdir -p ~/aria_data
mkdir -p ~/aria_logs

# Check what's still running
log "Checking remaining processes..."
ps aux | grep -E "(aria|clawd|openclaw)" | grep -v grep || log "No Aria processes running"

log "✅ Server cleaned and ready for deployment"
