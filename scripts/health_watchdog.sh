#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="$ROOT_DIR/aria_memories/logs/health_watchdog.state"
ALERT_FILE="$ROOT_DIR/aria_memories/logs/health_watchdog_alert_$(date +%Y%m%d_%H%M%S).md"
LOG_FILE="$ROOT_DIR/aria_memories/logs/health_watchdog.log"
CONTAINER="${1:-aria-api}"
MAX_STRIKES=3
MAX_RESTARTS=2

mkdir -p "$(dirname "$STATE_FILE")"

strikes=0
restarts=0
if [[ -f "$STATE_FILE" ]]; then
  source "$STATE_FILE"
fi

health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo 'missing')"

if [[ "$health" == "healthy" || "$health" == "running" ]]; then
  strikes=0
  echo "$(date -Iseconds) [$CONTAINER] health=$health strikes=$strikes" >> "$LOG_FILE"
else
  strikes=$((strikes + 1))
  echo "$(date -Iseconds) [$CONTAINER] health=$health strikes=$strikes" >> "$LOG_FILE"
fi

if (( strikes >= MAX_STRIKES )); then
  if (( restarts < MAX_RESTARTS )); then
    docker restart "$CONTAINER" >> "$LOG_FILE" 2>&1 || true
    restarts=$((restarts + 1))
    strikes=0
    echo "$(date -Iseconds) [$CONTAINER] auto-restart attempt=$restarts" >> "$LOG_FILE"
  else
    cat > "$ALERT_FILE" <<EOF
# Health Watchdog Alert

- Time: $(date -Iseconds)
- Container: $CONTAINER
- Status: $health
- Strikes: $MAX_STRIKES
- Restart attempts exhausted: $MAX_RESTARTS

Manual intervention required.
EOF
  fi
fi

cat > "$STATE_FILE" <<EOF
strikes=$strikes
restarts=$restarts
EOF
