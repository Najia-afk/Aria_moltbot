# S7-05: Sprint Board NULL Fix + Goals Auto-Refresh

## Summary
Two related goals issues:
1. **Sprint Board**: SQL `IN` clause doesn't match `NULL` sprint values. If any goals have `sprint=NULL`, they're invisible on the board. Current data: 52 backlog, 1 doing — works now but fragile.
2. **Goals auto-refresh**: No `setInterval` — page only loads on initial `DOMContentLoaded` and manual refresh button click. Should poll every 30s.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 3
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] Sprint board query includes `OR sprint IS NULL` to catch unassigned goals
- [ ] NULL sprint goals appear in "Backlog" column by default
- [ ] Goals page auto-refreshes every 30 seconds
- [ ] Manual refresh button still works

## Technical Details

### Issue 1: NULL sprint in SQL IN (goals.py ~line 130)
```python
# Current (fragile):
stmt = stmt.where(Goal.sprint.in_([sprint, "backlog"]))

# Fixed:
from sqlalchemy import or_
stmt = stmt.where(or_(Goal.sprint.in_([sprint, "backlog"]), Goal.sprint.is_(None)))
```

### Issue 2: Goals auto-refresh (goals.html ~line 1395)
```javascript
// After DOMContentLoaded handler, add:
setInterval(() => loadGoals(), 30000);
```

## Files to Modify
| File | Change |
|------|--------|
| src/api/routers/goals.py | Add `or_(Goal.sprint.is_(None))` to board query |
| src/web/templates/goals.html | Add setInterval for 30s auto-refresh |

## Verification
```bash
# Insert a goal with NULL sprint:
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "INSERT INTO goals (id, goal_id, title, status, priority) VALUES (gen_random_uuid(), 'test-null', 'NULL Sprint Test', 'active', 3)"
# Then verify it shows up on sprint board:
curl -s 'http://localhost:8000/goals/board?sprint=sprint-7' | python3 -m json.tool | grep 'NULL Sprint'
# Clean up:
docker exec aria-db psql -U aria_admin -d aria_warehouse -c "DELETE FROM goals WHERE goal_id = 'test-null'"
```

## Dependencies
- S7-01 (DOMContentLoaded fix for goals.html)
