# S6-10: Verification Pass — Full Endpoint Health Check

## Summary
Final verification ticket. Run all 83 endpoints, confirm all previously-broken ones now work. Update the endpoint audit report. Rebuild Docker, run smoke tests, verify every frontend page loads without errors.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] All 83 endpoints tested — document pass/fail for each
- [ ] All 18 previously-broken endpoints now return valid responses (200/201/400, NOT 500/502/503/disconnect)
- [ ] All frontend pages load without "Loading..." stuck states or silent errors
- [ ] Error states show correctly when an external service (LiteLLM) is intentionally stopped
- [ ] Docker build succeeds on clean build
- [ ] No console errors in browser DevTools on any page
- [ ] Sprint board drag-and-drop works end-to-end
- [ ] Working memory CRUD works in frontend
- [ ] Performance: no endpoint takes longer than 5 seconds to respond

## Technical Details
- Use curl/httpx to test all endpoints systematically
- Test with LiteLLM running AND with it stopped (verify graceful degradation)
- Check browser console on every page for JS errors
- Verify auto-refresh doesn't spam errors when services are down
- Document any remaining issues for future sprints

## Files to Modify
| File | Change |
|------|--------|
| None | verification only |
| SPRINT_MASTER_OVERVIEW.md | update if any issues found |

## Constraints Checklist
| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | 5-layer | ✅ | All constraints verified |
| 2 | .env secrets | ✅ | All constraints verified |
| 3 | models.yaml | ✅ | All constraints verified |
| 4 | Docker-first | ✅ | All constraints verified |
| 5 | aria_memories only | ✅ | All constraints verified |
| 6 | No soul edit | ✅ | All constraints verified |

## Dependencies
- S6-01 through S6-09
