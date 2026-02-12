#!/bin/bash
# Aria Database Backup Script
# Backs up full aria_warehouse + full litellm databases.
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
BACKUP_FILE="${BACKUP_DIR}/aria_warehouse_backup_${TIMESTAMP}.sql.gz"
LITELLM_BACKUP_FILE="${BACKUP_DIR}/litellm_backup_${TIMESTAMP}.sql.gz"
JSON_EXPORT="${BACKUP_DIR}/aria_export_${TIMESTAMP}.json"
KEEP_DAYS=7

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting full DB backup..."

# Full aria_warehouse backup (includes all current and future tables)
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${BACKUP_FILE}"

BACKUP_SIZE=$(ls -lh "${BACKUP_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] aria_warehouse backup: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Full LiteLLM database backup (all LiteLLM-owned data)
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d litellm \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${LITELLM_BACKUP_FILE}"

LITELLM_BACKUP_SIZE=$(ls -lh "${LITELLM_BACKUP_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] LiteLLM backup: ${LITELLM_BACKUP_FILE} (${LITELLM_BACKUP_SIZE})"

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
find "${BACKUP_DIR}" -name "aria_warehouse_backup_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "litellm_backup_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "aria_export_*.json" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

REMAINING=$(ls -1 "${BACKUP_DIR}"/aria_warehouse_backup_*.sql.gz 2>/dev/null | wc -l)
REMAINING_LITELLM=$(ls -1 "${BACKUP_DIR}"/litellm_backup_*.sql.gz 2>/dev/null | wc -l)
echo "[$(date -Iseconds)] Backup complete. aria_warehouse: ${REMAINING}, litellm: ${REMAINING_LITELLM} retained (${KEEP_DAYS}-day retention)."
echo "---"
