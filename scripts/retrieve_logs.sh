#!/bin/bash
# =============================================================================
# retrieve_logs.sh — Pull logs from Mac Mini for offline analysis
# TICKET-28: Log Analysis (Aria Blue v1.1)
#
# Usage:
#   bash scripts/retrieve_logs.sh [--output-dir DIR] [--hours N]
#
# Requires SSH access to the Mac Mini.
# =============================================================================
set -euo pipefail

# Defaults
SSH_KEY="${SSH_KEY:-$HOME/.ssh/najia_mac_key}"
SSH_HOST="${SSH_HOST:-${MAC_USER:-najia}@${MAC_HOST:?MAC_HOST env var not set}}"
OUTPUT_DIR="${OUTPUT_DIR:-aria_memories/logs}"
HOURS="${HOURS:-168}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --hours)      HOURS="$2"; shift 2 ;;
    --ssh-key)    SSH_KEY="$2"; shift 2 ;;
    --ssh-host)   SSH_HOST="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--output-dir DIR] [--hours N] [--ssh-key PATH] [--ssh-host USER@HOST]"
      echo ""
      echo "Options:"
      echo "  --output-dir   Directory to save logs (default: aria_memories/logs)"
      echo "  --hours        Hours of history to retrieve (default: 168 = 7 days)"
      echo "  --ssh-key      Path to SSH private key"
      echo "  --ssh-host     SSH target (user@host)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

SSH_CMD="ssh -i ${SSH_KEY} -o ConnectTimeout=10 -o StrictHostKeyChecking=no ${SSH_HOST}"

mkdir -p "${OUTPUT_DIR}"

echo "=== Aria Log Retrieval — $(date) ==="
echo "Target: ${SSH_HOST} | Hours: ${HOURS}h | Output: ${OUTPUT_DIR}"
echo ""

# ---- 1. OpenClaw (clawdbot) logs ----
echo "[1/4] Retrieving OpenClaw logs (${HOURS}h)..."
OPENCLAW_FILE="${OUTPUT_DIR}/openclaw_${TIMESTAMP}.log"
if ${SSH_CMD} "docker logs clawdbot --since ${HOURS}h 2>&1" > "${OPENCLAW_FILE}" 2>&1; then
  LINE_COUNT=$(wc -l < "${OPENCLAW_FILE}")
  echo "  ✅ Saved ${LINE_COUNT} lines → ${OPENCLAW_FILE}"
else
  echo "  ❌ Failed to retrieve OpenClaw logs (exit $?)"
  echo "RETRIEVAL_FAILED" > "${OPENCLAW_FILE}"
fi

# ---- 2. LiteLLM logs ----
echo "[2/4] Retrieving LiteLLM logs (tail 2000)..."
LITELLM_FILE="${OUTPUT_DIR}/litellm_${TIMESTAMP}.log"
if ${SSH_CMD} "docker logs litellm --tail 2000 2>&1" > "${LITELLM_FILE}" 2>&1; then
  LINE_COUNT=$(wc -l < "${LITELLM_FILE}")
  echo "  ✅ Saved ${LINE_COUNT} lines → ${LITELLM_FILE}"
else
  echo "  ❌ Failed to retrieve LiteLLM logs (exit $?)"
  echo "RETRIEVAL_FAILED" > "${LITELLM_FILE}"
fi

# ---- 3. MLX process info ----
echo "[3/4] Retrieving MLX process info..."
MLX_FILE="${OUTPUT_DIR}/mlx_processes_${TIMESTAMP}.log"
if ${SSH_CMD} "ps aux | grep -i mlx 2>&1; echo '---'; nvidia-smi 2>/dev/null || echo 'No nvidia-smi'; echo '---'; top -l 1 -n 10 2>/dev/null | head -20 || echo 'top unavailable'" > "${MLX_FILE}" 2>&1; then
  echo "  ✅ Saved → ${MLX_FILE}"
else
  echo "  ❌ Failed to retrieve MLX info (exit $?)"
  echo "RETRIEVAL_FAILED" > "${MLX_FILE}"
fi

# ---- 4. Docker stats snapshot ----
echo "[4/4] Retrieving Docker stats snapshot..."
DOCKER_FILE="${OUTPUT_DIR}/docker_stats_${TIMESTAMP}.log"
if ${SSH_CMD} "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1; echo '---'; docker stats --no-stream 2>&1" > "${DOCKER_FILE}" 2>&1; then
  echo "  ✅ Saved → ${DOCKER_FILE}"
else
  echo "  ❌ Failed to retrieve Docker stats (exit $?)"
  echo "RETRIEVAL_FAILED" > "${DOCKER_FILE}"
fi

echo ""
echo "=== Retrieval complete ==="
echo "Log files in ${OUTPUT_DIR}/:"
ls -lh "${OUTPUT_DIR}"/*_${TIMESTAMP}.log 2>/dev/null || echo "(no files found)"
