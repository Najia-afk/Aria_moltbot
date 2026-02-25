# S-21: Health Endpoint DB Check & Alembic as Single Migration Source
**Epic:** E11 — API Quality | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
### Problem A: /health lies about database connectivity
`src/api/routers/health.py` L40-48 always returns `database: "connected"` without actually checking:
```python
return HealthResponse(
    status="healthy",
    database="connected",  # HARDCODED — never actually checked
)
```
Docker healthchecks and load balancers trust this endpoint. If the DB goes down, /health still says "healthy" → new requests routed to a broken instance.

### Problem B: Three competing schema management mechanisms
1. **Raw SQL init scripts:** `stacks/brain/init-scripts/01-schema.sql` (503 lines), `03-aria-engine-schema.sql`
2. **ORM create_all:** `src/api/db/session.py` calls `Base.metadata.create_all()` — auto-creates any model not yet in DB
3. **Alembic:** Only 2 migrations exist (`s49_baseline`, `s50_add_embedding`), and `alembic.ini` has a blank DB URL

Schema changes go through ad-hoc SQL, never through proper versioned migrations. The first migration `s49_baseline_all_tables.py` L28-57 uses bare `except Exception: pass` that eats errors.

## Fix

### Fix 1: Real DB check in /health
**File:** `src/api/routers/health.py` L40-48
```python
@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": db_status}
        )
    return HealthResponse(status="healthy", database=db_status, ...)
```

### Fix 2: Configure alembic.ini from environment
**File:** `src/api/alembic.ini`
Set `sqlalchemy.url` to empty and use `env.py` to read from environment:
```python
# src/api/alembic/env.py
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```

### Fix 3: Disable auto-create in production
**File:** `src/api/db/session.py`
```python
if os.environ.get("ENGINE_DEBUG", "").lower() == "true":
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```
In production, schema changes MUST go through Alembic.

### Fix 4: Generate comprehensive baseline migration
```bash
cd src/api
alembic revision --autogenerate -m "s51_full_baseline_from_orm"
```
This captures all ORM models as a single migration. Replace the existing `s49_baseline` which has the broken `except: pass`.

### Fix 5: Fix existing migration error handling
**File:** `src/api/alembic/versions/s49_baseline_all_tables.py` L28-57
Replace `except Exception: pass` with proper logging:
```python
except Exception as e:
    logger.warning(f"Table may already exist: {e}")
```

### Fix 6: Document migration workflow
Add to CONTRIBUTING.md:
```markdown
## Database Migrations
1. Make changes to ORM models in src/api/db/models.py
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Review generated migration in src/api/alembic/versions/
4. Apply: `alembic upgrade head`
5. NEVER use raw SQL or Base.metadata.create_all() in production
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | DB access via ORM, migrations via Alembic |
| 2 | .env for secrets | ✅ | DATABASE_URL from env |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-14 (schema-qualified queries) — Alembic must use correct schemas.

## Verification
```bash
# 1. /health returns 503 when DB is down:
docker compose stop aria-db
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# EXPECTED: 503
docker compose start aria-db

# 2. /health returns 200 when DB is up:
curl -s http://localhost:8000/health | python -m json.tool
# EXPECTED: {"status": "healthy", "database": "connected"}

# 3. Alembic works:
cd src/api && alembic current
# EXPECTED: Shows current revision

# 4. Auto-create disabled in production:
grep -n 'create_all' src/api/db/session.py
# EXPECTED: Guarded by ENGINE_DEBUG check

# 5. alembic.ini uses env:
grep 'sqlalchemy.url' src/api/alembic.ini
# EXPECTED: Empty or commented out (loaded from env.py)
```

## Prompt for Agent
```
Read these files FIRST:
- src/api/routers/health.py (full)
- src/api/db/session.py (full — find create_all)
- src/api/alembic.ini (full)
- src/api/alembic/env.py (full)
- src/api/alembic/versions/ — list and read existing migrations
- stacks/brain/init-scripts/01-schema.sql (first 50 lines)
- CONTRIBUTING.md (if exists)

CONSTRAINTS: #1 (ORM only), #2 (DATABASE_URL from env).

STEPS:
1. Fix /health to do actual SELECT 1 and return 503 on failure
2. Update alembic.ini: clear sqlalchemy.url
3. Update alembic/env.py: read DATABASE_URL from os.environ
4. Guard Base.metadata.create_all with ENGINE_DEBUG check
5. Fix s49_baseline migration error handling
6. Generate a clean s51 baseline migration from current ORM models
7. Document migration workflow in CONTRIBUTING.md
8. Verify /health with DB up and down
9. Run alembic upgrade head and verify
10. Do NOT delete init-scripts — they're used for Docker first-run initialization
```
