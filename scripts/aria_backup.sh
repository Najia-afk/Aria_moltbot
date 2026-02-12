#!/bin/bash
# Aria-Only Database Backup Script
# Backs up ONLY Aria's tables from aria_warehouse, excluding LiteLLM's tables.
# Stored securely in ~/aria_vault/backups/ (NOT accessible by Aria).
#
# Usage:  ./scripts/aria_backup.sh
# Cron:   0 3 * * * ~/aria/scripts/aria_backup.sh >> ~/aria_vault/backups/backup.log 2>&1

set -euo pipefail
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/local/bin:/usr/bin:$PATH

# Self-locate: resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"

# Source environment from .env if available
# Uses grep to safely extract KEY=VALUE pairs, skipping values with spaces
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"
if [ -f "${ENV_FILE}" ]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" || "$value" == *" "* ]] && continue
        export "$key=$value"
    done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" | sed 's/\r$//')
fi

# Configuration — VAULT_DIR can be overridden via .env
VAULT_DIR="${VAULT_DIR:-${HOME}/aria_vault}"
BACKUP_DIR="${VAULT_DIR}/backups"
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

# Also create a lightweight JSON export for quick inspection.
# Keep this schema-safe across table/column changes to avoid backup failures.
if ! docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "
SELECT json_build_object(
    'timestamp', now()::text,
    'activities_count', (SELECT count(*) FROM activity_log),
    'thoughts_count', (SELECT count(*) FROM thoughts),
    'memories_count', (SELECT count(*) FROM memories),
    'goals_count', (SELECT count(*) FROM goals),
    'social_posts_count', (SELECT count(*) FROM social_posts),
    'knowledge_entities_count', (SELECT count(*) FROM knowledge_entities),
    'knowledge_relations_count', (SELECT count(*) FROM knowledge_relations),
    'heartbeats_count', (SELECT count(*) FROM heartbeat_log)
);" > "${JSON_EXPORT}" 2>/dev/null; then
    echo "[$(date -Iseconds)] WARNING: JSON export query failed; writing fallback metadata"
    printf '{"timestamp":"%s","json_export_error":true}\n' "$(date -Iseconds)" > "${JSON_EXPORT}"
fi

echo "[$(date -Iseconds)] JSON export: ${JSON_EXPORT}"

# Cleanup old backups (keep last N days)
find "${BACKUP_DIR}" -name "aria_backup_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "aria_export_*.json" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

REMAINING=$(ls -1 "${BACKUP_DIR}"/aria_backup_*.sql.gz 2>/dev/null | wc -l)
echo "[$(date -Iseconds)] Backup complete. ${REMAINING} backups retained (${KEEP_DAYS}-day retention)."
echo "---"
