#!/usr/bin/env bash
set -euo pipefail

PATCH_DIR="${1:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/stacks/brain/docker-compose.yml"
BACKUP_DIR="$ROOT_DIR/aria_memories/exports/patch_backup_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$ROOT_DIR/aria_memories/logs/apply_patch_$(date +%Y%m%d_%H%M%S).log"

if [[ -z "$PATCH_DIR" ]]; then
  echo "Usage: $0 <patch-directory>"
  exit 1
fi

if [[ ! -d "$PATCH_DIR" ]]; then
  echo "Patch directory not found: $PATCH_DIR"
  exit 1
fi

mkdir -p "$BACKUP_DIR" "$(dirname "$LOG_FILE")"

echo "[apply_patch] root=$ROOT_DIR patch=$PATCH_DIR" | tee -a "$LOG_FILE"

rollback() {
  echo "[apply_patch] rollback started" | tee -a "$LOG_FILE"
  rsync -a "$BACKUP_DIR/" "$ROOT_DIR/" | tee -a "$LOG_FILE"
  docker compose -f "$COMPOSE_FILE" restart aria-api aria-web aria-brain | tee -a "$LOG_FILE"
  echo "[apply_patch] rollback complete" | tee -a "$LOG_FILE"
}

trap 'echo "[apply_patch] failed" | tee -a "$LOG_FILE"; rollback; exit 1' ERR

while IFS= read -r relpath; do
  [[ -z "$relpath" ]] && continue
  src="$PATCH_DIR/$relpath"
  dst="$ROOT_DIR/$relpath"
  if [[ ! -f "$src" ]]; then
    echo "Missing patch file: $src" | tee -a "$LOG_FILE"
    exit 1
  fi
  mkdir -p "$BACKUP_DIR/$(dirname "$relpath")" "$(dirname "$dst")"
  if [[ -f "$dst" ]]; then
    cp "$dst" "$BACKUP_DIR/$relpath"
  fi
  cp "$src" "$dst"
  echo "[apply_patch] replaced $relpath" | tee -a "$LOG_FILE"
done < <(cd "$PATCH_DIR" && find . -type f ! -name '*.md' ! -name '*.log' | sed 's|^./||')

docker compose -f "$COMPOSE_FILE" restart aria-api aria-web aria-brain | tee -a "$LOG_FILE"

api_code="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || true)"
web_code="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/ || true)"
if [[ "$api_code" != "200" || "$web_code" != "200" ]]; then
  echo "[apply_patch] verification failed api=$api_code web=$web_code" | tee -a "$LOG_FILE"
  rollback
  exit 1
fi

echo "[apply_patch] success" | tee -a "$LOG_FILE"
