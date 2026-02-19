# S-51: Fix Disconnected s42 Migration Chain
**Epic:** E9 — Database Integration | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem

`src/api/alembic/versions/s42_add_fk_constraints.py` has `down_revision = None` (line 11),
making it a disconnected migration branch. The main chain is:
`s49 (baseline) → s37 → s44 → s46 → s47 → s48`

The s42 migration adds FK constraints to `knowledge_relations`, `model_usage`, `social_posts`,
and fixes `working_memory.updated_at`. Running `alembic upgrade head` may skip s42 entirely
because it's on a separate branch with no dependents.

## Root Cause

`s42_add_fk_constraints.py` line 11:
```python
down_revision = None  # Should point to a revision in the main chain
```

This creates two heads in Alembic's revision graph. The s42 migration should logically run
AFTER the baseline tables exist (s49) and BEFORE the orphan cleanup (s37), or between s37
and s44.

## Fix

**File:** `src/api/alembic/versions/s42_add_fk_constraints.py`

BEFORE (line 11):
```python
down_revision = None
```

AFTER:
```python
down_revision = "s37_drop_orphans"
```

Also update s44 to depend on s42:

**File:** `src/api/alembic/versions/s44_add_gin_indexes.py`

BEFORE:
```python
down_revision = "s37_drop_orphans"
```

AFTER:
```python
down_revision = "s42_add_fk"
```

New chain: `s49 → s37 → s42 → s44 → s46 → s47 → s48`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Migration only touches DB layer |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model names involved |
| 4 | Docker-first testing | ✅ | Must verify migration chain via Docker |
| 5 | aria_memories only writable path | ❌ | Code file, not runtime write |
| 6 | No soul modification | ❌ | No soul files involved |

## Dependencies
- S-50 must complete first — s42 now chains after s37, which chains after s49 (baseline).

## Verification
```bash
# 1. Chain is linear (single head):
cd src/api && python -m alembic heads
# EXPECTED: exactly 1 head (s48_add_aria_engine_tables)

# 2. Full chain shows 7 revisions:
cd src/api && python -m alembic history
# EXPECTED: s49 → s37 → s42 → s44 → s46 → s47 → s48

# 3. Upgrade succeeds:
cd src/api && python -m alembic upgrade head
# EXPECTED: no errors

# 4. FK constraints exist:
docker compose exec aria-db psql -U aria_admin -d aria -c "
  SELECT conname FROM pg_constraint WHERE conname LIKE 'fk_%';"
# EXPECTED: fk_kr_from_entity, fk_kr_to_entity, fk_mu_session, fk_sp_reply_to
```

## Prompt for Agent
Read these files first:
- `src/api/alembic/versions/s42_add_fk_constraints.py` (full file — 50 lines)
- `src/api/alembic/versions/s37_drop_orphan_tables.py` (full file — 28 lines)
- `src/api/alembic/versions/s44_add_gin_indexes.py` (first 20 lines — for down_revision)

Steps:
1. Edit `s42_add_fk_constraints.py`: change `down_revision = None` to `down_revision = "s37_drop_orphans"`
2. Edit `s44_add_gin_indexes.py`: change `down_revision = "s37_drop_orphans"` to `down_revision = "s42_add_fk"`
3. Run `alembic heads` to verify single head
4. Run `alembic history` to verify linear chain

Constraints: #1 (DB layer only), #4 (Docker test)
