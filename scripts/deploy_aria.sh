#!/bin/bash
# Aria Deployment Script
# Run this on the Mac to deploy the brain stack
# Usage: ./deploy_aria.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARIA_HOME="${HOME}/aria_brain"

echo "=== Aria Brain Deployment ==="
echo "Target: $ARIA_HOME"
echo ""

# Create directories
mkdir -p "$ARIA_HOME"
mkdir -p "$ARIA_HOME/init-scripts"
mkdir -p "$ARIA_HOME/grafana/provisioning/datasources"

# Check if docker-compose.yml exists
if [ ! -f "$ARIA_HOME/docker-compose.yml" ]; then
    echo "⚠ docker-compose.yml not found!"
    echo "Please copy stacks/brain/* to $ARIA_HOME first"
    exit 1
fi

# Check for .env
if [ ! -f "$ARIA_HOME/.env" ]; then
    if [ -f "$ARIA_HOME/.env.example" ]; then
        echo "Creating .env from .env.example..."
        cp "$ARIA_HOME/.env.example" "$ARIA_HOME/.env"
        echo "⚠ Please edit $ARIA_HOME/.env with your credentials"
        exit 1
    else
        echo "⚠ No .env or .env.example found!"
        exit 1
    fi
fi

# Load .env
set -a
source "$ARIA_HOME/.env"
set +a

# Copy schema to init-scripts
if [ -f "$SCRIPT_DIR/../aria_memory/db_dumps/schema.sql" ]; then
    cp "$SCRIPT_DIR/../aria_memory/db_dumps/schema.sql" "$ARIA_HOME/init-scripts/01_schema.sql"
    echo "✓ Schema copied to init-scripts"
fi

echo ""
echo "=== Starting Docker Stack ==="
cd "$ARIA_HOME"

# Pull latest images
echo "Pulling images..."
docker compose pull

# Start services
echo "Starting services..."
docker compose up -d

# Wait for postgres
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Check services
echo ""
echo "=== Service Status ==="
docker compose ps

echo ""
echo "=== Health Checks ==="

# Check postgres
if docker exec aria-db pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
    echo "✓ PostgreSQL: HEALTHY"
    
    # Check if schema applied
    TABLE_COUNT=$(docker exec aria-db psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
    echo "  Tables in database: $TABLE_COUNT"
else
    echo "✗ PostgreSQL: NOT READY"
fi

# Check LiteLLM
if curl -s http://localhost:18793/health > /dev/null 2>&1; then
    echo "✓ LiteLLM: HEALTHY"
else
    echo "⚠ LiteLLM: Starting up..."
fi

# Check Grafana
if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
    echo "✓ Grafana: HEALTHY"
else
    echo "⚠ Grafana: Starting up..."
fi

echo ""
echo "=== Access URLs ==="
echo "Portal:      https://$SERVICE_HOST"
echo "Grafana:     https://$SERVICE_HOST/grafana/"
echo "Traefik:     https://$SERVICE_HOST/dashboard/"
echo "LiteLLM:     https://$SERVICE_HOST/litellm/"
echo "Prometheus:  https://$SERVICE_HOST/prometheus/"
echo ""
echo "Deployment complete! ⚡️"
