# S3-10: Sprint 3 Verification & Integration Testing
**Epic:** E7 — QA | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
All Sprint 3 tickets must be verified as a complete unit.

## Root Cause
N/A — verification ticket.

## Fix
No code changes. Run comprehensive verification.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Verify sprint_manager uses api_client |
| 2 | .env | ✅ | Verify no secrets leaked |
| 3 | models.yaml | ✅ | Verify no hardcoded models |
| 4 | Docker-first | ✅ | All tests in Docker |
| 5 | aria_memories | ✅ | Verify writes thru API |
| 6 | No soul mod | ✅ | Verify soul untouched |

## Dependencies
ALL Sprint 3 tickets must complete first.

## Verification
```bash
# DB Model
docker compose exec aria-db psql -U aria -d aria_brain -c "\d goals" | grep -E 'sprint|board_column'
# Board API
curl -s http://localhost:8000/api/goals/board | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Board: {d[\"counts\"]}')"
# Sprint summary token-efficient
curl -s http://localhost:8000/api/goals/sprint-summary | wc -c
# PO Skill loads
python3 -c "from aria_skills.sprint_manager import SprintManagerSkill; print('OK')"
# Sprint board page
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/sprint-board
# Architecture: sprint_manager no SQLAlchemy
grep -rn 'sqlalchemy\|from db' aria_skills/sprint_manager/
# EXPECTED: 0 results
# Soul untouched
git diff --name-only HEAD -- aria_mind/soul/ aria_mind/SOUL.md
# EXPECTED: empty
echo "Sprint 3 Verification Complete"
```

## Prompt for Agent
```
Run Sprint 3 integration tests. Run ALL verification commands. Report pass/fail.
CONSTRAINTS: Read-only. Do NOT modify code. Update tasks/lessons.md.
```
