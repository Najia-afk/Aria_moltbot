#!/bin/bash
# =============================================================================
# Aria Complete Daily Backup Script
# Backs up BOTH aria_warehouse (Aria) and litellm (LiteLLM) databases
# Also exports key tables as CSV for easy import/analysis
# Stores everything in ~/aria_vault/ (OUTSIDE the aria/ repo)
#
# Usage:  ./scripts/daily_backup.sh
# Cron:   0 3 * * * ~/aria/scripts/daily_backup.sh >> ~/aria_vault/daily_backup.log 2>&1
# =============================================================================

set -euo pipefail
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/local/bin:/usr/bin:$PATH

# Self-locate: resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"

# Source environment from .env if available (gets DB_USER, DB_PASSWORD, etc.)
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
fi

# Configuration — VAULT_DIR can be overridden via .env
VAULT_DIR="${VAULT_DIR:-${HOME}/aria_vault}"
BACKUP_DIR="${VAULT_DIR}/backups"
CSV_DIR="${VAULT_DIR}/csv_exports"
MEMORIES_DIR="${VAULT_DIR}/aria_memories_snapshot"
DB_CONTAINER="aria-db"
DB_USER="${DB_USER:-admin}"
ARIA_DB="aria_warehouse"
LITELLM_DB="litellm"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_TAG=$(date +%Y-%m-%d)
KEEP_DAYS=14

# Ensure directories exist
mkdir -p "${BACKUP_DIR}" "${CSV_DIR}/${DATE_TAG}" "${MEMORIES_DIR}"

echo "=============================================="
echo "[$(date -Iseconds)] Aria Daily Backup Starting"
echo "=============================================="

# -------------------------------------------------------
# 1. Check Docker is running
# -------------------------------------------------------
if ! docker ps >/dev/null 2>&1; then
    echo "[ERROR] Docker is not running. Cannot proceed."
    exit 1
fi

if ! docker exec "${DB_CONTAINER}" pg_isready -U "${DB_USER}" >/dev/null 2>&1; then
    echo "[ERROR] PostgreSQL is not ready in ${DB_CONTAINER}."
    exit 1
fi

echo "[$(date -Iseconds)] Docker + PostgreSQL OK"

# -------------------------------------------------------
# 2. Full dump of aria_warehouse
# -------------------------------------------------------
ARIA_DUMP="${BACKUP_DIR}/aria_warehouse_${TIMESTAMP}.sql.gz"
echo "[$(date -Iseconds)] Backing up ${ARIA_DB}..."
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${ARIA_DB}" \
    --no-owner --no-acl --clean --if-exists \
    2>/dev/null | gzip > "${ARIA_DUMP}"
echo "[$(date -Iseconds)] -> $(ls -lh "${ARIA_DUMP}" | awk '{print $5}')"

# -------------------------------------------------------
# 3. Full dump of litellm database
# -------------------------------------------------------
LITELLM_DUMP="${BACKUP_DIR}/litellm_${TIMESTAMP}.sql.gz"
echo "[$(date -Iseconds)] Backing up ${LITELLM_DB}..."
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${LITELLM_DB}" \
    --no-owner --no-acl --clean --if-exists \
    2>/dev/null | gzip > "${LITELLM_DUMP}"
echo "[$(date -Iseconds)] -> $(ls -lh "${LITELLM_DUMP}" | awk '{print $5}')"

# -------------------------------------------------------
# 4. CSV export of key Aria tables
# -------------------------------------------------------
echo "[$(date -Iseconds)] Exporting CSVs from ${ARIA_DB}..."

ARIA_TABLES=(
    activity_log
    thoughts
    memories
    goals
    social_posts
    heartbeat_log
    rate_limits
    agent_sessions
    model_usage
    security_events
    knowledge_entities
    knowledge_relations
    key_value_memory
    performance_log
    hourly_goals
    model_cost_reference
    moltbook_users
    spending_log
)

for table in "${ARIA_TABLES[@]}"; do
    csv_file="${CSV_DIR}/${DATE_TAG}/${table}.csv"
    docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${ARIA_DB}" -c \
        "\\COPY (SELECT * FROM ${table}) TO STDOUT WITH CSV HEADER" \
        > "${csv_file}" 2>/dev/null || true
    if [ -s "${csv_file}" ]; then
        rows=$(wc -l < "${csv_file}")
        echo "  ${table}: $((rows - 1)) rows"
    else
        echo "  ${table}: empty or not found"
        rm -f "${csv_file}"
    fi
done

# -------------------------------------------------------
# 5. CSV export of LiteLLM key tables
# -------------------------------------------------------
echo "[$(date -Iseconds)] Exporting CSVs from ${LITELLM_DB}..."

# LiteLLM creates these tables automatically
LITELLM_TABLES=(
    "litellm_spendlog"
    "litellm_teamtable"
    "litellm_usertable"
    "litellm_endusertable"
    "litellm_budgettable"
    "litellm_verificationtoken"
)

for table in "${LITELLM_TABLES[@]}"; do
    csv_file="${CSV_DIR}/${DATE_TAG}/litellm_${table}.csv"
    docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${LITELLM_DB}" -c \
        "\\COPY (SELECT * FROM ${table}) TO STDOUT WITH CSV HEADER" \
        > "${csv_file}" 2>/dev/null || true
    if [ -s "${csv_file}" ]; then
        rows=$(wc -l < "${csv_file}")
        echo "  ${table}: $((rows - 1)) rows"
    else
        rm -f "${csv_file}"
    fi
done

# -------------------------------------------------------
# 6. JSON summary for quick inspection
# -------------------------------------------------------
JSON_SUMMARY="${BACKUP_DIR}/aria_summary_${DATE_TAG}.json"
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${ARIA_DB}" -t -A -c "
SELECT json_build_object(
    'backup_date', '${DATE_TAG}',
    'timestamp', now()::text,
    'activities', (SELECT count(*) FROM activity_log),
    'thoughts', (SELECT count(*) FROM thoughts),
    'memories', (SELECT count(*) FROM memories),
    'goals', (SELECT count(*) FROM goals),
    'social_posts', (SELECT count(*) FROM social_posts),
    'knowledge_entities', (SELECT count(*) FROM knowledge_entities),
    'knowledge_relations', (SELECT count(*) FROM knowledge_relations),
    'heartbeats', (SELECT count(*) FROM heartbeat_log),
    'model_usage', (SELECT count(*) FROM model_usage),
    'active_goals', (
        SELECT json_agg(row_to_json(g))
        FROM (SELECT goal_id, title, status, priority, progress FROM goals WHERE status IN ('active','pending') ORDER BY priority LIMIT 10) g
    ),
    'recent_activities', (
        SELECT json_agg(row_to_json(a))
        FROM (SELECT id, action, skill, success, created_at FROM activity_log ORDER BY created_at DESC LIMIT 10) a
    )
);" > "${JSON_SUMMARY}" 2>/dev/null || echo '{"error": "summary query failed"}' > "${JSON_SUMMARY}"
echo "[$(date -Iseconds)] JSON summary: ${JSON_SUMMARY}"

# -------------------------------------------------------
# 7. Snapshot aria_memories (file-based artifacts)
# -------------------------------------------------------
echo "[$(date -Iseconds)] Snapshotting aria_memories..."
MEMORIES_SNAPSHOT="${MEMORIES_DIR}/aria_memories_${DATE_TAG}.tar.gz"
if [ -d "${ARIA_DIR}/aria_memories" ]; then
    tar czf "${MEMORIES_SNAPSHOT}" -C "${ARIA_DIR}" aria_memories/ 2>/dev/null || true
    echo "[$(date -Iseconds)] -> $(ls -lh "${MEMORIES_SNAPSHOT}" | awk '{print $5}')"
fi

# -------------------------------------------------------
# 8. Cleanup old backups (keep KEEP_DAYS days)
# -------------------------------------------------------
echo "[$(date -Iseconds)] Cleaning up backups older than ${KEEP_DAYS} days..."
find "${BACKUP_DIR}" -name "aria_warehouse_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "litellm_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "aria_export_*.json" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "aria_summary_*.json" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${CSV_DIR}" -maxdepth 1 -type d -mtime +${KEEP_DAYS} -exec rm -rf {} \; 2>/dev/null || true
find "${MEMORIES_DIR}" -name "aria_memories_*.tar.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

# -------------------------------------------------------
# 9. Summary
# -------------------------------------------------------
REMAINING_SQL=$(ls -1 "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | wc -l)
REMAINING_CSV=$(find "${CSV_DIR}" -name "*.csv" 2>/dev/null | wc -l)
VAULT_SIZE=$(du -sh "${VAULT_DIR}" 2>/dev/null | awk '{print $1}')

echo "=============================================="
echo "[$(date -Iseconds)] Backup Complete"
echo "  SQL dumps: ${REMAINING_SQL}"
echo "  CSV files: ${REMAINING_CSV}"
echo "  Vault size: ${VAULT_SIZE}"
echo "=============================================="
