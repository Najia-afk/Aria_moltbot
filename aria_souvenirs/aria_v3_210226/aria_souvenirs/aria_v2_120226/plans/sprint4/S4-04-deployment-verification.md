# S4-04: Create Deployment Verification Script
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P0 | **Points:** 3 | **Phase:** 4

## Problem
After every change (patch, restart, deploy), verification is manual:
- Shiva runs `docker ps` to check containers
- Shiva curls a few endpoints by hand
- Shiva opens the dashboard to check if pages load
- No systematic check of ALL endpoints and ALL pages

This is slow, error-prone, and incomplete. Issues slip through.

## Root Cause
No automated deployment verification script exists. The `scripts/check_architecture.py` checks code quality but not runtime health.

## Fix
Create `scripts/verify_deployment.sh`:

```bash
#!/bin/bash
# scripts/verify_deployment.sh — Full Deployment Verification
# Usage: ./scripts/verify_deployment.sh [--quick]
#
# Checks:
#   1. All 9 Docker containers running
#   2. API health endpoint
#   3. All API endpoints return expected status codes
#   4. All frontend pages return 200
#   5. Database connectivity
#   6. Ollama connectivity
#   7. Architecture compliance (optional, skip with --quick)
#
# Exit: 0 = all pass, 1 = failures found

set -uo pipefail

PASS=0
FAIL=0
WARN=0
RESULTS=""

check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"
    
    result=$(eval "$cmd" 2>/dev/null)
    if echo "$result" | grep -q "$expected"; then
        PASS=$((PASS+1))
        RESULTS+="✅ $name\n"
    else
        FAIL=$((FAIL+1))
        RESULTS+="❌ $name (got: $result)\n"
    fi
}

echo "═══════════════════════════════════════"
echo "  Aria Deployment Verification"
echo "  $(date)"
echo "═══════════════════════════════════════"

# ═══ DOCKER CONTAINERS ═══
echo -e "\n📦 Docker Containers:"
EXPECTED_CONTAINERS="aria-db aria-api aria-web aria-brain clawdbot litellm traefik tor-proxy aria-browser"
for c in $EXPECTED_CONTAINERS; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
    check "Container: $c" "echo '$STATUS'" "running"
done

# ═══ API HEALTH ═══
echo -e "\n🏥 API Health:"
check "API /health" "curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null | grep status" "healthy"
check "DB connected" "curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null | grep database" "connected"

# ═══ API ENDPOINTS ═══
echo -e "\n🔌 API Endpoints:"
ENDPOINTS="goals memories thoughts activities sessions kg/entities working-memory lessons skills proposals records"
for ep in $ENDPOINTS; do
    check "GET /api/$ep" "curl -sf -o /dev/null -w '%{http_code}' http://localhost:8000/api/$ep" "200"
done

# ═══ FRONTEND PAGES ═══
echo -e "\n🖥️ Frontend Pages:"
PAGES="/ /goals /thoughts /memories /models /wallets /sessions /knowledge /sprint-board /skills /heartbeat /activities /social /security /settings"
for page in $PAGES; do
    check "Page $page" "curl -sf -o /dev/null -w '%{http_code}' http://localhost:5000$page" "200"
done

# ═══ OLLAMA ═══
echo -e "\n🧠 Ollama:"
check "Ollama API" "curl -sf http://localhost:11434/api/tags | head -c 20" "models"

# ═══ ARCHITECTURE (skip with --quick) ═══
if [ "${1:-}" != "--quick" ]; then
    echo -e "\n🏗️ Architecture:"
    ARCH_ERRORS=$(python scripts/check_architecture.py 2>&1 | grep "ERRORS:" | grep -o "[0-9]*")
    check "Architecture errors" "echo '${ARCH_ERRORS:-0}'" "0"
fi

# ═══ SUMMARY ═══
echo -e "\n═══════════════════════════════════════"
echo -e "$RESULTS"
echo "═══════════════════════════════════════"
echo "Total: $PASS passed, $FAIL failed, $WARN warnings"

if [ "$FAIL" -gt 0 ]; then
    echo "❌ DEPLOYMENT VERIFICATION FAILED"
    exit 1
else
    echo "✅ DEPLOYMENT VERIFIED"
    exit 0
fi
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Infrastructure script |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Checks Docker containers |
| 5 | aria_memories writable | ❌ | Output to stdout |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone script.

## Verification
```bash
# 1. Script exists and is executable:
ls -la scripts/verify_deployment.sh
# EXPECTED: -rwxr-xr-x

# 2. Quick mode runs:
./scripts/verify_deployment.sh --quick
# EXPECTED: "DEPLOYMENT VERIFIED" (or list of failures)

# 3. Full mode runs:
./scripts/verify_deployment.sh
# EXPECTED: "DEPLOYMENT VERIFIED" with architecture check

# 4. Exit code is correct:
./scripts/verify_deployment.sh --quick; echo "Exit: $?"
# EXPECTED: Exit: 0 (if all healthy)
```

## Prompt for Agent
```
Create a comprehensive deployment verification script.

**Files to read:**
- scripts/check_architecture.py (existing checker to integrate)
- stacks/brain/docker-compose.yml (container names)
- src/api/main.py (list of routers for endpoint checking)

**Steps:**
1. Create scripts/verify_deployment.sh
2. Test each category: containers, API, frontend, Ollama, architecture
3. Use color-coded output with emoji status indicators
4. Support --quick flag to skip slow checks
5. Return exit code 0/1 for CI integration
6. Make executable (chmod +x)
7. Add Makefile target: `make verify`
8. Run the script and fix any false positives
```
