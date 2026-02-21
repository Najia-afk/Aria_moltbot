# S6-02: Fix LiteLLM Proxy Timeouts (5 endpoints)

## Summary
Five endpoints proxy HTTP calls to LiteLLM at http://litellm:4000 with excessive timeouts (10-30s). When LiteLLM is unreachable, these hang until timeout, then the reverse proxy (Traefik) disconnects the client. Affects: /sessions/stats, /litellm/spend, /litellm/global-spend, /model-usage, /model-usage/stats.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 5
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] All LiteLLM HTTP calls use max 5-second timeout (down from 10-30s)
- [ ] Each LiteLLM call wrapped in proper try/except returning graceful fallback (empty data, not crash)
- [ ] /sessions/stats returns DB-only stats when LiteLLM unavailable (LiteLLM spend fields = null)
- [ ] /model-usage and /model-usage/stats return DB data even when LiteLLM fetch fails
- [ ] /litellm/spend and /litellm/global-spend return explicit error JSON: {"error": "LiteLLM unreachable", "status": "unavailable"}

## Technical Details
- In sessions.py get_session_stats(): reduce httpx timeouts to 5s, ensure cumulative timeout < Traefik timeout
- In litellm.py: reduce spend timeout from 30s to 5s, global-spend from 10s to 5s
- In model_usage.py: reduce _fetch_litellm_spend_logs() timeout, ensure DB query runs regardless of LiteLLM status
- Add a shared `LITELLM_TIMEOUT = 5.0` constant in a config module

## Files to Modify
| File | Change |
|------|--------|
| src/api/routers/sessions.py | reduce timeouts, graceful LiteLLM fallback |
| src/api/routers/litellm.py | reduce timeouts in spend/global-spend |
| src/api/routers/model_usage.py | reduce timeout, separate DB from LiteLLM logic |
| src/api/routers/providers.py | parallelize external calls with asyncio.gather(), 5s timeout |

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
- None
