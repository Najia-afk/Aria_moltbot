# S-50: Alembic Baseline Migration for All 36 Tables
**Epic:** E9 — Database Integration | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem

Currently, Aria has 36 ORM tables defined in `src/api/db/models.py` but only 7 of them have
Alembic migrations (6 engine tables in s48, plus sentiment_events in s47). The remaining ~29
tables rely entirely on `ensure_schema()` in `src/api/db/session.py` (line 88) which uses
`CREATE TABLE IF NOT EXISTS` at runtime.

This means:
- A fresh install cannot use `alembic upgrade head` to get a working schema — it only gets
  the 7 migrated tables, then `ensure_schema()` creates the rest at runtime.
- Alembic's `current` revision doesn't reflect actual DB state.
- Column type changes or additions can't be tracked through Alembic for ~29 tables.
- Existing users upgrading from an older version have no migration path for structural changes.

## Root Cause

The project bootstraps schema via two competing mechanisms:
1. `ensure_schema()` in `src/api/db/session.py` (line 88-162) — runtime `CREATE TABLE IF NOT EXISTS`
2. Alembic migrations in `src/api/alembic/versions/` — only covers s37→s44→s46→s47→s48 chain

The s37 migration (`down_revision = None`) is the root of the chain but only drops orphan tables.
No migration creates the initial 29 tables — they're only created by `ensure_schema()`.

## Fix

Create a new Alembic migration `s49_baseline_all_tables.py` that:
1. Uses `CREATE TABLE IF NOT EXISTS` semantics (idempotent for existing DBs)
2. Creates all 36 tables with all columns, indexes, and constraints
3. Slots into the chain as the NEW root migration (`down_revision = None`)
4. Updates s37's `down_revision` to point to s49

**File:** `src/api/alembic/versions/s49_baseline_all_tables.py`

The migration should:
- Import all table definitions from `db.models.Base.metadata`
- Use `op.create_table()` with full column specs for each table
- Use `op.create_index()` for all indexes
- Include `IF NOT EXISTS` checks via `op.execute("CREATE TABLE IF NOT EXISTS ...")` fallback
- This ensures both fresh installs (table doesn't exist → created) and existing installs
  (table exists → skipped) work correctly

**Chain update:** `s37_drop_orphan_tables.py` line 11 change:
- BEFORE: `down_revision = None`
- AFTER: `down_revision = "s49_baseline_all_tables"`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Migration only touches DB layer |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from env — no secrets in migration |
| 3 | models.yaml single source of truth | ❌ | No model names involved |
| 4 | Docker-first testing | ✅ | Must test via `docker compose exec aria-db psql` |
| 5 | aria_memories only writable path | ❌ | Code file, not runtime write |
| 6 | No soul modification | ❌ | No soul files involved |

## Dependencies
- None — this is the foundation ticket.
- S-51 depends on this (fixes s42 chain after baseline exists).

## Verification
```bash
# 1. Migration file exists:
ls src/api/alembic/versions/s49_baseline_all_tables.py
# EXPECTED: file exists

# 2. Chain is correct:
grep -n "down_revision" src/api/alembic/versions/s49_baseline_all_tables.py
# EXPECTED: down_revision = None

grep -n "down_revision" src/api/alembic/versions/s37_drop_orphan_tables.py
# EXPECTED: down_revision = "s49_baseline_all_tables"

# 3. Alembic can generate the upgrade path:
cd src/api && python -m alembic history
# EXPECTED: Shows s49 → s37 → s44 → s46 → s47 → s48 chain

# 4. Migration is idempotent on existing DB:
cd src/api && python -m alembic upgrade head
# EXPECTED: No errors (tables already exist, IF NOT EXISTS used)

# 5. Fresh DB gets all tables:
docker compose exec aria-db psql -U aria_admin -d aria -c "\dt" | wc -l
# EXPECTED: 36+ rows (all ORM tables)
```

## Prompt for Agent
Read these files first:
- `src/api/db/models.py` (all 889 lines — every ORM model class)
- `src/api/db/session.py` lines 88-162 (ensure_schema function)
- `src/api/alembic/env.py` (full file — 73 lines)
- `src/api/alembic/versions/s37_drop_orphan_tables.py` (full file)
- `src/api/alembic/versions/s48_add_aria_engine_tables.py` (full file — reference for style)

Steps:
1. Read all 36 model classes from `db/models.py` and extract table definitions
2. Create `src/api/alembic/versions/s49_baseline_all_tables.py` with:
   - `revision = "s49_baseline_all_tables"`, `down_revision = None`
   - `upgrade()` that creates all 36 tables with `IF NOT EXISTS` semantics
   - `downgrade()` that drops all 36 tables in reverse dependency order
   - All indexes from model definitions
3. Update `s37_drop_orphan_tables.py` line 11: `down_revision = "s49_baseline_all_tables"`
4. Run verification commands

Constraints: #1 (DB layer only), #2 (no secrets), #4 (Docker test)
