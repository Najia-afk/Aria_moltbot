#!/bin/bash
# =============================================================================
# Aria Database Restore Script
# Restores aria_warehouse and/or litellm databases from aria_vault backups
#
# Usage:
#   ./scripts/restore_backup.sh                     # Restore latest backups
#   ./scripts/restore_backup.sh 20260209_030000     # Restore specific timestamp
#   ./scripts/restore_backup.sh --aria-only         # Only aria_warehouse
#   ./scripts/restore_backup.sh --litellm-only      # Only litellm
# =============================================================================

set -euo pipefail
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/local/bin:/usr/bin:$PATH

VAULT_DIR="/Users/najia/aria_vault"
BACKUP_DIR="${VAULT_DIR}/backups"
DB_CONTAINER="aria-db"
DB_USER="${DB_USER:-admin}"

RESTORE_ARIA=true
RESTORE_LITELLM=true
TIMESTAMP=""

# Parse args
for arg in "$@"; do
    case "$arg" in
        --aria-only) RESTORE_LITELLM=false ;;
        --litellm-only) RESTORE_ARIA=false ;;
        *) TIMESTAMP="$arg" ;;
    esac
done

# Check Docker
if ! docker exec "${DB_CONTAINER}" pg_isready -U "${DB_USER}" >/dev/null 2>&1; then
    echo "[ERROR] PostgreSQL container is not running."
    exit 1
fi

# Find latest backups if no timestamp specified
if [ -z "${TIMESTAMP}" ]; then
    if [ "${RESTORE_ARIA}" = true ]; then
        ARIA_FILE=$(ls -t "${BACKUP_DIR}"/aria_warehouse_*.sql.gz 2>/dev/null | head -1)
        if [ -z "${ARIA_FILE}" ]; then
            echo "[ERROR] No aria_warehouse backup found in ${BACKUP_DIR}"
            exit 1
        fi
    fi
    if [ "${RESTORE_LITELLM}" = true ]; then
        LITELLM_FILE=$(ls -t "${BACKUP_DIR}"/litellm_*.sql.gz 2>/dev/null | head -1)
        if [ -z "${LITELLM_FILE}" ]; then
            echo "[ERROR] No litellm backup found in ${BACKUP_DIR}"
            exit 1
        fi
    fi
else
    ARIA_FILE="${BACKUP_DIR}/aria_warehouse_${TIMESTAMP}.sql.gz"
    LITELLM_FILE="${BACKUP_DIR}/litellm_${TIMESTAMP}.sql.gz"
fi

echo "=============================================="
echo "[$(date -Iseconds)] Aria Database Restore"
echo "=============================================="

if [ "${RESTORE_ARIA}" = true ] && [ -f "${ARIA_FILE}" ]; then
    echo "[$(date -Iseconds)] Restoring aria_warehouse from: $(basename "${ARIA_FILE}")"
    gunzip -c "${ARIA_FILE}" | docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d aria_warehouse 2>/dev/null
    echo "[$(date -Iseconds)] aria_warehouse restored."
fi

if [ "${RESTORE_LITELLM}" = true ] && [ -f "${LITELLM_FILE}" ]; then
    echo "[$(date -Iseconds)] Restoring litellm from: $(basename "${LITELLM_FILE}")"
    gunzip -c "${LITELLM_FILE}" | docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d litellm 2>/dev/null
    echo "[$(date -Iseconds)] litellm restored."
fi

echo "=============================================="
echo "[$(date -Iseconds)] Restore Complete"
echo "=============================================="
