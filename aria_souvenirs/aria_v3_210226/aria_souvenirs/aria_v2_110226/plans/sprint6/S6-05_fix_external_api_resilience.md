# S6-05: Fix External API Resilience (providers/balances)

## Summary
GET /providers/balances makes sequential HTTP calls to Moonshot (api.moonshot.ai) and OpenRouter (openrouter.ai) APIs with 10-second timeouts each. When services are slow/unreachable, cumulative 20s latency triggers proxy disconnects. The calls should be parallelized and timeout-protected.

## Priority / Points
- **Priority**: P2-Medium
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] External API calls parallelized using asyncio.gather() with return_exceptions=True
- [ ] Individual timeout reduced to 5 seconds per provider
- [ ] Response includes partial data when one provider fails (e.g., Moonshot succeeds but OpenRouter fails → return Moonshot data + error for OpenRouter)
- [ ] Successful responses cached for 5 minutes (stale data better than no data for balance display)
- [ ] Each provider's status included in response: {"moonshot": {"status": "ok", "balance": 42.5}, "openrouter": {"status": "error", "error": "timeout"}}

## Technical Details
- Refactor providers.py to use asyncio.gather() for parallel fetches
- Add a simple in-memory cache (dict with TTL) for balance responses
- Return per-provider status so frontend can show partial data
- Add error detail field per provider so frontend knows what's wrong

## Files to Modify
| File | Change |
|------|--------|
| src/api/routers/providers.py | parallelize, cache, per-provider status |

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
