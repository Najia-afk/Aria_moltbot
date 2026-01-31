#!/bin/bash
# 04_import.sh - Import data, soul files, and configure brain
# Usage: ./04_import.sh

set -e
echo "📥 Importing Aria data and soul..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$DEPLOY_DIR/../aria_memory"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log() { echo -e "${GREEN}[IMPORT]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

ENV_FILE="$DEPLOY_DIR/../stacks/brain/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    warn "Missing .env at $ENV_FILE"
    exit 1
fi

# Wait for postgres to be ready
log "Waiting for PostgreSQL to be ready..."
until docker exec aria-db pg_isready -U "$DB_USER" -d "$DB_NAME"; do
    sleep 2
done
log "PostgreSQL is ready"

# Import schema
log "Applying database schema..."
docker exec -i aria-db psql -U "$DB_USER" -d "$DB_NAME" < "$DATA_DIR/db_dumps/schema.sql" 2>/dev/null || warn "Schema already applied"

# Import original data if exists
if [ -f "$DATA_DIR/extracted/aria_warehouse.sql" ]; then
    log "Importing original data..."
    docker exec -i aria-db psql -U "$DB_USER" -d "$DB_NAME" < "$DATA_DIR/extracted/aria_warehouse.sql" 2>/dev/null || warn "Data already imported"
fi

# Copy soul files to container
log "Copying soul files..."
docker cp "$DATA_DIR/extracted/SOUL.md" aria-brain:/app/soul/ 2>/dev/null || warn "Could not copy SOUL.md"
docker cp "$DATA_DIR/extracted/IDENTITY.md" aria-brain:/app/soul/ 2>/dev/null || warn "Could not copy IDENTITY.md"
docker cp "$DATA_DIR/extracted/USER.md" aria-brain:/app/soul/ 2>/dev/null || warn "Could not copy USER.md"
docker cp "$DATA_DIR/extracted/AGENTS.md" aria-brain:/app/soul/ 2>/dev/null || warn "Could not copy AGENTS.md"
docker cp "$DATA_DIR/extracted/HEARTBEAT.md" aria-brain:/app/soul/ 2>/dev/null || warn "Could not copy HEARTBEAT.md"

# Copy session data
if [ -d "$DATA_DIR/sessions" ]; then
    log "Copying session data..."
    docker cp "$DATA_DIR/sessions/." aria-brain:/app/sessions/ 2>/dev/null || warn "Could not copy sessions"
fi

# Verify import
log "Verifying import..."
docker exec aria-db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) as tables FROM information_schema.tables WHERE table_schema = 'public';"
docker exec aria-db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"

log "✅ Data import complete"
