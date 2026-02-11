# S6-01: Install pgvector & Fix ensure_schema() Table Creation

## Summary
The `ensure_schema()` function in `src/api/db/session.py` runs `CREATE TABLE IF NOT EXISTS` for all models at startup. When it hits the `SemanticMemory` model (which uses `Vector(768)` from pgvector), it fails and aborts — leaving ALL subsequent tables uncreated (working_memory, rate_limits, api_key_rotations, etc.). This single fix unblocks 12 broken endpoints.

## Priority / Points
- **Priority**: P0-Critical
- **Story Points**: 5
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] pgvector extension installed in PostgreSQL container (`CREATE EXTENSION IF NOT EXISTS vector`)
- [ ] ensure_schema() handles table creation errors per-table (wrap each CREATE TABLE in try/except, log failures, continue)
- [ ] All tables verified present: working_memory, rate_limits, api_key_rotations, model_usage, heartbeat_log, semantic_memories
- [ ] All 12 previously-disconnecting endpoints return valid responses
- [ ] Alembic migration added for pgvector extension

## Technical Details
- Add `CREATE EXTENSION IF NOT EXISTS vector` to ensure_schema() BEFORE table creation loop
- Wrap each table creation in individual try/except so one failure doesn't cascade
- Add a startup health check that logs which tables exist vs which should exist
- Update Dockerfile to install pgvector extension in PostgreSQL or add to docker-compose postgres image

## Files to Modify
| File | Change |
|------|--------|
| src/api/db/session.py | add pgvector extension, per-table error handling |
| stacks/brain/docker-compose.yml (or similar) | ensure postgres image supports pgvector (use pgvector/pgvector:pg16) |
| src/api/alembic/versions/ | new migration for pgvector extension + verify all tables |

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
- None (must be done first, unblocks S6-02 through S6-04)
