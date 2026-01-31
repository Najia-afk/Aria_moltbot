#!/bin/bash
# 05_verify.sh - Verify deployment and run health checks
# Usage: ./05_verify.sh

set -e
echo "🔍 Verifying Aria deployment..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[OK]${NC} $1"; }
error() { echo -e "${RED}[FAIL]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

ERRORS=0

# Check Docker containers
echo ""
echo "📦 Container Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(aria|postgres|traefik|grafana|prometheus|nginx)"

# Health checks
echo ""
echo "🏥 Health Checks:"

# PostgreSQL
if docker exec aria-db pg_isready -U aria_admin -d aria_bubble > /dev/null 2>&1; then
    log "PostgreSQL: Ready"
else
    error "PostgreSQL: Not ready"
    ((ERRORS++))
fi

# Traefik
if curl -s http://localhost:8080/ping > /dev/null 2>&1; then
    log "Traefik: Responding"
else
    warn "Traefik: Not responding on :8080"
fi

# Nginx
if curl -s http://localhost > /dev/null 2>&1; then
    log "Nginx: Serving on port 80"
else
    error "Nginx: Not responding"
    ((ERRORS++))
fi

# Grafana
if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
    log "Grafana: Healthy"
else
    warn "Grafana: Not responding on :3001"
fi

# API
if curl -s http://localhost/api/health > /dev/null 2>&1; then
    log "API: Healthy"
else
    warn "API: Not responding"
fi

# Database tables
echo ""
echo "📊 Database Tables:"
docker exec aria-db psql -U aria_admin -d aria_bubble -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;" 2>/dev/null

# Schedule tick status
echo ""
echo "⏰ Schedule Tick (Coroutine Status):"
docker exec aria-db psql -U aria_admin -d aria_bubble -c "SELECT id, ts, horizon, goal, status FROM schedule_tick ORDER BY ts DESC LIMIT 5;" 2>/dev/null

# Summary
echo ""
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All critical services are running${NC}"
else
    echo -e "${RED}❌ $ERRORS critical service(s) failed${NC}"
fi

# Print access URLs
IP=$(hostname -I | awk '{print $1}')
echo ""
echo "🌐 Access URLs:"
echo "   Main:      http://$IP"
echo "   API:       http://$IP/api"
echo "   Grafana:   http://$IP/grafana (admin/aria2026)"
echo "   PGAdmin:   http://$IP/pgadmin"
echo "   Traefik:   http://$IP:8080"
