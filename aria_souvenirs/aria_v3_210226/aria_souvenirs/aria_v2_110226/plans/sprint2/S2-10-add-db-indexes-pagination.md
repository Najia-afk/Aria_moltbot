# S2-10: Add SQLAlchemy Indexes for Pagination Performance
**Epic:** E2 — Pagination | **Priority:** P2 | **Points:** 2 | **Phase:** 1

## Problem
Pagination with OFFSET requires efficient sorting. Current indexes on some tables are insufficient for paginated queries:
- `activities` has no index on `created_at` (paginated ORDER BY created_at DESC will sequential scan)
- `social_posts` has no index on `created_at`
- `security_events` has no index on `created_at`
- `model_usage` has no index on `created_at`
- `working_memory` has no composite index for the weighted context query

## Root Cause
Indexes were added ad-hoc. A systematic pass for pagination-friendly indexes hasn't been done.

## Fix

### File: `src/api/db/models.py`
Add indexes to models that will be paginated. Check each model — only add if missing.

Models to verify/add indexes:
1. **ActivityLog**: Add `idx_activities_created` on `created_at DESC`
2. **SocialPost**: Add `idx_social_created` on `created_at DESC`  
3. **SecurityEvent**: Add `idx_security_created` on `created_at DESC`
4. **ModelUsage**: Add `idx_model_usage_created` on `created_at DESC`
5. **WorkingMemory**: Add `idx_wm_importance_created` composite on `(importance DESC, created_at DESC)` for context queries

### Alembic Migration
Create migration: `alembic revision --autogenerate -m "add_pagination_indexes"`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | DB layer change (correct) |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No models |
| 4 | Docker-first | ✅ | Run migration in Docker |
| 5 | aria_memories writable | ❌ | DB changes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- S2-06 should complete first so we know which queries need indexes.

## Verification
```bash
# 1. Verify indexes in models.py:
grep -c 'Index(' src/api/db/models.py
# EXPECTED: increased count

# 2. Run migration:
cd src/api && alembic upgrade head

# 3. Verify indexes exist in PostgreSQL:
docker compose exec aria-db psql -U aria -d aria_brain -c "\di" | grep -E 'activities|social|security|model_usage|working_memory'
# EXPECTED: New indexes visible

# 4. Run tests:
cd src/api && python -m pytest -x -q
```

## Prompt for Agent
```
You are adding database indexes for pagination performance.

FILES TO READ FIRST:
- src/api/db/models.py (check existing indexes with grep 'Index(')
- src/api/alembic/ (migration setup)

STEPS:
1. Read models.py and list all existing indexes
2. For each model that will be paginated, verify index on created_at exists
3. Add missing indexes (DO NOT duplicate existing ones)
4. Create alembic migration
5. Run verification commands

CONSTRAINTS: DB layer only. Check for duplicate indexes before adding.
```
