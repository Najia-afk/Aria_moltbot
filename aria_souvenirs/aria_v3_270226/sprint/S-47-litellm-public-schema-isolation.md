# S-47: LiteLLM Writing to Public Schema — Schema Isolation Broken
**Epic:** E20 — Database Integrity | **Priority:** P0** | **Points:** 2 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

> ⚠️ **P0 — Data Corruption Risk**  
> LiteLLM is actively creating/writing tables in the `public` schema instead of `litellm`. This
> violates the architecture constraint ("nothing in public") and makes backup/restore and schema
> audits unreliable.

---

## Problem

Three places in the codebase set `search_path=litellm,public`. The `,public` fallback means
PostgreSQL will silently create LiteLLM tables in `public` whenever the `litellm` schema is
missing or doesn't yet own a given table name.

**Affected files and exact lines:**

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `stacks/brain/docker-compose.yml` | 221 | LiteLLM `DATABASE_URL` includes `search_path%3Dlitellm,public` | 🔴 Data corruption |
| `src/api/db/session.py` | 55 | `_litellm_url_from()` appends `?options=-csearch_path%3Dlitellm,public` | 🔴 Data corruption |
| `src/api/deps.py` | 28 | `SET search_path TO litellm, public` | 🔴 Data corruption |
| `src/api/db/session.py` | 129 | `ensure_schema()` never creates `litellm` schema — it only creates `aria_data` and `aria_engine` | 🔴 Root cause |

**Failure sequence that causes the bug:**
1. First run (or after DB reset) — `litellm` schema does not exist
2. LiteLLM container starts with `search_path=litellm,public`
3. Prisma migration looks for schema `litellm`:
   - If not found → PostgreSQL falls through to `public`
   - Prisma creates `_prisma_migrations`, `LiteLLM_SpendLogs`, `LiteLLM_VerificationToken`, etc. directly in `public`
4. Those tables now pollute `public` for the lifetime of that DB volume
5. Even on a clean run where `litellm` schema exists: if any table is wrong, Prisma probes `public` as backup

**Confirmed:** `docs/archive/DATA_MIGRATION_REPORT.md` line 62 lists `litellm__prisma_migrations` — the double-underscore is Prisma naming convention when it falls into an unexpected schema.

**Constraint violated:** Architecture rule: _"nothing in public"_ — all tables must be in named schemas (`aria_data`, `aria_engine`, `litellm`).

---

## Root Cause

| Symptom | Root Cause |
|---------|------------|
| LiteLLM tables appear in `public` schema instead of `litellm` | `ensure_schema()` never creates the `litellm` schema — LiteLLM starts before it exists, Prisma falls through to `public` |
| `,public` fallback was added via workaround | When LiteLLM migrations initially failed (schema didn't exist), `,public` was added as a quick fix — masking the root problem |
| Pollution survives DB restarts | Once tables exist in `public`, they persist in the volume even after the real `litellm` schema is created |

---

## Fix

### Fix 1 — Create `litellm` schema in `ensure_schema()`

**File:** `src/api/db/session.py`

```python
# BEFORE (line ~129)
for schema_name in ("aria_data", "aria_engine"):
    await _run_isolated(conn, f"schema_{schema_name}",
                        f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

# AFTER
for schema_name in ("aria_data", "aria_engine", "litellm"):
    await _run_isolated(conn, f"schema_{schema_name}",
                        f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
```

### Fix 2 — Remove `,public` from `_litellm_url_from()` 

**File:** `src/api/db/session.py`

```python
# BEFORE (line ~55)
return f"{base}?options=-csearch_path%3Dlitellm,public"

# AFTER
return f"{base}?options=-csearch_path%3Dlitellm"
```

### Fix 3 — Remove `,public` from LiteLLM container `DATABASE_URL`

**File:** `stacks/brain/docker-compose.yml`

```yaml
# BEFORE (line 221)
DATABASE_URL: postgresql://${DB_USER:-admin}:${DB_PASSWORD:-admin}@aria-db:${DB_INTERNAL_PORT:-5432}/${DB_NAME:-aria_warehouse}?options=-csearch_path%3Dlitellm,public

# AFTER
DATABASE_URL: postgresql://${DB_USER:-admin}:${DB_PASSWORD:-admin}@aria-db:${DB_INTERNAL_PORT:-5432}/${DB_NAME:-aria_warehouse}?options=-csearch_path%3Dlitellm
```

### Fix 4 — Remove `,public` from `get_litellm_db()` in deps.py

**File:** `src/api/deps.py`

```python
# BEFORE (line 28)
await session.execute(text("SET search_path TO litellm, public"))

# AFTER
await session.execute(text("SET search_path TO litellm"))
```

---

## Fresh Clone Dependency

> **Prerequisite: S-49** — this fix depends on `stacks/brain/.env` existing and containing a
> valid `DB_PASSWORD` / `DATABASE_URL`. A fresh clone without `.env` means `ensure_schema()`
> never runs (aria-api crashes before it reaches the DB), so the `litellm` schema never gets
> created and the isolation fix is moot. S-49 (auto-bootstrap) must land first or alongside.

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Changes in DB/ORM layer only |
| 2 | `stacks/brain/.env` for all secrets/ports | ✅ | Verification uses `$ARIA_API_PORT` |
| 3 | No direct SQL from skills | ✅ | Fix is in DB session layer only |
| 4 | Nothing in `public` schema | ✅ | This is the constraint being enforced |
| 5 | `aria_memories/` only writable path for Aria | ✅ | Not applicable — server-side fix |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `ARCHITECTURE.md` | DB schema table | `litellm, public` in LiteLLM schema column | `litellm` only — public schema no longer used by LiteLLM |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. ensure_schema() creates litellm schema
grep -n "litellm" src/api/db/session.py | grep "schema_litellm\|litellm.*ensure\|for schema_name"
# EXPECTED: "litellm" appears in the for loop with aria_data and aria_engine

# 2. No ,public in _litellm_url_from
grep -n "search_path" src/api/db/session.py
# EXPECTED: search_path%3Dlitellm (no trailing ,public)

# 3. No ,public in docker-compose LiteLLM DATABASE_URL
grep -n "search_path" stacks/brain/docker-compose.yml
# EXPECTED: search_path%3Dlitellm (no trailing ,public)

# 4. No ,public in deps.py
grep -n "search_path" src/api/deps.py
# EXPECTED: SET search_path TO litellm (no , public)

# 5. After restart — litellm schema exists (not just public)
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} \
  -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('litellm','aria_data','aria_engine','public') ORDER BY schema_name;"
# EXPECTED: aria_data, aria_engine, litellm, public all listed (public is system-mandatory, just must stay empty)

# 6. LiteLLM tables are in litellm schema, NOT public
docker compose -f stacks/brain/docker-compose.yml exec aria-db \
  psql -U ${DB_USER:-admin} -d ${DB_NAME:-aria_warehouse} \
  -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name NOT LIKE 'pg_%' ORDER BY table_name;"
# EXPECTED: 0 rows — public schema has no user tables

# 7. API still healthy after DB schema change
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"

# 8. LiteLLM models endpoint still responds (its DB is intact)
curl -sS "http://localhost:${ARIA_API_PORT}/api/llm/models" | jq '. | length'
# EXPECTED: number > 0
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-47 public schema audit"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Ask Aria to audit the schema isolation
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read src/api/db/session.py. Tell me: (1) Does ensure_schema() create the litellm schema? (2) Does _litellm_url_from() still have ,public in the search_path? (3) What schemas are in the for loop?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms litellm in the loop, no ,public in search_path

# Step 3 — Ask Aria to check the live database
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Check if any LiteLLM tables exist in the public schema by calling the API health endpoint and reading the LiteLLM model list. Are both responding? Does any error mention public schema?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms health OK, LiteLLM models available, no public schema error

# Step 4 — Log confirmation
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log a create_activity with action=schema_isolation_verified, details={\"litellm_in_ensure_schema\":true,\"public_fallback_removed\":true}.","enable_tools":true}' \
  | jq -r '.content // .message // .'

# Step 5 — Reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: What could have gone wrong if LiteLLM had continued writing to the public schema over time? What does this fix protect?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on data integrity risk — backup pollution, migration conflicts, audit failures

# Verify activity logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=schema_isolation_verified&limit=1" \
  | jq '.[0] | {action, success}'

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-47. Total changes: 4 lines across 3 files.**

### Architecture Constraints
- All changes are in the **DB layer** (`session.py`, `deps.py`) and **docker-compose config** — no skills, no api_client
- Port from `stacks/brain/.env` → `$ARIA_API_PORT` in all verifications
- **Do NOT run direct SQL on the schema via `psql` yourself** — verification uses the psql check to inspect what the code creates, not to manually create schemas

### Files to Read First
1. `src/api/db/session.py` — full file (269 lines), focus on `_litellm_url_from()` (line ~48) and `ensure_schema()` (line ~115)
2. `src/api/deps.py` — full file, focus on `get_litellm_db()` (line ~23)
3. `stacks/brain/docker-compose.yml` — line 213-245 (litellm service)

### Steps
1. Read all 3 files
2. `src/api/db/session.py` line ~129: add `"litellm"` to the for loop alongside `"aria_data"` and `"aria_engine"`
3. `src/api/db/session.py` line ~55: change `search_path%3Dlitellm,public` → `search_path%3Dlitellm`
4. `stacks/brain/docker-compose.yml` line 221: remove `,public` from DATABASE_URL search_path
5. `src/api/deps.py` line 28: change `SET search_path TO litellm, public` → `SET search_path TO litellm`
6. Restart the stack: `docker compose -f stacks/brain/docker-compose.yml up -d aria-db aria-api litellm` (or restart the relevant containers)
7. Run verification block (schema checks + API health)
8. Run ARIA-to-ARIA integration test
9. **Update `ARCHITECTURE.md`** DB schema table: change `litellm, public` → `litellm` in the LiteLLM schema column
10. Update SPRINT_OVERVIEW.md to mark S-47 Done
11. Append lesson to `tasks/lessons.md`

### Hard Constraints Checklist
- [ ] All 4 occurrences of `,public` in search_path removed
- [ ] `"litellm"` added to `ensure_schema()` schema loop
- [ ] No manual SQL `CREATE SCHEMA` commands — ensure_schema() handles it at runtime
- [ ] API still starts clean after changes
- [ ] LiteLLM container still healthy after changes

### Definition of Done
- [ ] `grep "search_path" src/api/db/session.py | grep ",public"` → 0 results
- [ ] `grep "search_path" src/api/deps.py | grep ",public"` → 0 results  
- [ ] `grep "search_path" stacks/brain/docker-compose.yml | grep ",public"` → 0 results
- [ ] `grep "litellm" src/api/db/session.py | grep "for schema_name"` OR `grep -A5 "for schema_name" src/api/db/session.py | grep litellm` → match found
- [ ] DB check: 0 rows in `public` schema with user tables after stack restart
- [ ] `curl http://localhost:${ARIA_API_PORT}/health | jq .status` → "healthy"
- [ ] `grep -i "litellm.*public\|public.*litellm" ARCHITECTURE.md` → 0 results (no more `,public` in schema table)
- [ ] `git diff HEAD -- ARCHITECTURE.md` shows schema table updated
- [ ] ARIA-to-ARIA confirms `ensure_schema()` change and schema isolation
- [ ] SPRINT_OVERVIEW.md updated
