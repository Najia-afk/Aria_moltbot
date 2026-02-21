# S7-10: Full Dashboard Page Verification

## Summary
Final verification pass — load every dashboard page and confirm data displays correctly. This is the Sprint 7 acceptance gate.

## Priority / Points
- **Priority**: P0-Critical
- **Story Points**: 3
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] Dashboard: activity timeline shows 7 days, thoughts chart readable
- [ ] Thoughts page: displays 67+ thoughts with pagination
- [ ] Memories page: displays 31+ memories
- [ ] Goals page: displays 53+ goals, auto-refreshes
- [ ] Sprint Board: shows goals in columns, NULL sprints in Backlog
- [ ] Working Memory: displays 5 items, no "Failed to load" error
- [ ] Skills page: shows available skills (not empty)
- [ ] Social page: displays 19+ posts
- [ ] Models page: shows spend data (15K+ logs via direct DB)
- [ ] Model Usage page: shows usage logs with source: litellm
- [ ] Operations page: shows global spend stats
- [ ] Sessions page: shows 3,500+ sessions
- [ ] Performance page: shows health data
- [ ] No 4xx/5xx errors in API logs during page loads

## Verification Script
```bash
#!/bin/bash
echo "=== Sprint 7 Page Verification ==="
endpoints=(
    "/thoughts?limit=3"
    "/memories?limit=3"
    "/social?limit=3"
    "/goals?limit=3"
    "/goals/board?sprint=backlog"
    "/working-memory"
    "/skills"
    "/litellm/spend?limit=3"
    "/litellm/global-spend"
    "/model-usage?limit=3"
    "/model-usage/stats"
    "/sessions?limit=3"
    "/activities/timeline?days=7"
)
for ep in "${endpoints[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000${ep}")
    echo "${status} ${ep}"
done
```

## Dependencies
- All S7-01 through S7-09 completed
