#!/bin/bash
# Aria Database Backup Script for Mac Server
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/bin:$PATH

# Self-locate: resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"

# Source environment from .env if available
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"
if [ -f "${ENV_FILE}" ]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" || "$value" == *" "* ]] && continue
        export "$key=$value"
    done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" | sed 's/\r$//')
fi

VAULT_DIR="${VAULT_DIR:-${HOME}/aria_vault}"
BACKUP_DIR="${VAULT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="aria_backup_${TIMESTAMP}.dump"

echo "=== Aria Database Backup ==="
echo "Timestamp: $TIMESTAMP"
echo "Backup dir: $BACKUP_DIR"

# Create backup inside container
docker exec aria-db pg_dump -U "${DB_USER:-admin}" -d aria_warehouse -Fc -f /tmp/aria_backup.dump
if [ $? -ne 0 ]; then
    echo "ERROR: pg_dump failed"
    exit 1
fi

# Copy to host
docker cp aria-db:/tmp/aria_backup.dump "${BACKUP_DIR}/${BACKUP_FILE}"
if [ $? -ne 0 ]; then
    echo "ERROR: docker cp failed"
    exit 1
fi

# Cleanup container tmp
docker exec aria-db rm /tmp/aria_backup.dump

echo "Backup created: ${BACKUP_DIR}/${BACKUP_FILE}"
ls -lh "${BACKUP_DIR}/"

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t aria_backup_*.dump 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null
echo "=== Backup Complete ==="
