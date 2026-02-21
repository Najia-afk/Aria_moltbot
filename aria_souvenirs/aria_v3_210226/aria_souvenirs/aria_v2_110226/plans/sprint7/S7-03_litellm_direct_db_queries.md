# S7-03: LiteLLM Direct Database Queries (DONE)

## Summary
The LiteLLM HTTP proxy approach (`httpx → litellm:4000/spend/logs`) fetches ALL 15K+ rows regardless of `limit` param, causing OOM kills (exit code 137) and 5s timeouts. Both `/litellm/spend` and `/litellm/global-spend` returned empty data. Fix: query the `litellm` PostgreSQL database directly — same PG instance, just different database name.

**Data:** 15,442 spend logs in LiteLLM DB, all now accessible instantly.

## Priority / Points
- **Priority**: P0-Critical
- **Story Points**: 5
- **Sprint**: 7 — Dashboard Data Fixes

## Status: ✅ COMPLETED
Implemented ahead of ticket creation. All changes verified.

## What Was Done
1. **db/session.py**: Added `_litellm_url_from()` to derive `litellm` DB URL from `DATABASE_URL` (same host/creds, different DB name). Created `litellm_engine` (pool_size=3) and `LiteLLMSessionLocal`.
2. **deps.py**: Added `get_litellm_db()` FastAPI dependency for litellm database sessions.
3. **routers/litellm.py**: Rewrote `/spend` and `/global-spend` to use direct SQL queries (`SELECT ... FROM "LiteLLM_SpendLogs"`) with proper `LIMIT/OFFSET`. Kept `/models` and `/health` as HTTP proxy (lightweight).
4. **routers/model_usage.py**: Rewrote `_fetch_litellm_spend_logs()` to query DB directly. Added `_litellm_aggregate_stats()` and `_litellm_by_model_stats()` for server-side aggregation. Removed `httpx` import entirely.

## Files Modified
| File | Change |
|------|--------|
| src/api/db/session.py | Added litellm_engine, LiteLLMSessionLocal |
| src/api/db/__init__.py | Exported new symbols |
| src/api/deps.py | Added get_litellm_db() dependency |
| src/api/routers/litellm.py | Direct DB queries for /spend and /global-spend |
| src/api/routers/model_usage.py | Direct DB queries, server-side aggregation |

## Verification (All Passing)
```
/litellm/spend?limit=5 → 5 logs + total: 15,442
/litellm/global-spend → spend: 0.009, total_tokens: 360M, api_requests: 15,442
/model-usage/stats → total_requests: 3,625 (24h), by_model: kimi, trinity-free, etc.
/model-usage?limit=3 → paginated logs with source: "litellm"
```

## Dependencies
- None (already deployed and tested)
