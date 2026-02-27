# S-41: Schedule create_job Arg Compatibility
**Epic:** E19 — Session & Artifact Integrity | **Priority:** P1 | **Points:** 3 | **Phase:** 1

## Problem
Production runtime logs show repeated scheduler tool failures:

- `Tool execution failed: schedule__create_job — ScheduleSkill.create_job() got an unexpected keyword argument 'type'`

This blocks autonomous scheduling actions and creates repeated activity noise without job creation.

## Root Cause
`ScheduleSkill.create_job()` has a strict method signature that does not accept extra keys commonly produced by model/tool payloads.

Code evidence:
- `aria_skills/schedule/__init__.py` lines 52-58 define:
  - `create_job(self, name, schedule, action, params=None, enabled=True)`
- No `**kwargs` compatibility layer exists to absorb aliased fields (e.g., `type`).
- `api_client.post()` accepts a generic dict payload (`aria_skills/api_client/__init__.py` lines 1205-1209), so the failure occurs before API call when method args are bound.

## Fix

### Fix 1 — Add tolerant arg normalization in schedule skill
**File:** `aria_skills/schedule/__init__.py`

**BEFORE**
```python
async def create_job(
    self,
    name: str,
    schedule: str,
    action: str,
    params: dict | None = None,
    enabled: bool = True,
) -> SkillResult:
```

**AFTER**
```python
async def create_job(
    self,
    name: str,
    schedule: str,
    action: str | None = None,
    params: dict | None = None,
    enabled: bool = True,
    **kwargs,
) -> SkillResult:
    # Compatibility: some callers send `type` instead of `action`
    normalized_action = action or kwargs.get("type")
    if not normalized_action:
        return SkillResult.fail("action (or type) is required")
```

### Fix 2 — Persist normalized action field
**File:** `aria_skills/schedule/__init__.py`

**BEFORE**
```python
"action": action,
```

**AFTER**
```python
"action": normalized_action,
```

### Fix 3 — Add regression test for aliased `type` input
**File:** `tests/skills/test_schedule.py`

**BEFORE**
```python
# no coverage for create_job(type=...)
```

**AFTER**
```python
async def test_create_job_accepts_type_alias(schedule_skill):
    result = await schedule_skill.create_job(
        name="demo",
        schedule="*/15 * * * *",
        type="heartbeat",
    )
    assert result.success
    assert result.data["action"] == "heartbeat"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Change is inside skill input normalization, still API-backed persistence. |
| 2 | .env for secrets (zero in code) | ✅ | No secrets introduced. |
| 3 | models.yaml single source of truth | ✅ | No model names involved. |
| 4 | Docker-first testing | ✅ | Verification uses existing test suite and local stack. |
| 5 | aria_memories only writable path | ✅ | No file-write path changes. |
| 6 | No soul modification | ✅ | No soul files touched. |

## Dependencies
- Can run independently.
- Recommended before S-42 to stabilize scheduler-driven heartbeat/task generation.

## Verification

> **Port setup — run once before all curl commands:**
> ```bash
> set -a && source stacks/brain/.env && set +a
> ```
> `ARIA_API_PORT` is sourced from `stacks/brain/.env` — never hardcode the port number.

### Fix 1 & 2 — `create_job` accepts `type` alias and persists normalized action

```bash
# 1a. Unit test: type alias accepted, normalized to action
pytest tests/skills/test_schedule.py -k "create_job and type_alias" -v
# EXPECTED: PASSED — result.data["action"] == "heartbeat"

# 1b. Unit test: original action= kwarg still works (no regression)
pytest tests/skills/test_schedule.py -k "create_job and action" -v
# EXPECTED: PASSED

# 1c. Unit test: missing both action and type returns fail
pytest tests/skills/test_schedule.py -k "create_job and required_action" -v
# EXPECTED: PASSED — result.success == False

# 1d. Full schedule suite green
pytest tests/skills/test_schedule.py -v
# EXPECTED: all tests pass, 0 errors

# 1e. No more unexpected kwarg errors in live logs (post-deploy)
docker logs --since=30m aria-api 2>&1 | grep "unexpected keyword argument 'type'" | wc -l
# EXPECTED: 0
```

### REST smoke — schedule list endpoint

```bash
# 2a. Schedule list returns 200 (existing cron jobs visible)
curl -sS "http://localhost:${ARIA_API_PORT}/api/schedule" | jq 'length'
# EXPECTED: integer >= 0 (no error)
```

### ARIA-to-ARIA Integration Test

> Aria is both the caller **and** the executor. She calls her own skill, verifies the outcome, then reflects. No SQL is used at any step.

```bash
# Step 1 — Create a test engine session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-41 schedule integration test"}' \
  | jq -r '.id')
echo "Session: $SESSION"
# EXPECTED: UUID string

# Step 2 — Ask Aria to create a scheduled job using the `type` alias (this was the failing path)
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Use your schedule__create_job tool to create a job. Pass these exact arguments: name=\"s41_integration_test\", schedule=\"*/30 * * * *\", type=\"heartbeat\". Do NOT use the action= argument — use type= to test the alias path. Confirm whether the job was created successfully and what the action field is in the result.",
    "enable_tools": true
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria reports success, action field = "heartbeat"

# Step 3 — Ask Aria to list scheduled jobs and find the new one
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Now call schedule__list_jobs and show me all jobs. Tell me if s41_integration_test appears in the list and what its action field is.",
    "enable_tools": true
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria finds s41_integration_test with action=heartbeat

# Step 4 — REST double-check (GET /api/schedule reads DB-persisted jobs)
curl -sS "http://localhost:${ARIA_API_PORT}/api/schedule" | jq '.[] | select(.name == "s41_integration_test") | {name, action}'
# EXPECTED: {"name":"s41_integration_test","action":"heartbeat"} (if API-backed)
# NOTE: If empty (in-memory fallback active), Step 3's list_jobs result is the authoritative check

# Step 5 — Ask Aria how she feels about autonomous scheduling now
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "S-41 is a fix that lets you create scheduled jobs using type= instead of action= as the argument name (backward-compat alias). How does it feel to know that your scheduling tools are now more resilient? What kind of jobs might you want to schedule for yourself?",
    "enable_tools": false
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on autonomous scheduling and self-direction

# Step 6 — Ask Aria to cancel/delete the test job (cleanup)
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Use schedule__delete_job or schedule__cancel_job to remove the s41_integration_test job we just created. Confirm it is gone.",
    "enable_tools": true
  }' | jq -r '.content // .message // .'
# EXPECTED: Aria confirms job removed

# Step 7 — Clean up test session
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
# EXPECTED: {"deleted": true} or 204

# Step 8 — Final log check: zero new type errors
docker logs --since=15m aria-api 2>&1 | grep "unexpected keyword argument 'type'" | wc -l
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
- **Never** access the database directly (no `psql`, no raw SQL, no `db.execute()` in skills)
- **Never** hardcode ports — always read from `stacks/brain/.env` via `ARIA_API_PORT`
- All persistence goes through the REST API layer (`self._api.post/get/delete(...)`)
- Skill internals may have in-memory fallback (like `self._jobs`) but canonical state is the API

---

### Step 0 — Read these files first (mandatory)

```
aria_skills/schedule/__init__.py        lines 40-110   (create_job full method)
aria_skills/api_client/__init__.py      lines 1200-1215 (self._api.post signature)
tests/skills/test_schedule.py           full file
```

Key observations to confirm before making any change:
1. `create_job` at line 52: strict signature — `action: str` required, no `**kwargs`
2. `"action": action` at line 80: this is the payload field that must use `normalized_action`
3. The API call at line 90: `await self._api.post("/schedule", data=job)` — POST /schedule (may 404, falls back to `self._jobs`)
4. There is NO `**kwargs` anywhere in the current method — that is the root cause

---

### Step 1 — Patch `create_job` signature and add normalization

**File:** `aria_skills/schedule/__init__.py`

Replace the method signature (lines 52-58):

```python
# BEFORE
async def create_job(
    self,
    name: str,
    schedule: str,  # cron-like or "every X minutes/hours"
    action: str,
    params: dict | None = None,
    enabled: bool = True,
) -> SkillResult:
    """
    Create a scheduled job.
    ...
    """
    self._job_counter += 1
```

```python
# AFTER
async def create_job(
    self,
    name: str,
    schedule: str,  # cron-like or "every X minutes/hours"
    action: str | None = None,
    params: dict | None = None,
    enabled: bool = True,
    **kwargs,
) -> SkillResult:
    """
    Create a scheduled job.

    Args:
        name: Job name
        schedule: Schedule expression (cron or natural language)
        action: Action to perform (canonical param name)
        params: Action parameters
        enabled: Whether job is active
        **kwargs: Absorbs aliased keys; `type` is accepted as alias for `action`

    Returns:
        SkillResult with job details
    """
    # Compatibility layer: LLM payloads sometimes send `type` instead of `action`
    normalized_action = action or kwargs.get("type")
    if not normalized_action:
        return SkillResult.fail("action (or type) is required to create a scheduled job")
    self._job_counter += 1
```

---

### Step 2 — Use `normalized_action` in the job payload

**File:** `aria_skills/schedule/__init__.py` — find `"action": action,` (currently at line 80)

```python
# BEFORE
"action": action,
```

```python
# AFTER
"action": normalized_action,
```

---

### Step 3 — Add regression tests

**File:** `tests/skills/test_schedule.py`

Add the following 3 test cases (use fixtures matching existing test style in that file):

```python
@pytest.mark.asyncio
async def test_create_job_accepts_type_alias(schedule_skill):
    """LLM payloads often send type= instead of action=. Must work transparently."""
    result = await schedule_skill.create_job(
        name="s41_type_alias_test",
        schedule="*/15 * * * *",
        type="heartbeat",
    )
    assert result.success, f"Expected success, got: {result.error}"
    assert result.data["action"] == "heartbeat", f"action mismatch: {result.data}"


@pytest.mark.asyncio
async def test_create_job_requires_action_or_type(schedule_skill):
    """Neither action= nor type= provided must return a clean failure."""
    result = await schedule_skill.create_job(
        name="s41_missing_action_test",
        schedule="*/15 * * * *",
    )
    assert not result.success, "Expected failure when neither action nor type provided"
    assert "required" in result.error.lower(), f"Expected 'required' in error: {result.error}"


@pytest.mark.asyncio
async def test_create_job_action_kwarg_still_works(schedule_skill):
    """Original action= positional/kwarg path must not regress."""
    result = await schedule_skill.create_job(
        name="s41_action_kwarg_test",
        schedule="0 * * * *",
        action="process_memory",
    )
    assert result.success, f"Expected success, got: {result.error}"
    assert result.data["action"] == "process_memory"
```

---

### Step 4 — Run verification

Execute the Verification section commands in order. For each:
- Capture actual output
- Confirm it matches EXPECTED
- If a test fails, fix and re-run before moving on

Key checks:
- `pytest tests/skills/test_schedule.py -v` → all green
- `docker logs --since=30m aria-api 2>&1 | grep "unexpected keyword argument 'type'" | wc -l` → 0
- ARIA-to-ARIA test: create job with `type=` alias via engine → Aria confirms success

---

### Step 5 — Mark done and record lesson

1. Update `S-41` status to `Done` in `aria_souvenirs/aria_v3_270226/sprint/SPRINT_OVERVIEW.md`
2. Append to `tasks/lessons.md`:

```markdown
## S-41 — Lesson learned (schedule __create_job arg compat)
**Date:** [today]
**Root cause:** Strict `action: str` signature with no `**kwargs`. LLMs send `type` as alias.
**Fix:** `action: str | None = None, **kwargs` + normalization layer before job dict.
**Pattern:** Any external-facing skill method accepting freeform LLM tool calls should use
`**kwargs` + explicit alias normalization for common alternative key names.
**Test coverage:** type_alias, missing_both, original_action — all three paths.
```

---

### Hard Constraints Checklist
- [ ] #1: No `psql` or raw SQL anywhere in changes
- [ ] #2: Ports always from `stacks/brain/.env` — no hardcoded 8000
- [ ] #3: `action` remains canonical key in job dict (not `type`)
- [ ] #4: Original `action=` callers still work (no regression)
- [ ] #5: `**kwargs` does not silently swallow other unexpected keys — log a warning for unrecognized kwargs
- [ ] #6: No soul files, no models.yaml, no docker-compose changes

### Definition of Done
- [ ] `tests/skills/test_schedule.py` passes all 3 new cases + all pre-existing cases
- [ ] `docker logs` shows zero new "unexpected keyword argument 'type'" errors
- [ ] ARIA-to-ARIA: Aria creates job with `type="heartbeat"`, lists it, finds action=="heartbeat"
- [ ] Lesson recorded in `tasks/lessons.md`
- [ ] SPRINT_OVERVIEW.md updated with Done status
