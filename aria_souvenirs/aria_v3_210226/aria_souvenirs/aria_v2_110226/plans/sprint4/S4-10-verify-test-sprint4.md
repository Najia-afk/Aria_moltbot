# S4-10: Sprint 4 Verification & Integration Testing
**Epic:** E11 — QA | **Priority:** P0 | **Points:** 3 | **Phase:** 3

## Problem
All Sprint 4 tickets must be verified as a complete unit.

## Root Cause
N/A — verification ticket.

## Fix
No code changes.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Verify all new code complies |
| 2 | .env | ✅ | No secrets leaked |
| 3 | models.yaml | ✅ | No hardcoded models |
| 4 | Docker-first | ✅ | All tests in Docker |
| 5 | aria_memories | ✅ | Verify writable path only |
| 6 | No soul mod | ✅ | Soul untouched |

## Dependencies
ALL Sprint 4 tickets (S4-01 through S4-09) must complete first.

## Verification
```bash
# Knowledge Graph
curl -s http://localhost:8000/api/knowledge-graph/entities?type=skill | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Skill entities: {len(d.get(\"entities\",[]))}')"
# EXPECTED: 26 skills

# Pathfinding
curl -s 'http://localhost:8000/api/knowledge-graph/traverse?start_name=api_client&max_depth=1' | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Traverse: {d[\"node_count\"]} nodes')"

# Skill discovery
curl -s 'http://localhost:8000/api/knowledge-graph/skill-for-task?task=telegram' | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Candidates: {d[\"count\"]}')"

# Query logging
curl -s http://localhost:8000/api/knowledge-graph/query-log | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Logged queries: {len(d[\"queries\"])}')"

# Skill graph page
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/skill-graph
# EXPECTED: 200

# Architecture compliance
python scripts/check_architecture.py
# EXPECTED: 0 issues

# No new secrets:
grep -rn 'sk-\|AKIA' src/ aria_skills/ --include='*.py' | grep -v 'os.getenv\|os.environ\|.env'
# EXPECTED: 0

# Soul untouched:
git diff --name-only HEAD -- aria_mind/soul/ aria_mind/SOUL.md
# EXPECTED: empty

# Graph sync is idempotent:
curl -s -X POST http://localhost:8000/api/knowledge-graph/sync-skills
curl -s -X POST http://localhost:8000/api/knowledge-graph/sync-skills
# EXPECTED: same entity/relation counts both times

echo "Sprint 4 Verification Complete"
```

## Prompt for Agent
```
Run Sprint 4 integration tests. Execute ALL verification commands. Report pass/fail for each.
CONSTRAINTS: Read-only. Update tasks/lessons.md with new patterns.
```
