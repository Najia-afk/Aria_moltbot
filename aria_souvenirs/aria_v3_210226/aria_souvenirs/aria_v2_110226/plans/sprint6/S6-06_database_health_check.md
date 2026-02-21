# S6-06: Add Database Health Check & Missing Table Detection

## Summary
The API currently crashes silently when tables are missing — causing server disconnects that are hard to diagnose. Add a startup health check that compares ORM model tables against what actually exists in PostgreSQL, logging any discrepancies. Also add a `/health/db` endpoint for runtime diagnostics.

## Priority / Points
- **Priority**: P2-Medium
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] On API startup: log list of expected tables vs actual tables, WARN on any missing
- [ ] New GET /health/db endpoint returns: `{"status": "ok|degraded", "tables": {"working_memory": true, "rate_limits": true, ...}, "missing": [], "pgvector_installed": true}`
- [ ] If any tables are missing, API still starts (log warnings, don't crash)
- [ ] Health endpoint accessible without authentication
- [ ] Docker health check updated to use /health/db

## Technical Details
- Query `pg_catalog.pg_tables` to get list of existing tables in schema
- Compare against `Base.metadata.sorted_tables`
- Check pgvector extension via: `SELECT * FROM pg_extension WHERE extname = 'vector'`
- Add to existing /status or create new /health/db router

## Files to Modify
| File | Change |
|------|--------|
| src/api/db/session.py | add table presence check on startup |
| src/api/routers/ | new health router or extend existing status endpoint |
| stacks/brain/docker-compose.yml | update healthcheck command |

## Constraints Checklist
| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | 5-layer | ✅ | - |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | - | - |
| 4 | Docker-first | ✅ | Docker rebuild |
| 5 | aria_memories only | - | - |
| 6 | No soul edit | ❌ | Untouched |

## Dependencies
- S6-01 (pgvector fix)
