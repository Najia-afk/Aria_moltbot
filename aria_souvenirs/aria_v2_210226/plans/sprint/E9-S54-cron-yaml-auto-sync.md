# S-54: Cron Jobs YAML Auto-Sync on Startup
**Epic:** E9 — Database Integration | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem

Cron jobs are defined in `aria_mind/cron_jobs.yaml` (15 jobs) and stored in the
`engine_cron_jobs` DB table. There is **no automatic sync** between YAML and DB.
The current workflow requires manually running `python scripts/migrate_cron_jobs.py`
after editing the YAML file.

This means:
- If someone edits `cron_jobs.yaml` and deploys, the scheduler uses stale DB data
- New installs get an empty `engine_cron_jobs` table with no pre-seeded jobs
- The YAML is the source of truth for definitions but the DB is the runtime store — gap

Additionally, there is a **legacy `scheduled_jobs` table** alongside the new
`engine_cron_jobs` table, creating confusion about which system is active.

## Root Cause

`aria_engine/scheduler.py` reads jobs **only from DB** on startup. The migration script
`scripts/migrate_cron_jobs.py` is a one-time manual tool. There is no startup hook that
syncs YAML → DB automatically.

The lifespan handler in `src/api/main.py` (lines 38-87) does not call any cron job sync.

## Fix

### Change 1: Create auto-sync function

**File:** `src/api/cron_sync.py` (new file)

Create a function `sync_cron_jobs_from_yaml()` that:
1. Reads `aria_mind/cron_jobs.yaml` (or configurable path via env var `CRON_JOBS_YAML`)
2. For each job in YAML:
   - If job ID doesn't exist in DB → INSERT with YAML values
   - If job ID exists but schedule/payload changed → UPDATE schedule/payload only
     (preserve runtime state: last_run_at, run_count, success_count, fail_count)
   - If job exists and matches → skip (no-op)
3. Returns a summary: `{inserted: N, updated: N, unchanged: N}`
4. Does NOT delete DB jobs missing from YAML (manual cleanup only)

### Change 2: Call sync in lifespan

**File:** `src/api/main.py`, in the lifespan handler, after `ensure_schema()`:

```python
    # Auto-sync cron jobs from YAML → DB
    try:
        from cron_sync import sync_cron_jobs_from_yaml
        cron_summary = await sync_cron_jobs_from_yaml()
        print(f"✅ Cron jobs synced: {cron_summary}")
    except Exception as e:
        print(f"⚠️  Cron job sync failed (non-fatal): {e}")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Sync uses ORM (EngineCronJob model), not raw SQL |
| 2 | .env for secrets (zero in code) | ✅ | CRON_JOBS_YAML path from env, no secrets in code |
| 3 | models.yaml single source of truth | ❌ | No model names involved |
| 4 | Docker-first testing | ✅ | Must work in Docker — YAML path must be correct in container |
| 5 | aria_memories only writable path | ❌ | Writes to DB, not filesystem |
| 6 | No soul modification | ❌ | No soul files involved |

## Dependencies
- None — can be executed independently.
- Benefits from S-50 (Alembic baseline includes `engine_cron_jobs` table).

## Verification
```bash
# 1. Sync module exists:
python -c "from cron_sync import sync_cron_jobs_from_yaml; print('OK')"
# EXPECTED: OK (from src/api/ directory)

# 2. YAML has jobs:
python -c "
import yaml
with open('aria_mind/cron_jobs.yaml') as f:
    jobs = yaml.safe_load(f)
print(f'{len(jobs)} jobs in YAML')
"
# EXPECTED: 15 jobs in YAML (or current count)

# 3. After startup, DB has jobs:
docker compose exec aria-db psql -U aria_admin -d aria -c "SELECT id, name, schedule FROM engine_cron_jobs ORDER BY id;"
# EXPECTED: 15+ rows matching YAML definitions

# 4. Idempotent — running again changes nothing:
# (restart API, check logs for "unchanged: 15" or similar)

# 5. Tests pass:
pytest tests/ -k "cron" -v
# EXPECTED: all cron-related tests pass
```

## Prompt for Agent
Read these files first:
- `aria_mind/cron_jobs.yaml` (full file)
- `scripts/migrate_cron_jobs.py` (full file — reference implementation)
- `src/api/db/models.py` lines 820-860 (EngineCronJob model)
- `aria_engine/scheduler.py` lines 1-50 (how scheduler reads jobs)
- `src/api/main.py` lines 36-87 (lifespan handler)

Steps:
1. Read existing `scripts/migrate_cron_jobs.py` to understand the mapping logic
2. Create `src/api/cron_sync.py` with an async `sync_cron_jobs_from_yaml()` function
3. Use SQLAlchemy ORM (not raw SQL) with `EngineCronJob` model
4. Add upsert logic: INSERT new jobs, UPDATE changed jobs, skip unchanged
5. Add the sync call to the lifespan handler in `main.py`
6. Run verification commands

Constraints: #1 (use ORM not raw SQL), #2 (paths from env), #4 (Docker test)
