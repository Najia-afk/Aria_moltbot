# S6-04: Frontend Error Handling for Broken Data Pages

## Summary
Eight frontend pages silently fail when API endpoints return errors. Pages show "-" or "Loading..." forever with no user feedback. The worst offenders are /sessions (overview tab perpetually loading) and /model-usage (entire page broken with no error message). All broken pages need visible error states, retry buttons, and timeout handling.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 5
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] sessions.html: Overview tab shows "Could not load stats" with Retry button when /sessions/stats fails
- [ ] model_usage.html: Shows error states with Retry buttons for both /model-usage/stats and /model-usage failures
- [ ] wallets.html: Individual wallet cards show "Error" instead of "--" when /providers/balances fails; spend section shows "Unavailable" with retry
- [ ] models.html: Consistent error states for balances/spend/global-spend sections (already has retry for balances, extend to others)
- [ ] All fetch() calls include AbortController with 15-second client-side timeout
- [ ] All fetch() calls check `response.ok` before processing (many currently only catch network errors)
- [ ] Auto-refresh uses exponential backoff on repeated failures (30s → 60s → 120s → stop)

## Technical Details
- Create a shared `fetchWithTimeout(url, options, timeout=15000)` wrapper in aria-common.js
- Create a shared `showErrorState(container, message, retryCallback)` helper
- Replace all `console.error()` silent failures with visible error states
- Add error boundary divs to each section that can flip between "loading", "loaded", "error" states
- For stat cards: show "N/A" or "Error" with red indicator instead of staying at "-"

## Files to Modify
| File | Change |
|------|--------|
| src/web/static/js/aria-common.js | add fetchWithTimeout, showErrorState helpers |
| src/web/templates/sessions.html | error states for overview/agent tabs |
| src/web/templates/model_usage.html | error states for all sections |
| src/web/templates/wallets.html | improved error states for wallet cards and spend |
| src/web/templates/models.html | extend error handling to spend/global-spend |

## Constraints Checklist
| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | 5-layer | - | - |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | - | - |
| 4 | Docker-first | ✅ | Docker rebuild |
| 5 | aria_memories only | - | - |
| 6 | No soul edit | ❌ | Untouched |

## Dependencies
- S6-01 and S6-02 fix the backend; this ticket makes frontend resilient regardless
