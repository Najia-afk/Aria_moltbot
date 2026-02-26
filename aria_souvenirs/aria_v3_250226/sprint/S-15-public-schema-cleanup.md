# S-15: Drop Public Schema Duplicate Tables
**Epic:** E9 — Schema Cleanup | **Priority:** P2 | **Points:** 2 | **Phase:** 3

## Problem
The `public` schema contains duplicate/stale copies of tables that properly live in `aria_data` or `aria_engine`. Production DB audit showed tables exist in both `public` and their correct schema. These duplicates:
- Confuse new developers
- Risk accidental writes to wrong schema
- Waste storage (minor)
- Make `pg_dump` larger than necessary

## Root Cause
Tables were originally created in `public` (PostgreSQL default). When `aria_data` and `aria_engine` schemas were introduced, tables were copied/migrated but `public` copies were not dropped.

## Fix

### Fix 1: Identify duplicate tables
**Method:** Compare table names across schemas
```sql
-- Conceptual query (run via monitoring endpoint or pgAdmin, not in app code)
SELECT t1.table_name, t1.table_schema AS schema1, t2.table_schema AS schema2
FROM information_schema.tables t1
JOIN information_schema.tables t2 ON t1.table_name = t2.table_name
WHERE t1.table_schema = 'public'
  AND t2.table_schema IN ('aria_data', 'aria_engine')
ORDER BY t1.table_name;
```

### Fix 2: Verify S-14 is complete
**BLOCKER:** Do NOT proceed until S-14 confirms all ORM models use explicit schema declarations. If any model still defaults to `public`, dropping public tables will break the app.

### Fix 3: Create migration to drop public duplicates
**Via:** ORM migration (Constraint #1)

For each confirmed duplicate:
```python
# In migration file
op.execute("DROP TABLE IF EXISTS public.sessions CASCADE")
op.execute("DROP TABLE IF EXISTS public.messages CASCADE")
# ... etc
```

**IMPORTANT:** Use `IF EXISTS` and `CASCADE` for safety.

### Fix 4: Verify no foreign key references to public
Before dropping, check:
```sql
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE confrelid::regclass::text LIKE 'public.%';
```
If any FK points to a public table, update it to point to the schema-qualified table first.

### Fix 5: Create rollback script
**File:** `scripts/rollback_public_schema_drop.sql`
Before dropping, dump the public schema tables:
```bash
pg_dump -n public aria_warehouse > scripts/rollback_public_schema_drop.sql
```
This allows restoring public tables if something breaks.

### Fix 6: Keep essential public tables
Some tables MUST stay in public:
- `alembic_version` — migration tracking (Alembic default)
- `spatial_ref_sys` — PostGIS extension table (if exists)
- Any extension-managed tables

Do NOT drop these.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Migration via ORM, not ad-hoc SQL |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | Test full app cycle after drop |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

**Safety:** This is a destructive operation. Must have:
1. DB backup (done in sprint prep — `/aria_vault/backup_250226/`)
2. S-14 verified complete
3. Rollback script created before execution

## Dependencies
- **HARD BLOCKER:** S-14 (schema-qualified queries) must be complete and verified
- DB backup must exist (already done: `~/aria_vault/backup_250226/aria_db_full_250226.sql`)

## Verification
```bash
# 1. Verify public schema has minimal tables:
curl -s http://localhost:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query": "{ databaseInfo { schemas { name tableCount } } }"}'
# EXPECTED: public.tableCount ≤ 3 (alembic_version + extensions only)

# 2. Verify app still works after drop:
curl -s http://localhost:5050/dashboard
# EXPECTED: 200 with data

# 3. Verify session creation still works:
curl -X POST http://localhost:8000/engine/chat/sessions -H 'Content-Type: application/json' -d '{}'
# EXPECTED: 200 — session created in aria_engine.sessions

# 4. Verify rollback script exists:
test -f scripts/rollback_public_schema_drop.sql && echo "OK"

# 5. Count total tables (should be reduced):
# Before: 89 tables
# After: ~65-70 tables (duplicates removed)
```

## Prompt for Agent
```
BEFORE STARTING: Verify that S-14 is complete by running scripts/verify_schema_refs.py.
If S-14 is NOT complete, STOP and report.

Read these files FIRST:
- scripts/verify_schema_refs.py (run it — must pass)
- src/api/ — find migration configuration (Alembic or equivalent)

CONSTRAINTS: #1 (migration via ORM framework), backup before destructive ops.

STEPS:
1. Run verify_schema_refs.py — MUST pass
2. Connect to DB (via API/monitoring endpoint) and list duplicate tables across schemas
3. Create rollback script: dump public schema to scripts/rollback_public_schema_drop.sql
4. Identify which public tables are extension-managed (keep those)
5. Check for FK references to public tables — fix any found
6. Create ORM migration to DROP public duplicates (with IF EXISTS CASCADE)
7. Run migration
8. Run FULL app test: create session, send message, check dashboard
9. Verify tables are gone
10. Run verification commands
```
