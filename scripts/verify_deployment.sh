#!/usr/bin/env bash
set -euo pipefail

QUICK=0
if [[ "${1:-}" == "--quick" ]]; then
  QUICK=1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/stacks/brain/docker-compose.yml"
LOG_FILE="$ROOT_DIR/aria_memories/logs/deploy_verify_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")"

failures=0

check_http() {
  local name="$1"
  local url="$2"
  local expected="$3"
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)"
  echo "HTTP $name $url => $code" | tee -a "$LOG_FILE"
  if [[ "$code" != "$expected" ]]; then
    failures=$((failures + 1))
  fi
}

echo "== container status ==" | tee -a "$LOG_FILE"
docker compose -f "$COMPOSE_FILE" ps | tee -a "$LOG_FILE"

required=(aria-db aria-api aria-web aria-brain litellm traefik)
for name in "${required[@]}"; do
  if ! docker ps --format '{{.Names}}' | grep -qx "$name"; then
    echo "missing container: $name" | tee -a "$LOG_FILE"
    failures=$((failures + 1))
  fi
done

check_http "api-health" "http://localhost:8000/health" "200"
check_http "web-root" "http://localhost:5000/" "200"
check_http "social" "http://localhost:8000/social" "200"
check_http "security" "http://localhost:8000/security-events" "200"
check_http "rate-limits" "http://localhost:8000/rate-limits" "200"

if (( QUICK == 0 )); then
  check_http "goals" "http://localhost:5000/goals" "200"
  check_http "memories" "http://localhost:5000/memories" "200"
  check_http "knowledge" "http://localhost:5000/knowledge" "200"
  check_http "sprint-board" "http://localhost:5000/sprint-board" "200"
fi

if (( failures > 0 )); then
  echo "verification failed: $failures checks" | tee -a "$LOG_FILE"
  exit 1
fi

echo "verification passed" | tee -a "$LOG_FILE"
