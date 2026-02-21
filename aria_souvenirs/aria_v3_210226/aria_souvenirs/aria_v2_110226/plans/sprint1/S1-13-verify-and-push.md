# S1-13: Git Push + Verify All Fixes in Docker

**Priority:** Critical | **Estimate:** 3 pts | **Status:** TODO

---

## Problem

After completing tickets S1-01 through S1-12, all changes need to be:
1. Verified in a fresh Docker deployment
2. Tested end-to-end
3. Committed and pushed to the remote repository

This is the final gate — no partial deployments.

---

## Root Cause

N/A — this is a verification and release ticket, not a bug fix.

---

## Fix

### Step 1: Clean Docker restart

```bash
cd /Users/najia/aria/stacks/brain
docker compose down
docker compose up -d
```

### Step 2: Wait for all containers healthy

```bash
# Wait up to 120s for all services
timeout 120 bash -c 'until docker compose ps --format json | python3 -c "
import sys, json
services = [json.loads(l) for l in sys.stdin if l.strip()]
unhealthy = [s[\"Name\"] for s in services if s.get(\"Health\",\"\") not in (\"healthy\",\"\") and s.get(\"State\") != \"running\"]
print(f\"Waiting: {unhealthy}\") if unhealthy else sys.exit(0)
"; do sleep 5; done'

# Verify all running
docker compose ps
```

### Step 3: Run test suite

```bash
cd /Users/najia/aria
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

### Step 4: Verify each sprint fix

#### S1-08: Deduplicate spend fetches
```bash
grep -c "fetch.*litellm/spend" src/web/templates/models.html
# Expected: 1

grep -c "fetch.*litellm/spend" src/web/templates/wallets.html
# Expected: 1
```

#### S1-09: No console.log in production
```bash
grep -n "console\.log" src/web/templates/wallets.html | grep -v "ARIA_DEBUG"
# Expected: (no output)
```

#### S1-10: Model config fixed
```bash
grep "qwen3-coder" aria_models/models.yaml | grep "model"
# Expected: contains "qwen3-coder:free" (NOT "480b-a35b")

grep -A5 '"chimera-free"' aria_models/models.yaml | grep "tool_calling"
# Expected: "tool_calling": false
```

#### S1-11: DB garbage cleaned
```bash
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT COUNT(*) FROM goals WHERE title IN ('Test Goal', 'Live test goal', 'Patchable');"
# Expected: 0
```

#### S1-12: LiteLLM link fixed
```bash
grep 'href="/litellm"' src/web/templates/services.html
# Expected: (no output)

grep 'href="/models"' src/web/templates/services.html
# Expected: 1 match
```

### Step 5: Browser smoke tests

| Page | URL | Check |
|------|-----|-------|
| Models | `http://localhost:18788/models` | Charts load, single network request to /spend |
| Wallets | `http://localhost:18788/wallets` | Balances load, no console.log spam in DevTools |
| Services | `http://localhost:18788/services` | LiteLLM link goes to /models (no redirect flash) |
| Goals | `http://localhost:18788/goals` | No garbage goals visible |

### Step 6: Git commit and push

```bash
cd /Users/najia/aria

# Check what changed
git status
git diff --stat

# Stage all sprint 1 changes
git add -A

# Commit with descriptive message
git commit -m "Sprint 1: Complete S1-01 through S1-12

- S1-08: Deduplicate spend log fetches (models.html, wallets.html)
- S1-09: Remove console.log from production (wallets.html)
- S1-10: Fix model config (qwen3-coder-free ID, chimera-free tool_calling)
- S1-11: DB cleanup (9 garbage goals removed)
- S1-12: Fix stale /litellm link in services.html
- Plus: S1-01 through S1-07 fixes"

# Push
git push origin main
```

---

## Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | All S1-01 to S1-12 must pass verification | ⚠️ Gate — do not push if any fail |
| 2 | Docker containers must all be healthy | ⚠️ Wait for health checks |
| 3 | Test suite must pass (no regressions) | ⚠️ Run pytest before commit |
| 4 | Git working tree must be clean after commit | ✅ `git status` check |
| 5 | No force-push to main | ✅ Standard push only |
| 6 | Browser smoke tests must pass | ⚠️ Manual verification required |

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| S1-01 through S1-12 | Hard | ALL must be completed before this ticket |
| Docker daemon | Runtime | Must be running |
| `stacks/brain/docker-compose.yml` | Runtime | Compose file for full stack |
| Git remote | Runtime | Must have push access to origin/main |
| Browser | Manual | For smoke tests |

---

## Verification

```bash
# 1. All containers running
cd /Users/najia/aria/stacks/brain && docker compose ps | grep -c "running"
# Expected: matches total service count (all running)

# 2. Test suite passes
cd /Users/najia/aria && python -m pytest tests/ -q 2>&1 | tail -5
# Expected: "X passed" with 0 failures

# 3. Git is clean after push
git status --porcelain
# Expected: (no output — clean working tree)

# 4. Git log shows the commit
git log --oneline -1
# Expected: "Sprint 1: Complete S1-01 through S1-12"

# 5. Remote has the commit
git log --oneline origin/main -1
# Expected: Same hash as local HEAD
```

---

## Prompt for Agent

```
This is the final verification ticket for Sprint 1. Execute these steps in order:

1. Restart Docker:
   cd /Users/najia/aria/stacks/brain
   docker compose down && docker compose up -d

2. Wait for healthy containers (up to 2 minutes):
   docker compose ps

3. Run tests:
   cd /Users/najia/aria
   python -m pytest tests/ -v --tb=short

4. Run verification commands for S1-08 through S1-12:
   - grep -c "fetch.*litellm/spend" src/web/templates/models.html  → expect 1
   - grep -c "fetch.*litellm/spend" src/web/templates/wallets.html  → expect 1
   - grep -n "console\.log" src/web/templates/wallets.html | grep -v "ARIA_DEBUG"  → expect empty
   - grep "qwen3-coder" aria_models/models.yaml | grep "model"  → expect no "480b-a35b"
   - grep -A5 '"chimera-free"' aria_models/models.yaml | grep tool_calling  → expect false
   - docker exec aria-db psql -U aria_admin -d aria_warehouse -c "SELECT COUNT(*) FROM goals WHERE title IN ('Test Goal','Live test goal','Patchable');"  → expect 0
   - grep 'href="/litellm"' src/web/templates/services.html  → expect empty
   - grep 'href="/models"' src/web/templates/services.html  → expect 1 match

5. If ALL checks pass:
   git add -A
   git commit -m "Sprint 1: Complete S1-01 through S1-12"
   git push origin main

6. If ANY check fails: STOP. Report which ticket's verification failed and do not push.
```
