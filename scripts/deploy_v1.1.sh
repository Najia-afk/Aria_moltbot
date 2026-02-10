#!/bin/bash
# Aria v1.1 Production Deploy Script
# Run on Mac Mini: bash deploy_v1.1.sh
set -euo pipefail

DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
COMPOSE="/Applications/Docker.app/Contents/Resources/bin/docker compose"
ARIA_DIR="$HOME/aria"
BACKUP_DIR="$HOME/aria_backups/pre_v1.1_$(date +%Y%m%d_%H%M%S)"
DB_USER="aria_admin"
DB_NAME="aria_warehouse"

echo "============================================"
echo "  ARIA v1.1 PRODUCTION DEPLOY"
echo "  $(date)"
echo "============================================"

# ── STEP 1: Pre-deploy row counts ──
echo ""
echo ">>> STEP 1: Pre-deploy baseline"
$DOCKER exec aria-db psql -U $DB_USER -d $DB_NAME -c \
  "SELECT tablename, n_live_tup as rows FROM pg_stat_user_tables ORDER BY tablename;"
echo "PRE-DEPLOY BASELINE CAPTURED"

# ── STEP 2: Backup ──
echo ""
echo ">>> STEP 2: Database backup"
mkdir -p "$BACKUP_DIR"
$DOCKER exec aria-db pg_dump -U $DB_USER -d $DB_NAME --format=custom -f /tmp/aria_warehouse.dump
$DOCKER cp aria-db:/tmp/aria_warehouse.dump "$BACKUP_DIR/aria_warehouse.dump"
$DOCKER exec aria-db pg_dump -U $DB_USER -d litellm --format=custom -f /tmp/litellm.dump
$DOCKER cp aria-db:/tmp/litellm.dump "$BACKUP_DIR/litellm.dump"
# Save current git state
cd "$ARIA_DIR"
git log -1 --format="%H %s" > "$BACKUP_DIR/git_state.txt"
cp stacks/brain/.env "$BACKUP_DIR/dot_env.backup" 2>/dev/null || true
ls -lh "$BACKUP_DIR/"
echo "BACKUP COMPLETE: $BACKUP_DIR"

# ── STEP 3: Pull vscode_dev ──
echo ""
echo ">>> STEP 3: Pull vscode_dev branch"
cd "$ARIA_DIR"
git fetch origin
git stash || true
git checkout vscode_dev 2>/dev/null || git checkout -b vscode_dev origin/vscode_dev
git pull origin vscode_dev
echo "GIT PULL DONE"
echo "Latest commit:"
git log -1 --oneline

# ── STEP 4: Schema migration (new working_memory table) ──
echo ""
echo ">>> STEP 4: Schema migration"
$DOCKER exec aria-db psql -U $DB_USER -d $DB_NAME -c "
  CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";
  
  CREATE TABLE IF NOT EXISTS working_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50) NOT NULL,
    key VARCHAR(200) NOT NULL,
    value JSONB NOT NULL,
    importance FLOAT DEFAULT 0.5,
    ttl_hours INTEGER,
    source VARCHAR(100),
    checkpoint_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    accessed_at TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0
  );
  
  CREATE INDEX IF NOT EXISTS ix_working_memory_category ON working_memory(category);
  CREATE INDEX IF NOT EXISTS ix_working_memory_key ON working_memory(key);
"
echo "SCHEMA MIGRATION DONE"

# Verify table exists
$DOCKER exec aria-db psql -U $DB_USER -d $DB_NAME -c "\dt working_memory"

# ── STEP 5: Rebuild Docker images ──
echo ""
echo ">>> STEP 5: Rebuild affected images"
cd "$ARIA_DIR/stacks/brain"
$COMPOSE build --no-cache aria-api aria-web
echo "DOCKER BUILD DONE"

# ── STEP 6: Rolling restart ──
echo ""
echo ">>> STEP 6: Rolling restart (keep DB running)"
$COMPOSE stop aria-api aria-web clawdbot
sleep 3
$COMPOSE up -d
echo "SERVICES RESTARTED"

# Wait for health
echo "Waiting 15s for services to stabilize..."
sleep 15

# ── STEP 7: Health checks ──
echo ""
echo ">>> STEP 7: Health checks"
curl -sf http://localhost:8000/api/health && echo " ✓ aria-api healthy" || echo " ✗ aria-api FAILED"
curl -sf http://localhost:5000/ > /dev/null && echo " ✓ aria-web healthy" || echo " ✗ aria-web FAILED"
$DOCKER ps --format "table {{.Names}}\t{{.Status}}" | grep -E "aria|clawdbot|litellm|traefik"

# ── STEP 8: Post-deploy row counts ──
echo ""
echo ">>> STEP 8: Post-deploy verification"
$DOCKER exec aria-db psql -U $DB_USER -d $DB_NAME -c \
  "SELECT tablename, n_live_tup as rows FROM pg_stat_user_tables ORDER BY tablename;"

# ── STEP 9: Endpoint smoke tests ──
echo ""
echo ">>> STEP 9: Endpoint smoke tests"
for endpoint in \
  "/api/health" \
  "/api/sessions/stats" \
  "/api/activities?limit=1" \
  "/api/model-usage?limit=1" \
  "/api/goals?limit=1" \
  "/api/memories?limit=1" \
  "/api/thoughts?limit=1" \
  "/api/heartbeat?limit=1" \
  "/api/performance?limit=1" \
  "/api/security-events?limit=1" \
  "/api/knowledge-graph/entities?limit=1" \
  "/api/social?limit=1" \
  "/api/records?limit=1"; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000${endpoint}")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✓ ${endpoint} → ${HTTP_CODE}"
  else
    echo "  ✗ ${endpoint} → ${HTTP_CODE}"
  fi
done

echo ""
echo ">>> Web page smoke tests"
for page in "/" "/dashboard" "/activities" "/sessions" "/goals" "/memories" \
  "/thoughts" "/records" "/services" "/models" "/heartbeat" "/knowledge" \
  "/social" "/performance" "/security" "/operations" "/model-usage"; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5000${page}")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✓ ${page} → ${HTTP_CODE}"
  else
    echo "  ✗ ${page} → ${HTTP_CODE}"
  fi
done

echo ""
echo "============================================"
echo "  DEPLOY COMPLETE — $(date)"
echo "  Backup: $BACKUP_DIR"
echo "============================================"
