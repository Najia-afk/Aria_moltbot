# S3-04: Consolidate renderGoalCard Between Sprint Board and Goals
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P1 | **Points:** 3 | **Phase:** 3

## Problem
`renderGoalCard` is defined in both `sprint_board.html` and `goals.html`. These two pages share the same goal card rendering logic but may have drifted out of sync.

## Root Cause
The sprint board was created in Sprint 3 (S3-03) as a Kanban view for goals, reusing the goal card rendering from the goals page. The function was copy-pasted rather than extracted.

## Fix
Extract `renderGoalCard` into `src/web/static/js/goals-common.js`:

1. Compare both implementations to find the canonical version
2. Merge any unique features from each version
3. Create `goals-common.js` with the merged function
4. Update both templates to use the shared version
5. Add `<script src="/static/js/goals-common.js"></script>` to both

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Verify both pages work |
| 5 | aria_memories writable | ❌ | Code changes |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S3-01 (utils.js extraction) should complete first.

## Verification
```bash
# 1. goals-common.js exists:
ls -la src/web/static/js/goals-common.js
# EXPECTED: file exists

# 2. No duplicate renderGoalCard:
python3 scripts/check_architecture.py 2>&1 | grep "DUP_JS.*renderGoalCard"
# EXPECTED: no output

# 3. Both pages include shared file:
grep "goals-common.js" src/web/templates/goals.html src/web/templates/sprint_board.html
# EXPECTED: both include it

# 4. Both pages load:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/goals && echo " /goals"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/sprint-board && echo " /sprint-board"
# EXPECTED: 200 200
```

## Prompt for Agent
```
Consolidate renderGoalCard into a shared goals-common.js file.

**Files to read:**
- src/web/templates/goals.html (search for renderGoalCard — get full function)
- src/web/templates/sprint_board.html (search for renderGoalCard — get full function)

**Steps:**
1. Compare both renderGoalCard implementations
2. Create src/web/static/js/goals-common.js with the merged version
3. Remove inline definitions from both templates
4. Add script tag to both templates
5. Test both /goals and /sprint-board pages
```
