#!/bin/bash
# Aria-Only Database Backup Script
# Backs up ONLY Aria's tables from aria_warehouse, excluding LiteLLM's tables.
# Stored securely in /Users/najia/aria_vault/backups/ (NOT accessible by Aria).
#
# Usage:  ./scripts/aria_backup.sh
# Cron:   0 3 * * * /Users/najia/aria/scripts/aria_backup.sh >> /Users/najia/aria_vault/backups/backup.log 2>&1

set -euo pipefail

# Source environment from .env if available
ENV_FILE="/Users/najia/aria/stacks/brain/.env"
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
fi

# Configuration
BACKUP_DIR="/Users/najia/aria_vault/backups"
DB_CONTAINER="aria-db"
DB_NAME="aria_warehouse"
DB_USER="${DB_USER:-admin}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/aria_backup_${TIMESTAMP}.sql.gz"
JSON_EXPORT="${BACKUP_DIR}/aria_export_${TIMESTAMP}.json"
KEEP_DAYS=7

# Aria's core tables (exclude litellm-owned tables)
ARIA_TABLES=(
    activity_log
    thoughts
    memories
    goals
    social_posts
    heartbeat_log
    schema_migrations
    rate_limits
    agent_sessions
    model_usage
    security_events
    api_key_rotations
    knowledge_entities
    knowledge_relations
    key_value_memory
    performance_log
    hourly_goals
    model_cost_reference
    bubble_balances
    bubble_monetization
    enrich_kg_runs
    model_discovery_log
    moltbook_users
    opportunities
    pending_complex_tasks
    schedule_tick
    scheduled_jobs
    secops_work
    spending_alerts
    spending_log
    yield_positions
)

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting Aria-only backup..."

# Build pg_dump table flags
TABLE_FLAGS=""
for table in "${ARIA_TABLES[@]}"; do
    TABLE_FLAGS="${TABLE_FLAGS} -t ${table}"
done

# Run pg_dump inside Docker container, compress output
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    ${TABLE_FLAGS} \
    2>/dev/null | gzip > "${BACKUP_FILE}"

BACKUP_SIZE=$(ls -lh "${BACKUP_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] SQL backup: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Also create a JSON export of key data for easy inspection
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "
SELECT json_build_object(
    'timestamp', now()::text,
    'activities', (SELECT count(*) FROM activity_log),
    'thoughts', (SELECT count(*) FROM thoughts),
    'memories', (SELECT count(*) FROM memories),
    'goals', (SELECT count(*) FROM goals),
    'social_posts', (SELECT count(*) FROM social_posts),
    'knowledge_entities', (SELECT count(*) FROM knowledge_entities),
    'knowledge_relations', (SELECT count(*) FROM knowledge_relations),
    'heartbeats', (SELECT count(*) FROM heartbeat_log),
    'recent_activities', (
        SELECT json_agg(row_to_json(a))
        FROM (SELECT id, type, description, created_at FROM activity_log ORDER BY created_at DESC LIMIT 10) a
    ),
    'active_goals', (
        SELECT json_agg(row_to_json(g))
        FROM (SELECT id, name, status, priority FROM goals WHERE status = 'active' ORDER BY priority LIMIT 10) g
    ),
    'recent_thoughts', (
        SELECT json_agg(row_to_json(t))
        FROM (SELECT id, category, content, timestamp FROM thoughts ORDER BY timestamp DESC LIMIT 10) t
    )
);" > "${JSON_EXPORT}" 2>/dev/null

echo "[$(date -Iseconds)] JSON export: ${JSON_EXPORT}"

# Cleanup old backups (keep last N days)
find "${BACKUP_DIR}" -name "aria_backup_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "aria_export_*.json" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

REMAINING=$(ls -1 "${BACKUP_DIR}"/aria_backup_*.sql.gz 2>/dev/null | wc -l)
echo "[$(date -Iseconds)] Backup complete. ${REMAINING} backups retained (${KEEP_DAYS}-day retention)."
echo "---"
