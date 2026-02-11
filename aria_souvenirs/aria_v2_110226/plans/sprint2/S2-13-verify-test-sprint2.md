# S2-13: Sprint 2 Verification & Integration Testing
**Epic:** E4 — QA | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem  
All Sprint 2 tickets (S2-01 through S2-12) must be verified as a complete unit. Individual ticket verification may pass while integration breaks.

## Root Cause
N/A — this is a verification ticket, not a bug fix.

## Fix
No code changes. Run comprehensive verification.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Verify all changes respect architecture |
| 2 | .env secrets | ✅ | Verify no secrets leaked into code |
| 3 | models.yaml | ✅ | Verify no hardcoded model names added |
| 4 | Docker-first | ✅ | All tests run in Docker |
| 5 | aria_memories | ✅ | Verify no writes outside aria_memories |
| 6 | No soul mod | ✅ | Verify soul files untouched |

## Dependencies
ALL Sprint 2 tickets (S2-01 through S2-12) must complete first.

## Verification
```bash
# === Architecture Compliance ===

# 1. No secrets in code:
grep -rn 'sk-\|MOONSHOT.*=.*[a-zA-Z0-9]' src/ aria_skills/ --include='*.py' | grep -v '.env' | grep -v 'os.getenv\|os.environ'
# EXPECTED: 0 results

# 2. No hardcoded model names:
grep -rn '"gpt-4\|"claude\|"kimi\|"moonshot"' src/ aria_skills/ --include='*.py' | grep -v 'models.yaml\|test_\|#'
# EXPECTED: 0 results (all via models.yaml)

# === Bug Fixes ===

# 3. Goal priority sort (S2-01):
curl -s http://localhost:8000/api/goals?limit=5 | python3 -c "
import sys,json; goals=json.load(sys.stdin).get('items',json.load(sys.stdin))
priorities = [g['priority'] for g in goals]
assert priorities == sorted(priorities), f'Not sorted asc: {priorities}'
print('S2-01 PASS: priorities ascending')
"

# 4. Pagination works (S2-06):
curl -s 'http://localhost:8000/api/goals?page=1&limit=2' | python3 -c "
import sys,json; d=json.load(sys.stdin)
assert 'items' in d and 'total' in d and 'pages' in d
print(f'S2-06 PASS: paginated response ({d[\"total\"]} total, {d[\"pages\"]} pages)')
"

# 5. Update non-existent goal returns 404 (S2-12):
code=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH http://localhost:8000/api/goals/fake-id -H 'Content-Type: application/json' -d '{"status":"x"}')
[ "$code" = "404" ] && echo "S2-12 PASS: 404 on missing goal" || echo "S2-12 FAIL: got $code"

# === Full Test Suite ===
# 6. API tests:
cd src/api && python -m pytest -x -q --tb=short

# 7. Docker health:
docker compose ps --format '{{.Name}}: {{.Status}}' | grep -v 'Up'
# EXPECTED: empty (all services Up)

# === Soul Integrity ===
# 8. No soul files modified:
git diff --name-only HEAD -- aria_mind/soul/ aria_mind/SOUL.md aria_mind/IDENTITY.md
# EXPECTED: empty

echo "Sprint 2 Verification Complete"
```

## Prompt for Agent
```
You are running Sprint 2 integration tests.

STEPS:
1. Run ALL verification commands above in sequence
2. Report pass/fail for each check
3. If any fail, investigate and report the issue
4. Update tasks/lessons.md with any new patterns discovered

CONSTRAINTS: Read-only verification. Do NOT modify code.
```
