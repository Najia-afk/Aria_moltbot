````markdown
# S-51: Upgrade PostgreSQL pg16→pg17, pgvector 0.8.0→0.8.2, Fix Missing Python Package, Add HNSW Indexes
**Epic:** E20 — Infrastructure Hardening | **Priority:** P0 | **Points:** 3 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

> 🔴 **P0 — Semantic Memory Search Silently Broken**  
> The `pgvector` Python package is **absent from `pyproject.toml`**. Every fresh Docker build  
> sets `HAS_PGVECTOR = False` → ORM maps all `embedding` columns as JSONB → `cosine_distance()`  
> calls in `memories.py` crash at runtime. Additionally, no HNSW indexes exist on any  
> embedding column — every vector similarity search is a full sequential table scan.

---

## Problem

Three distinct bugs, all requiring this one ticket:

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `pyproject.toml` | dependencies | `pgvector` Python package **missing** — `HAS_PGVECTOR` is always `False` in Docker | 🔴 Silent crash |
| `stacks/brain/docker-compose.yml` | 4 | `pgvector/pgvector:0.8.0-pg16` — pgvector 2 patch versions behind, PostgreSQL one major version behind | ⚠️ Stale |
| `src/api/db/session.py` | ~629 | No HNSW index on `semantic_memories.embedding` — full sequential scan on every vector search | ⚠️ Perf bug |
| `src/api/db/session.py` | ~433 | No HNSW index on `session_messages.embedding` — same issue | ⚠️ Perf bug |

**Failure trace for Bug 1 (Python package missing):**
```python
# src/api/db/models.py line 26-30
try:
    from pgvector.sqlalchemy import Vector   # ← ImportError in Docker (not in pyproject.toml)
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False                     # ← always False in Docker

# models.py line 702
embedding: Mapped[Any] = mapped_column(
    Vector(768), nullable=False             # ← SKIPPED
) if HAS_PGVECTOR else mapped_column(
    JSONB, nullable=False                   # ← used instead — type mismatch with vector(768) DDL
)

# memories.py line 314 — crashes because SQLAlchemy thinks column is JSONB:
distance_col = SemanticMemory.embedding.cosine_distance(query_embedding).label("distance")
# AttributeError: 'JSONB' object has no attribute 'cosine_distance'
```

**Latest versions confirmed (Docker Hub, 2026-02-27):**

| Component | Current | Latest stable | Image |
|-----------|---------|--------------|-------|
| PostgreSQL | 16 | **17** (pg18-trixie is bleeding edge, skip) | — |
| pgvector extension | 0.8.0 | **0.8.2** (published ~20h ago) | `pgvector/pgvector:0.8.2-pg17` |
| pgvector Python pkg | missing | **0.3.6** | PyPI |

---

## Root Cause

| Bug | Root Cause |
|-----|-----------|
| `pgvector` missing from `pyproject.toml` | Added via `pip install` directly without updating project manifest — never committed |
| No HNSW indexes | Table DDL in `session.py` was written before HNSW support matured; indexes were never added after pgvector 0.5+ HNSW became stable |
| pg16 / pgvector 0.8.0 | Initial setup was correct at the time; no upgrade policy was enforced |

---

## Fix

### Fix 1 — Add `pgvector` Python package to `pyproject.toml`

**File:** `pyproject.toml`

```toml
# BEFORE (lines 22-39) — pgvector absent from dependencies
dependencies = [
    "httpx>=0.25.0",
    "asyncpg>=0.29.0",
    ...
    "fastapi>=0.115.0",
    "mcp>=1.0.0",
]

# AFTER — add pgvector
dependencies = [
    "httpx>=0.25.0",
    "asyncpg>=0.29.0",
    ...
    "fastapi>=0.115.0",
    "mcp>=1.0.0",
    "pgvector>=0.3.6",
]
```

### Fix 2 — Upgrade DB image in `stacks/brain/docker-compose.yml`

**File:** `stacks/brain/docker-compose.yml`

```yaml
# BEFORE (line 4)
    image: pgvector/pgvector:0.8.0-pg16

# AFTER
    image: pgvector/pgvector:0.8.2-pg17
```

> ⚠️ **PostgreSQL major version upgrade (pg16→pg17) requires a data migration.**  
> See Migration Path section below. For fresh clones (S-49 bootstrap), no migration needed.

### Fix 3 — Add HNSW indexes in `src/api/db/session.py`

**File:** `src/api/db/session.py` — in the `_create_tables()` function, after the `semantic_memories` DDL block.

```python
# BEFORE — no vector indexes after semantic_memories table creation (line ~629)
    _safe_execute("CREATE INDEX IF NOT EXISTS idx_semantic_created ON semantic_memories (created_at DESC)")

# AFTER — add HNSW indexes immediately after
    _safe_execute("CREATE INDEX IF NOT EXISTS idx_semantic_created ON semantic_memories (created_at DESC)")
    # HNSW index for cosine similarity search (pgvector 0.5+)
    # m=16 ef_construction=64 are defaults — good balance for Aria's memory sizes
    _safe_execute(
        "CREATE INDEX IF NOT EXISTS idx_semantic_embedding_hnsw "
        "ON semantic_memories USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
```

And after the `session_messages` embedding column handling:

```python
# AFTER session_messages HNSW index (find the idx_session_messages_session_created block)
    _safe_execute(
        "CREATE INDEX IF NOT EXISTS idx_session_messages_embedding_hnsw "
        "ON session_messages USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
```

### Fix 4 — New Alembic migration: HNSW indexes

**File:** `src/api/alembic/versions/s51_pg17_pgvector_hnsw_upgrade.py` (new file)

```python
"""s51 — pg17 / pgvector 0.8.2 upgrade: add HNSW indexes on embedding columns

Revision ID: s51_pg17_pgvector_hnsw
Revises: s50_add_embedding_agent_id_to_chat_messages
Create Date: 2026-02-27

Notes:
  - HNSW indexes were unavailable / immature when the tables were created.
  - This migration adds them idempotently using CREATE INDEX IF NOT EXISTS.
  - The pg16→pg17 image bump requires a separate data migration (see S-51 ticket).
  - pgvector extension version upgrade from 0.8.0 → 0.8.2 is automatic on container restart.
"""

from alembic import op

revision = "s51_pg17_pgvector_hnsw"
down_revision = "s50_add_embedding_agent_id_to_chat_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update pgvector extension to latest installed version
    op.execute("ALTER EXTENSION vector UPDATE")

    # HNSW cosine index — semantic_memories (768-dim embeddings)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_semantic_embedding_hnsw "
        "ON aria_data.semantic_memories USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # HNSW cosine index — session_messages (1536-dim embeddings, nullable)
    # Only created on rows where embedding IS NOT NULL
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_messages_embedding_hnsw "
        "ON aria_engine.session_messages USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS aria_data.idx_semantic_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS aria_engine.idx_session_messages_embedding_hnsw")
```

---

## Migration Path (pg16 → pg17)

PostgreSQL major versions cannot be upgraded by simply swapping the image tag — the data directory format changes. Two paths:

### Path A — Fresh clone (preferred for dev / new deployments)
No migration needed. `make up` after S-49 bootstrap will start pg17 clean.

### Path B — Existing deployment with data
```bash
set -a && source stacks/brain/.env && set +a

# 1. Dump all data from the running pg16 container
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  pg_dumpall -U ${DB_USER:-admin} > /tmp/aria_pg16_backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Stop the stack
docker compose -f stacks/brain/docker-compose.yml down aria-db

# 3. Remove the pg16 data volume (DESTRUCTIVE — backup must succeed first)
docker volume rm brain_aria_pg_data

# 4. Apply the image change (Fix 2) to docker-compose.yml, then start pg17
docker compose -f stacks/brain/docker-compose.yml up -d aria-db
sleep 10   # wait for pg17 to initialize

# 5. Restore the dump into pg17
cat /tmp/aria_pg16_backup_*.sql | docker compose -f stacks/brain/docker-compose.yml exec -T aria-db \
  psql -U ${DB_USER:-admin}

# 6. Restart full stack
docker compose -f stacks/brain/docker-compose.yml up -d
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Fixes in DB layer (docker-compose, session.py) + ORM layer (models.py via pyproject.toml) |
| 2 | `stacks/brain/.env` for all secrets/ports | ✅ | Verification uses `$ARIA_API_PORT`, `$DB_PORT`, `$DB_USER` |
| 3 | No direct SQL from skills or API | ✅ | HNSW DDL is in session.py infra layer only |
| 4 | No hardcoded ports | ✅ | All DB connections use `${DB_PORT:-5432}` |
| 5 | `aria_skills/` must stay compatible | ✅ | `cosine_distance()` ORM method unchanged in pgvector 0.8.x |
| 6 | No `:latest` image tags | ✅ | Pin to `pgvector/pgvector:0.8.2-pg17` |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `ARCHITECTURE.md` | ~156 | `PostgreSQL 16 + pgvector` | `PostgreSQL 17 + pgvector 0.8.2` |
| `DEPLOYMENT.md` | ~257 | `pgvector/pgvector:pg16` | `pgvector/pgvector:0.8.2-pg17` |
| `DEPLOYMENT.md` | ~258 | `browserless/chrome:2.18.0` | `ghcr.io/browserless/chromium:v2.42.0` _(also fixed by S-50 — coordinate to avoid conflict)_ |
| `DEPLOYMENT.md` | ~546 | `PostgreSQL 16 + pgvector — pgvector/pgvector:pg16` | `PostgreSQL 17 + pgvector 0.8.2 — pgvector/pgvector:0.8.2-pg17` |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. Docker image is the correct version
grep "pgvector" stacks/brain/docker-compose.yml | head -2
# EXPECTED: pgvector/pgvector:0.8.2-pg17

# 2. Python package is declared in pyproject.toml
grep "pgvector" pyproject.toml
# EXPECTED: "pgvector>=0.3.6",

# 3. Installed pgvector Python package version in Docker
docker compose -f stacks/brain/docker-compose.yml exec aria-api \
  pip show pgvector 2>/dev/null | grep Version
# EXPECTED: Version: 0.3.6 (or newer)

# 4. HAS_PGVECTOR is True at runtime
docker compose -f stacks/brain/docker-compose.yml exec aria-api \
  python3 -c "from pgvector.sqlalchemy import Vector; print('HAS_PGVECTOR: True')"
# EXPECTED: HAS_PGVECTOR: True

# 5. PostgreSQL version is 17
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} -c "SELECT version();" | grep "PostgreSQL 17"
# EXPECTED: PostgreSQL 17.x

# 6. pgvector extension version is 0.8.2
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} \
  -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
# EXPECTED: 0.8.2

# 7. HNSW index exists on semantic_memories
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} \
  -c "SELECT indexname, indexdef FROM pg_indexes WHERE indexname = 'idx_semantic_embedding_hnsw';"
# EXPECTED: 1 row — idx_semantic_embedding_hnsw ... USING hnsw ... vector_cosine_ops

# 8. HNSW index exists on session_messages
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} \
  -c "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_session_messages_embedding_hnsw';"
# EXPECTED: 1 row

# 9. EXPLAIN shows HNSW index scan (not Seq Scan) for vector search
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} \
  -c "EXPLAIN SELECT id FROM aria_data.semantic_memories ORDER BY embedding <=> '[$(python3 -c "print(','.join(['0.1']*768))")]' LIMIT 5;"
# EXPECTED: Index Scan using idx_semantic_embedding_hnsw (NOT Seq Scan)

# 10. Semantic memory search endpoint returns results without error
curl -sS "http://localhost:${ARIA_API_PORT}/api/memories/semantic?q=test&limit=3" | jq 'length >= 0'
# EXPECTED: true (no crash, returns array)

# 11. API still healthy
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-51 vector upgrade verification"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Ask Aria to verify the pgvector setup
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Check if the pgvector Python package is importable and if HAS_PGVECTOR is True in the current environment. Also check what version of PostgreSQL the database is running.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms pgvector is importable, HAS_PGVECTOR True, PostgreSQL 17.x

# Step 3 — Ask Aria to store and retrieve a semantic memory
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Store a semantic memory with content=\"pgvector upgrade test memory for S-51\" then immediately search for it using semantic search for the query \"pgvector upgrade\". Confirm the memory is returned in results.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria stores the memory and retrieves it, confirming vector search works end-to-end

# Step 4 — Log confirmation
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log a create_activity with action=pgvector_upgrade_verified, details={\"pg_version\":\"17\",\"pgvector\":\"0.8.2\",\"hnsw_indexes\":true,\"has_pgvector\":true}.","enable_tools":true}' \
  | jq -r '.content // .message // .'

# Step 5 — Reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: what was the impact of HAS_PGVECTOR being False on semantic memory quality? What does the HNSW index provide that a sequential scan does not?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on silent JSONB fallback, type mismatch crash risk, and HNSW O(log n) vs O(n) scan

# Verify activity logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=pgvector_upgrade_verified&limit=1" \
  | jq '.[0] | {action, success}'

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-51. Total changes: 4 locations across 4 files + 1 new migration file.**

### Architecture Constraints
- DB layer changes only (`docker-compose.yml`, `session.py`, new alembic migration, `pyproject.toml`)
- No changes to skills, api_client, or API routers — `cosine_distance()` ORM call is unchanged in pgvector 0.8.x
- Port from `stacks/brain/.env` → `$ARIA_API_PORT`, `$DB_PORT`, `$DB_USER`, `$DB_NAME` in all verifications
- **Do NOT use `:latest`** — pin to `pgvector/pgvector:0.8.2-pg17`
- HNSW indexes use `_safe_execute()` so they are idempotent on re-run

### Files to Read First
1. `stacks/brain/docker-compose.yml` lines 1-20 — aria-db service (confirm current image)
2. `pyproject.toml` lines 22-40 — dependencies list (confirm pgvector absent)
3. `src/api/db/session.py` lines 580-645 — semantic_memories DDL + existing indexes
4. `src/api/db/session.py` lines 420-445 — session_messages section (find embedding column + indexes)
5. `src/api/alembic/versions/s50_add_embedding_agent_id_to_chat_messages.py` lines 1-15 — get revision ID for down_revision

### Steps
1. Read all 5 files above
2. `pyproject.toml`: Add `"pgvector>=0.3.6",` to the `dependencies` list (after `"mcp>=1.0.0",`)
3. `stacks/brain/docker-compose.yml` line 4: Replace `pgvector/pgvector:0.8.0-pg16` → `pgvector/pgvector:0.8.2-pg17`
4. `src/api/db/session.py`: Add HNSW `_safe_execute()` call after `idx_semantic_created` index creation
5. `src/api/db/session.py`: Add HNSW `_safe_execute()` call after `session_messages` index block (only if embedding column present)
6. Create `src/api/alembic/versions/s51_pg17_pgvector_hnsw_upgrade.py` using the code in Fix 4 above
   - Set `down_revision` to the actual revision ID from s50 migration (read step 5)
7. Decide migration path (Path A for fresh clone, Path B for existing data — run pg_dumpall first if data exists)
8. Rebuild the aria-api container: `docker compose -f stacks/brain/docker-compose.yml build aria-api`
9. Restart the stack: `docker compose -f stacks/brain/docker-compose.yml up -d`
10. Run verification block (checks 1–11 above)
11. Run ARIA-to-ARIA integration test
12. **Update `ARCHITECTURE.md` ~line 156:** replace `PostgreSQL 16 + pgvector` → `PostgreSQL 17 + pgvector 0.8.2`
13. **Update `DEPLOYMENT.md` ~line 257:** replace `pgvector/pgvector:pg16` → `pgvector/pgvector:0.8.2-pg17`
14. **Update `DEPLOYMENT.md` ~line 546:** replace `PostgreSQL 16 + pgvector — pgvector/pgvector:pg16` → `PostgreSQL 17 + pgvector 0.8.2 — pgvector/pgvector:0.8.2-pg17`
15. Update SPRINT_OVERVIEW.md to mark S-51 Done
16. Append lesson to `tasks/lessons.md`

### Hard Constraints Checklist
- [ ] `pgvector>=0.3.6` present in `pyproject.toml` dependencies list
- [ ] `stacks/brain/docker-compose.yml` uses `pgvector/pgvector:0.8.2-pg17`
- [ ] `src/api/db/models.py` — **zero changes** (HAS_PGVECTOR becomes True automatically)
- [ ] `src/api/routers/memories.py` — **zero changes** (cosine_distance ORM call unchanged)
- [ ] HNSW index uses `vector_cosine_ops` (matches the `cosine_distance()` operator in use)
- [ ] Migration s51 file created with correct `down_revision` pointing to s50
- [ ] `pip show pgvector` in aria-api container returns version ≥ 0.3.6
- [ ] PostgreSQL 17.x confirmed via `SELECT version()`
- [ ] pgvector 0.8.2 confirmed via `SELECT extversion FROM pg_extension WHERE extname='vector'`
- [ ] EXPLAIN for embedding query shows `Index Scan using idx_semantic_embedding_hnsw` not `Seq Scan`

### Definition of Done
- [ ] `grep "pgvector" pyproject.toml` → `"pgvector>=0.3.6",`
- [ ] `grep "pgvector" stacks/brain/docker-compose.yml | head -1` → `pgvector/pgvector:0.8.2-pg17`
- [ ] `docker compose exec aria-api python3 -c "from pgvector.sqlalchemy import Vector; print('OK')"` → `OK`
- [ ] `docker compose exec aria-db psql -U $DB_USER -d $DB_NAME -c "SELECT version();"` → PostgreSQL 17.x
- [ ] `docker compose exec aria-db psql -U $DB_USER -d $DB_NAME -c "SELECT extversion FROM pg_extension WHERE extname='vector';"` → `0.8.2`
- [ ] `docker compose exec aria-db psql -U $DB_USER -d $DB_NAME -c "SELECT indexname FROM pg_indexes WHERE indexname='idx_semantic_embedding_hnsw';"` → 1 row
- [ ] `git diff HEAD -- src/api/db/models.py` → empty
- [ ] `git diff HEAD -- src/api/routers/memories.py` → empty
- [ ] `grep "PostgreSQL 17" ARCHITECTURE.md` → 1 match
- [ ] `grep "pgvector.*0.8" ARCHITECTURE.md` → 1 match
- [ ] `grep "pgvector/pgvector:0.8.2-pg17" DEPLOYMENT.md` → 2 matches (lines ~257 and ~546)
- [ ] `grep "pg16\|PostgreSQL 16" DEPLOYMENT.md` → 0 results
- [ ] `git diff HEAD -- ARCHITECTURE.md` shows pg17 + pgvector 0.8.2 update
- [ ] `git diff HEAD -- DEPLOYMENT.md` shows both pg17 references updated
- [ ] `curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status` → `"healthy"`
- [ ] ARIA-to-ARIA confirms semantic memory store + vector search works end-to-end
- [ ] SPRINT_OVERVIEW.md updated
- [ ] Lesson appended to `tasks/lessons.md`
````
