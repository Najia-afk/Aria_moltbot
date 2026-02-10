#!/bin/bash
# Aria Daily Backup — pg_dump both DBs + tgz aria_memories
# Cron: 0 3 * * * ~/aria/scripts/backup.sh >> ~/aria_vault/backup.log 2>&1
set -euo pipefail
export PATH=/bin:/usr/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"
VAULT_DIR="${HOME}/aria_vault"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=14
DB_CONTAINER="aria-db"
DB_USER="${DB_USER:-admin}"

mkdir -p "${VAULT_DIR}"

echo "[$(date -Iseconds)] Backup starting..."

# 1. aria_warehouse (Aria tables)
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d aria_warehouse \
    --no-owner --no-acl --clean --if-exists \
    | gzip > "${VAULT_DIR}/aria_warehouse_${TIMESTAMP}.sql.gz"
echo "[$(date -Iseconds)] aria_warehouse: $(du -h "${VAULT_DIR}/aria_warehouse_${TIMESTAMP}.sql.gz" | cut -f1)"

# 2. litellm (LLM proxy data)
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d litellm \
    --no-owner --no-acl --clean --if-exists \
    | gzip > "${VAULT_DIR}/litellm_${TIMESTAMP}.sql.gz"
echo "[$(date -Iseconds)] litellm: $(du -h "${VAULT_DIR}/litellm_${TIMESTAMP}.sql.gz" | cut -f1)"

# 3. aria_memories snapshot
if [ -d "${ARIA_DIR}/aria_memories" ]; then
    tar czf "${VAULT_DIR}/aria_memories_${TIMESTAMP}.tgz" -C "${ARIA_DIR}" aria_memories/
    echo "[$(date -Iseconds)] aria_memories: $(du -h "${VAULT_DIR}/aria_memories_${TIMESTAMP}.tgz" | cut -f1)"
fi

# 4. Cleanup older than KEEP_DAYS
find "${VAULT_DIR}" -name "aria_warehouse_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${VAULT_DIR}" -name "litellm_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
find "${VAULT_DIR}" -name "aria_memories_*.tgz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

echo "[$(date -Iseconds)] Backup complete. Vault: $(du -sh "${VAULT_DIR}" | cut -f1)"
