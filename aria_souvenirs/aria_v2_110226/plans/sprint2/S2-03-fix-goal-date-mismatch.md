# S2-03: Fix Goal target_date vs due_date Field Mismatch
**Epic:** E1 — Bug Fixes | **Priority:** P1 | **Points:** 2 | **Phase:** 1

## Problem
The Goal DB model (`src/api/db/models.py` line ~97) uses `due_date`. The API router (`src/api/routers/goals.py` line 47) accepts both `due_date` and `target_date` via `data.get("due_date") or data.get("target_date")`. But the frontend `goals.html` uses `target_date` for overdue detection in the stats section, while the API returns `due_date`. This means "Due Soon" count is always 0 on the frontend.

## Root Cause
Field name inconsistency across layers:
- **DB Model**: `due_date` (correct, canonical)
- **API create**: accepts both `due_date` and `target_date` (fallback)
- **API response**: returns `due_date` (via `to_dict()`)
- **Frontend**: references `target_date` for stats calculation
- **New Goal form**: sends `target_date` field name

The frontend looks for `goal.target_date` but the API returns `goal.due_date`, so overdue/due-soon logic never finds dates.

## Fix

### File: `src/web/templates/goals.html`
Find all references to `target_date` and change to `due_date`:

BEFORE (in stats calculation):
```javascript
goal.target_date
```
AFTER:
```javascript
goal.due_date
```

BEFORE (in goal card rendering):
```javascript
target_date
```
AFTER:
```javascript
due_date
```

BEFORE (in new goal form submission):
```javascript
target_date: document.getElementById('goalTargetDate').value
```
AFTER:
```javascript
due_date: document.getElementById('goalTargetDate').value
```

Also in the GraphQL types, `GoalType` already uses `due_date` which is correct.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Frontend must use the field name returned by API |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test via browser |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
None — standalone field name fix.

## Verification
```bash
# 1. Verify no remaining target_date references in goals.html (except the input label):
grep -c 'target_date' src/web/templates/goals.html
# EXPECTED: 0 or 1 (only the HTML label text, not JS field references)

# 2. Verify due_date is used in JS:
grep -c 'due_date' src/web/templates/goals.html
# EXPECTED: 3+ (stats calc, card render, form submit)

# 3. Test Due Soon count is non-zero (if goals with due dates exist):
curl -s http://localhost:8000/api/goals | python3 -c "
import sys,json
goals=json.load(sys.stdin)
with_dates=[g for g in goals if g.get('due_date')]
print(f'Goals with due_date: {len(with_dates)}')
"
```

## Prompt for Agent
```
You are fixing a field name mismatch between the Aria API and frontend.

FILES TO READ FIRST:
- src/api/db/models.py (Goal model — uses `due_date`)
- src/api/routers/goals.py (accepts both, returns `due_date`)
- src/web/templates/goals.html (uses `target_date` — BUG)

STEPS:
1. Read goals.html and find ALL references to `target_date` in JavaScript
2. Change them to `due_date` to match what the API returns
3. Keep the HTML label text as-is (user-facing label can say "Target Date")
4. Run verification commands

CONSTRAINTS: Frontend-only. Must match API response field names.
```
