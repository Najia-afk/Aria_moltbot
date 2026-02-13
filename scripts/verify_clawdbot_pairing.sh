#!/usr/bin/env bash
set -euo pipefail

# Verify OpenClaw Telegram pairing persistence after clawdbot rebuild.
# Optional repair mode: pass a fresh pairing code explicitly.
#
# Usage:
#   scripts/verify_clawdbot_pairing.sh --user-id 1643801012
#   scripts/verify_clawdbot_pairing.sh --user-id 1643801012 --approve-code U8GRXFMV

COMPOSE_FILE="stacks/brain/docker-compose.yml"
SERVICE="clawdbot"
EXPECTED_USER_ID=""
APPROVE_CODE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user-id)
      EXPECTED_USER_ID="${2:-}"
      shift 2
      ;;
    --approve-code)
      APPROVE_CODE="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$EXPECTED_USER_ID" ]]; then
  echo "Missing --user-id" >&2
  exit 2
fi

run_in_clawdbot() {
  docker compose -f "$COMPOSE_FILE" exec "$SERVICE" sh -lc "$1"
}

echo "[check] clawdbot running"
docker compose -f "$COMPOSE_FILE" ps "$SERVICE" >/dev/null

echo "[check] openclaw CLI available"
run_in_clawdbot 'openclaw --version >/dev/null'

ALLOW_FILE="/root/.openclaw/credentials/telegram-allowFrom.json"

echo "[check] pairing allow-list file exists"
run_in_clawdbot "test -f '$ALLOW_FILE'"

echo "[check] user id $EXPECTED_USER_ID present in allow-list"
if run_in_clawdbot "grep -q '\"$EXPECTED_USER_ID\"' '$ALLOW_FILE'"; then
  echo "[ok] user id is already approved and persisted"
  exit 0
fi

if [[ -n "$APPROVE_CODE" ]]; then
  echo "[repair] approving with provided pairing code"
  run_in_clawdbot "openclaw pairing approve telegram '$APPROVE_CODE'"
  echo "[verify] checking allow-list again"
  run_in_clawdbot "grep -q '\"$EXPECTED_USER_ID\"' '$ALLOW_FILE'"
  echo "[ok] repaired: user id approved"
  exit 0
fi

echo "[fail] user id not approved. Provide fresh code with --approve-code" >&2
exit 1
