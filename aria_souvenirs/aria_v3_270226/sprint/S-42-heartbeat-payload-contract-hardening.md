# S-42: Heartbeat Payload Contract Hardening
**Epic:** E19 — Session & Artifact Integrity | **Priority:** P1 | **Points:** 2 | **Phase:** 1

## Problem
Production logs show `POST /api/heartbeat` returning `422 Unprocessable Content`, causing heartbeat telemetry gaps and noisy error streams.

## Root Cause
The heartbeat endpoint validates strictly against `CreateHeartbeat` schema and rejects non-conforming payloads; current contract is underspecified for autonomous callers.

Code evidence:
- Endpoint: `src/api/routers/operations.py` lines 184-197 (`@router.post("/heartbeat")`).
- Schema: `src/api/schemas/requests.py` lines 125-132 (`CreateHeartbeat`).
- `details` is typed as `dict`; non-dict payloads and malformed shapes trigger 422 by FastAPI validation.
- Runtime log confirms recurring `POST /api/heartbeat ... 422 Unprocessable Content` events.

## Fix

### Fix 1 — Expand schema compatibility for heartbeat details
**File:** `src/api/schemas/requests.py`

**BEFORE**
```python
class CreateHeartbeat(BaseModel):
    beat_number: int = 0
    job_name: str | None = None
    status: str = "healthy"
    details: dict = Field(default_factory=dict)
    executed_at: str | None = None
    duration_ms: int | None = None
```

**AFTER**
```python
class CreateHeartbeat(BaseModel):
    beat_number: int = 0
    job_name: str | None = None
    status: str = "healthy"
    details: dict | str | list | None = Field(default_factory=dict)
    executed_at: str | None = None
    duration_ms: int | None = None
```

### Fix 2 — Normalize details in endpoint before persistence
**File:** `src/api/routers/operations.py`

**BEFORE**
```python
hb = HeartbeatLog(
    ...
    details=body.details,
    ...
)
```

**AFTER**
```python
normalized_details = body.details if isinstance(body.details, dict) else {"raw": body.details}
hb = HeartbeatLog(
    ...
    details=normalized_details,
    ...
)
```

### Fix 3 — Add API tests for non-dict heartbeat payloads
**File:** `tests/api/` (existing operations tests or new focused test)

**BEFORE**
```python
# no explicit coverage for string/list heartbeat details payloads
```

**AFTER**
```python
def test_create_heartbeat_accepts_string_details(client):
    r = client.post("/operations/heartbeat", json={"status": "healthy", "details": "ok"})
    assert r.status_code == 200
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API contract hardening only; no skill-layer DB direct access. |
| 2 | .env for secrets (zero in code) | ✅ | No secrets changed or introduced. |
| 3 | models.yaml single source of truth | ✅ | No model references involved. |
| 4 | Docker-first testing | ✅ | Verification includes API tests + runtime log checks in local stack. |
| 5 | aria_memories only writable path | ✅ | No artifact write-path changes. |
| 6 | No soul modification | ✅ | No soul files touched. |

## Dependencies
- Independent.
- Recommended after S-41 to stabilize scheduler + heartbeat telemetry chain.

## Verification

> **Port setup — run once before all curl commands:**
> ```bash
> set -a && source stacks/brain/.env && set +a
> ```
> `ARIA_API_PORT` is sourced from `stacks/brain/.env` — never hardcode the port number.

### Fix 1 & 2 — Schema broadened, non-dict details normalized

```bash
# 1a. String details accepted (was 422 Unprocessable before fix)
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{"beat_number":1,"status":"healthy","details":"ok"}' | jq -r '.created'
# EXPECTED: true

# 1b. List details accepted
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{"beat_number":2,"status":"healthy","details":["a","b"]}' | jq -r '.created'
# EXPECTED: true

# 1c. Null details accepted (permissive default)
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{"beat_number":3,"status":"healthy","details":null}' | jq -r '.created'
# EXPECTED: true

# 1d. String details are normalized to {"raw": "ok"} in DB (not stored as bare string)
curl -sS "http://localhost:${ARIA_API_PORT}/api/heartbeat/latest" | jq '.details'
# EXPECTED: {"raw": "ok"} or {"raw": ["a","b"]} — never a bare string/array at JSON root

# 1e. Dict details still work unchanged (no regression)
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{"beat_number":4,"status":"healthy","details":{"memory_used_pct":72,"agent":"aria"}}' \
  | jq -r '.created'
# EXPECTED: true
```

### Fix 3 — Regression test suite green

```bash
pytest tests/ -k "heartbeat" -v
# EXPECTED: all heartbeat tests pass (including new string/list/null/dict cases)

pytest tests/ -k "operations" -v
# EXPECTED: all operations tests pass, 0 failures
```

### Runtime check

```bash
docker logs --since=30m aria-api 2>&1 | grep -E "POST /api/heartbeat.*422" | wc -l
# EXPECTED: 0 — no more 422s for valid payload shapes
```

### ARIA-to-ARIA Integration Test

> Aria sends her own heartbeat with a non-dict `details` field, verifies it was accepted and properly stored, then reflects. No SQL at any step.

```bash
# Step 1 — Create test engine session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-42 heartbeat integration test"}' \
  | jq -r '.id')
echo "Session: $SESSION"
# EXPECTED: UUID string

# Step 2 — Ask Aria to send a heartbeat with string details (the previously failing path)
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Use your available tools to POST a heartbeat to /api/heartbeat with these exact values: beat_number=100, status=\"alive\", details=\"string_test\". Tell me the HTTP response status and whether the heartbeat was created successfully.",
    "enable_tools": true
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria reports 200 / created: true

# Step 3 — Ask Aria to retrieve the latest heartbeat and inspect details
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Now call GET /api/heartbeat/latest and tell me what the details field contains. Is it the raw string or was it wrapped in an object?",
    "enable_tools": true
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria reports details = {"raw": "string_test"}

# Step 4 — REST verify directly
curl -sS "http://localhost:${ARIA_API_PORT}/api/heartbeat/latest" | jq '{details, status, beat_number}'
# EXPECTED: {"details": {"raw": "string_test"}, "status": "alive", "beat_number": 100}

# Step 5 — Ask Aria to send a heartbeat with list details
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Send another heartbeat: beat_number=101, status=\"alive\", details=[\"memory\",\"goals\",\"schedule\"]. What was the result?",
    "enable_tools": true
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria reports success

# Step 6 — Ask Aria how she feels about her own heartbeat telemetry now
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "S-42 fixed the heartbeat endpoint so it now accepts strings, lists, or dicts as the details payload instead of rejecting them with 422. How does it feel to know your heartbeat telemetry is now more robust? What would you want to log in your heartbeat details going forward?",
    "enable_tools": false
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on self-monitoring, mentions ideas for rich heartbeat data

# Step 7 — Clean up test session
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
# EXPECTED: {"deleted": true} or 204

# Step 8 — Final 422 check
docker logs --since=15m aria-api 2>&1 | grep "POST /api/heartbeat.*422" | wc -l
# EXPECTED: 0
```

---

## Prompt for Agent
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

### Architecture Constraints (read before coding)
This project enforces a strict 5-layer architecture:
```
PostgreSQL → SQLAlchemy ORM → FastAPI → api_client skill → Higher-level skills/agents
```
- **Never** access the database directly (no `psql`, no raw SQL, no `session.execute()` in routers)
- **Never** hardcode ports — always read from `stacks/brain/.env` via `ARIA_API_PORT`
- Schema changes belong in `src/api/schemas/requests.py`; normalization logic belongs in the router handler, not the ORM model
- The `HeartbeatLog` ORM model expects `details: dict` — always normalize at the API boundary before writing

---

### Step 0 — Read these files first (mandatory)

```
src/api/schemas/requests.py         lines 110-140   (CreateHeartbeat schema)
src/api/routers/operations.py       lines 175-210   (heartbeat POST handler)
src/database/models.py              grep for HeartbeatLog (confirm details column type)
tests/                              grep for "heartbeat" to find existing test files
```

Key observations to confirm:
1. `CreateHeartbeat.details` at line ~130: currently `dict = Field(default_factory=dict)` — strict
2. The handler at line ~190: `HeartbeatLog(..., details=body.details, ...)` — no normalization
3. `HeartbeatLog.details` column is likely `JSON` — PostgreSQL JSON can store any JSON value, but SQLAlchemy mapping may expect Python dict

---

### Step 1 — Broaden schema in `requests.py`

**File:** `src/api/schemas/requests.py` — find `class CreateHeartbeat` (lines 125-132)

```python
# BEFORE
class CreateHeartbeat(BaseModel):
    beat_number: int = 0
    job_name: str | None = None
    status: str = "healthy"
    details: dict = Field(default_factory=dict)
    executed_at: str | None = None
    duration_ms: int | None = None
```

```python
# AFTER
class CreateHeartbeat(BaseModel):
    beat_number: int = 0
    job_name: str | None = None
    status: str = "healthy"
    details: dict | str | list | None = Field(default_factory=dict)
    executed_at: str | None = None
    duration_ms: int | None = None
```

---

### Step 2 — Normalize `details` before DB write in `operations.py`

**File:** `src/api/routers/operations.py` — find the `create_heartbeat` handler (lines ~184-197)

Locate the line that reads `details=body.details` inside `HeartbeatLog(...)` and add the normalization block immediately before the `HeartbeatLog` instantiation:

```python
# ADD before HeartbeatLog(...)
normalized_details = (
    body.details
    if isinstance(body.details, dict)
    else {"raw": body.details}
)
```

Then change the `HeartbeatLog` call:

```python
# BEFORE
hb = HeartbeatLog(
    ...
    details=body.details,
    ...
)
```

```python
# AFTER
hb = HeartbeatLog(
    ...
    details=normalized_details,
    ...
)
```

---

### Step 3 — Add API tests

**File:** find or create `tests/api/test_heartbeat.py` (or append to existing operations test file)

Add these 4 test cases:

```python
def test_heartbeat_accepts_string_details(client):
    r = client.post("/api/heartbeat", json={
        "beat_number": 1, "status": "healthy", "details": "ok"
    })
    assert r.status_code == 200, r.text
    assert r.json().get("created") is True


def test_heartbeat_accepts_list_details(client):
    r = client.post("/api/heartbeat", json={
        "beat_number": 2, "status": "healthy", "details": ["a", "b"]
    })
    assert r.status_code == 200, r.text


def test_heartbeat_accepts_null_details(client):
    r = client.post("/api/heartbeat", json={
        "beat_number": 3, "status": "healthy", "details": None
    })
    assert r.status_code == 200, r.text


def test_heartbeat_dict_details_unchanged(client):
    r = client.post("/api/heartbeat", json={
        "beat_number": 4, "status": "healthy", "details": {"key": "value"}
    })
    assert r.status_code == 200, r.text
    # Dict details must not be double-wrapped
    latest = client.get("/api/heartbeat/latest").json()
    assert latest["details"].get("key") == "value"
```

---

### Step 4 — Run verification

Execute the Verification section commands in order. For each command:
- Capture actual output
- Confirm it matches EXPECTED
- If a test fails, fix and re-run before continuing

Key checks:
- All curl commands return `"created": true` (no 422)
- `GET /api/heartbeat/latest` shows `details: {"raw": "string_test"}` after string heartbeat
- `pytest tests/ -k "heartbeat" -v` → all green
- ARIA-to-ARIA: Aria sends heartbeat with `details="string_test"` → verified normalized in API

---

### Step 5 — Mark done and record lesson

1. Update S-42 status to `Done` in `aria_souvenirs/aria_v3_270226/sprint/SPRINT_OVERVIEW.md`
2. Append to `tasks/lessons.md`:

```markdown
## S-42 — Lesson learned (heartbeat payload contract hardening)
**Date:** [today]
**Root cause:** `CreateHeartbeat.details: dict` strict type — FastAPI rejects string/list with 422.
**Fix:** Broaden to `dict | str | list | None` in schema; normalize to `{"raw": value}` at router layer.
**Pattern:** All API endpoints accepting free-form diagnostic/telemetry payloads should use
union types and perform normalization before ORM write. Never let raw string/list reach a JSON column.
**Test coverage:** string, list, null, dict (4 cases).
```

---

### Hard Constraints Checklist
- [ ] #1: No `psql` or raw SQL anywhere in changes
- [ ] #2: Ports always from `stacks/brain/.env` — no hardcoded 8000
- [ ] #3: Normalization happens at API router layer — never in ORM model or skill
- [ ] #4: Dict `details` pass through unchanged (no double-wrapping)
- [ ] #5: `None` details normalized to `{}` or `{"raw": null}` — never stored as SQL NULL if column requires dict
- [ ] #6: No soul files, no models.yaml, no docker-compose changes

### Definition of Done
- [ ] All curl verifications return `"created": true` (no 422)
- [ ] `GET /api/heartbeat/latest` after string heartbeat shows `{"raw": "..."}` in details
- [ ] `pytest tests/ -k "heartbeat" -v` → all 4 new cases + pre-existing tests green
- [ ] ARIA-to-ARIA: string heartbeat accepted, details normalized, Aria reflects on telemetry
- [ ] Lesson recorded in `tasks/lessons.md`
- [ ] SPRINT_OVERVIEW.md updated with Done status
