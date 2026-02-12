# S4-02: Add Health-Based Auto-Restart
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P1 | **Points:** 3 | **Phase:** 4

## Problem
When a container becomes unhealthy (OOM, deadlock, DB connection pool exhaustion), it stays unhealthy until Shiva manually restarts it via SSH. This can leave Aria non-functional for hours overnight.

Currently:
- Docker has basic health checks (HEALTHCHECK in Dockerfile)
- But no automation acts on unhealthy status
- The cron `hourly_health_check` logs health but doesn't restart anything

## Root Cause
No watchdog process monitors container health and takes corrective action. Docker's built-in `restart: unless-stopped` only handles crashes, not "running but unhealthy" states.

## Fix
Create `scripts/health_watchdog.sh` that:

```bash
#!/bin/bash
# scripts/health_watchdog.sh — Container Health Watchdog
# Run via cron every 5 minutes: */5 * * * * /path/to/health_watchdog.sh
#
# Logic:
#   1. Check health of critical containers (aria-api, aria-web, aria-db)
#   2. If unhealthy 3 consecutive times → restart container
#   3. Log all restarts to aria_memories/logs/
#   4. If restart doesn't help after 2 attempts → alert file

CRITICAL_CONTAINERS="aria-api aria-web aria-db"
STATE_DIR="/tmp/aria_health_state"
LOG_DIR="aria_memories/logs"
MAX_FAILS=3
MAX_RESTARTS=2

mkdir -p "$STATE_DIR" "$LOG_DIR"

for container in $CRITICAL_CONTAINERS; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing")
    FAIL_FILE="$STATE_DIR/${container}_fails"
    RESTART_FILE="$STATE_DIR/${container}_restarts"
    
    if [ "$HEALTH" = "healthy" ]; then
        # Reset counters on healthy
        echo "0" > "$FAIL_FILE"
        echo "0" > "$RESTART_FILE"
    else
        FAILS=$(cat "$FAIL_FILE" 2>/dev/null || echo "0")
        FAILS=$((FAILS + 1))
        echo "$FAILS" > "$FAIL_FILE"
        
        if [ "$FAILS" -ge "$MAX_FAILS" ]; then
            RESTARTS=$(cat "$RESTART_FILE" 2>/dev/null || echo "0")
            if [ "$RESTARTS" -lt "$MAX_RESTARTS" ]; then
                echo "[$(date)] Auto-restarting $container (fail count: $FAILS)" >> "$LOG_DIR/watchdog.log"
                docker compose restart "$container"
                RESTARTS=$((RESTARTS + 1))
                echo "$RESTARTS" > "$RESTART_FILE"
                echo "0" > "$FAIL_FILE"
            else
                echo "[$(date)] ALERT: $container still unhealthy after $MAX_RESTARTS restarts" >> "$LOG_DIR/watchdog.log"
                echo "ALERT: $container unhealthy" > "$STATE_DIR/ALERT_${container}"
            fi
        fi
    fi
done
```

Also add a crontab entry (or document how to add one):
```
*/5 * * * * cd /Users/najia/aria && ./scripts/health_watchdog.sh
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Infrastructure script |
| 2 | .env secrets | ❌ | No secrets accessed |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Uses docker compose for restarts |
| 5 | aria_memories writable | ✅ | Writes watchdog.log |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone infrastructure.

## Verification
```bash
# 1. Script exists and is executable:
ls -la scripts/health_watchdog.sh
# EXPECTED: -rwxr-xr-x

# 2. Dry run (all containers healthy):
./scripts/health_watchdog.sh
cat /tmp/aria_health_state/*_fails 2>/dev/null
# EXPECTED: all 0 (healthy containers reset counters)

# 3. Simulate unhealthy (stop a non-critical test container if available):
# Or just verify the logic manually:
mkdir -p /tmp/aria_health_state
echo "3" > /tmp/aria_health_state/test-container_fails
echo "0" > /tmp/aria_health_state/test-container_restarts
# Verify the script would attempt restart at 3 fails

# 4. Watchdog log exists:
ls aria_memories/logs/watchdog.log 2>/dev/null || echo "No watchdog events yet (all healthy)"
# EXPECTED: either file exists or "No watchdog events" message
```

## Prompt for Agent
```
Create a container health watchdog script for auto-restart on failure.

**Files to read:**
- stacks/brain/docker-compose.yml (container names and health check configs)
- scripts/ (existing scripts for style)
- Makefile (check for existing health targets)

**Steps:**
1. Create scripts/health_watchdog.sh with:
   - Health check loop for critical containers
   - Consecutive failure counting (3 strikes)
   - Auto-restart with attempt limiting (max 2)
   - Alert file creation when restarts exhausted
   - Full logging to aria_memories/logs/watchdog.log
2. Make executable (chmod +x)
3. Document crontab installation in script header
4. Test with a dry run (all containers should be healthy)
5. Add a Makefile target: `make watchdog`
```
