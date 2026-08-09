#!/bin/bash
# Aria Database Backup Script
# Backs up all Aria data across all schemas and all databases.
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
BACKUP_ROOT="${VAULT_DIR}/backups/postgres_daily"
DB_CONTAINER="aria-db"
DB_NAME="aria_warehouse"
DB_USER="${DB_USER:-admin}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
BACKUP_FILE="${RUN_DIR}/aria_warehouse.sql.gz"
LITELLM_BACKUP_FILE="${RUN_DIR}/litellm.sql.gz"
ALL_DB_BACKUP_FILE="${RUN_DIR}/postgres_all_databases.sql.gz"
GLOBAL_OBJECTS_FILE="${RUN_DIR}/postgres_globals.sql.gz"
ARIA_DATA_SCHEMA_FILE="${RUN_DIR}/aria_data_schema.sql.gz"
ARIA_ENGINE_SCHEMA_FILE="${RUN_DIR}/aria_engine_schema.sql.gz"
LITELLM_SCHEMA_FILE="${RUN_DIR}/litellm_schema.sql.gz"
JSON_EXPORT="${RUN_DIR}/aria_export.json"
KEEP_DAYS=14

# Ensure backup directory exists
mkdir -p "${RUN_DIR}"

echo "[$(date -Iseconds)] Starting full DB backup..."

# Global objects (roles/tablespaces) for full-cluster recovery
docker exec "${DB_CONTAINER}" pg_dumpall \
    -U "${DB_USER}" \
    --globals-only \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${GLOBAL_OBJECTS_FILE}"

GLOBAL_SIZE=$(ls -lh "${GLOBAL_OBJECTS_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] globals backup: ${GLOBAL_OBJECTS_FILE} (${GLOBAL_SIZE})"

# Full cluster backup (all databases)
docker exec "${DB_CONTAINER}" pg_dumpall \
    -U "${DB_USER}" \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${ALL_DB_BACKUP_FILE}"

ALL_DB_SIZE=$(ls -lh "${ALL_DB_BACKUP_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] all-databases backup: ${ALL_DB_BACKUP_FILE} (${ALL_DB_SIZE})"

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

# Explicit schema backups inside aria_warehouse
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --schema=aria_data \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${ARIA_DATA_SCHEMA_FILE}"

ARIA_DATA_SIZE=$(ls -lh "${ARIA_DATA_SCHEMA_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] aria_data schema backup: ${ARIA_DATA_SCHEMA_FILE} (${ARIA_DATA_SIZE})"

docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --schema=aria_engine \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${ARIA_ENGINE_SCHEMA_FILE}"

ARIA_ENGINE_SIZE=$(ls -lh "${ARIA_ENGINE_SCHEMA_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] aria_engine schema backup: ${ARIA_ENGINE_SCHEMA_FILE} (${ARIA_ENGINE_SIZE})"

docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --schema=litellm \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${LITELLM_SCHEMA_FILE}"

LITELLM_SCHEMA_SIZE=$(ls -lh "${LITELLM_SCHEMA_FILE}" | awk '{print $5}')
echo "[$(date -Iseconds)] litellm schema backup: ${LITELLM_SCHEMA_FILE} (${LITELLM_SCHEMA_SIZE})"

# Full LiteLLM database backup (all LiteLLM-owned data)
if docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d litellm \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    2>/dev/null | gzip > "${LITELLM_BACKUP_FILE}"; then
    LITELLM_BACKUP_SIZE=$(ls -lh "${LITELLM_BACKUP_FILE}" | awk '{print $5}')
    echo "[$(date -Iseconds)] LiteLLM backup: ${LITELLM_BACKUP_FILE} (${LITELLM_BACKUP_SIZE})"
else
    rm -f "${LITELLM_BACKUP_FILE}" || true
    echo "[$(date -Iseconds)] WARNING: litellm database backup failed or database missing (non-fatal)."
fi

# Also create a lightweight JSON export for quick inspection.
# Keep this schema-safe across table/column changes to avoid backup failures.
if ! docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "
SELECT json_build_object(
    'timestamp', now()::text,
    'activities_count', (SELECT count(*) FROM aria_data.activity_log),
    'thoughts_count', (SELECT count(*) FROM aria_data.thoughts),
    'memories_count', (SELECT count(*) FROM aria_data.memories),
    'goals_count', (SELECT count(*) FROM aria_data.goals),
    'social_posts_count', (SELECT count(*) FROM aria_data.social_posts),
    'knowledge_entities_count', (SELECT count(*) FROM aria_data.knowledge_entities),
    'knowledge_relations_count', (SELECT count(*) FROM aria_data.knowledge_relations),
    'heartbeats_count', (SELECT count(*) FROM aria_data.heartbeat_log),
    'chat_sessions_count', (SELECT count(*) FROM aria_engine.chat_sessions),
    'chat_messages_count', (SELECT count(*) FROM aria_engine.chat_messages)
);" > "${JSON_EXPORT}" 2>/dev/null; then
    echo "[$(date -Iseconds)] WARNING: JSON export query failed; writing fallback metadata"
    printf '{"timestamp":"%s","json_export_error":true}\n' "$(date -Iseconds)" > "${JSON_EXPORT}"
fi

echo "[$(date -Iseconds)] JSON export: ${JSON_EXPORT}"

# Mark latest successful backup for quick restore automation
ln -sfn "${RUN_DIR}" "${BACKUP_ROOT}/latest"

# Cleanup old backup runs (keep last N days)
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -name "20*" -mtime +${KEEP_DAYS} -exec rm -rf {} + 2>/dev/null || true

REMAINING_RUNS=$(find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -name "20*" | wc -l | tr -d ' ')
echo "[$(date -Iseconds)] Backup complete. run=${RUN_DIR}, retained_runs=${REMAINING_RUNS} (${KEEP_DAYS}-day retention)."
echo "---"
