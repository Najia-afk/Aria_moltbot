# S-39: Work-Cycle Log Integrity Guardrails
**Epic:** E19 — Session & Artifact Integrity | **Priority:** P1 | **Points:** 5 | **Phase:** 1
**Status:** NOT STARTED | **Reviewed:** 3× (code-verified 2026-02-27)

---

## Problem

Work-cycle artifacts from the last 8 hours are internally inconsistent and one `.json` artifact contains raw Markdown instead of valid JSON.

**Verified filesystem evidence (2026-02-27):**
- `aria_memories/logs/work_cycle_2026-02-27_14-01.md` line 8 reports `Agent Sessions: 8 (7 ended, 1 active)`, while line 12 reports `8 total sessions, 0 stale pruned`.
- `aria_memories/logs/work_cycle_2026-02-27_1416.json` lines 11-15 reports `total: 1, active: 1, stale_pruned: 0`.
- `aria_memories/logs/work_cycle_2026-02-27_15.json` line 8 reports `14 sessions, 0 stale pruned`.
- `aria_memories/memory/logs/work_cycle_2026-02-27_1531.json` line 1 starts with markdown heading (`# Work Cycle...`) despite `.json` extension.

These artifacts feed operational understanding and sprint decisions; inconsistent counts and malformed JSON reduce trust in dashboards, bug triage, and sprint reporting.

## Root Cause
The issue is structural in write/aggregation paths, not a one-off content typo.

Code evidence:
1. Artifact writes do not validate file extension vs content format:
   - `src/api/routers/artifacts.py` lines 45-49 accept arbitrary `filename`/`content`.
   - `src/api/routers/artifacts.py` lines 73-74 write raw content to disk without JSON validation.

2. Session statistics are computed by different semantics across surfaces:
   - `src/api/routers/sessions.py` lines 258-263 compute active sessions by explicit DB status (`status == "active"`) with include/exclude filters.
   - `aria_skills/session_manager/__init__.py` lines 274-277 compute active sessions as `len(sessions) - stale_count` using timestamp staleness heuristics (lines 257-272), which is a different definition.

3. Work-cycle prompt allows free-form output and does not force machine-parseable artifact format:
   - `aria_mind/cron_jobs.yaml` line 36 uses broad instructions for logging but does not require strict JSON schema output for `work_cycle` artifacts.

4. Goal ordering is inconsistent between prompt assembly and API listing (can cause selection/reporting drift):
   - `aria_engine/prompts.py` lines 293-295 sorts active goals by descending priority.
   - `src/api/routers/goals.py` line 69 sorts goals by ascending priority.

## Fix

### Fix 1 — Enforce content/extension integrity in artifacts API
**File:** `src/api/routers/artifacts.py`  
**Lines:** 45-49, 73-74

**BEFORE**
```python
class ArtifactWriteRequest(BaseModel):
    content: str
    filename: str
    category: str = "memory"
    subfolder: str | None = None

with open(filepath, "w", encoding="utf-8") as f:
    f.write(body.content)
```

**AFTER**
```python
class ArtifactWriteRequest(BaseModel):
    content: str
    filename: str
    category: str = "memory"
    subfolder: str | None = None

# Validate JSON payloads when filename ends with .json
if body.filename.lower().endswith(".json"):
    try:
        json.loads(body.content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON content for '{body.filename}': {exc.msg}",
        )

with open(filepath, "w", encoding="utf-8") as f:
    f.write(body.content)
```

### Fix 2 — Use canonical session stats source in session_manager
**File:** `aria_skills/session_manager/__init__.py`  
**Lines:** 240-282

**BEFORE**
```python
sessions = await self._fetch_sessions(limit=200)
...
"active_sessions": len(sessions) - stale_count,
```

**AFTER**
```python
stats_resp = await self._api.get(
    "/sessions/stats",
    params={"include_runtime_events": True, "include_cron_events": True},
)
if not stats_resp.success:
    return SkillResult.fail(f"Error getting session stats: {stats_resp.error}")

data = stats_resp.data if isinstance(stats_resp.data, dict) else {}
return SkillResult.ok({
    "total_sessions": data.get("total_sessions", 0),
    "active_sessions": data.get("active_sessions", 0),
    "by_agent": data.get("by_agent", []),
    "by_type": data.get("by_type", []),
    "source": "engine_sessions_status",
})
```

### Fix 3 — Force structured work-cycle artifact output
**File:** `aria_mind/cron_jobs.yaml`  
**Lines:** 33-36 (`work_cycle` job)

**BEFORE**
```yaml
text: "Read HEARTBEAT.md work_cycle section (including RUNTIME PATH MAP). Use TOOL CALLS (aria-api-client, aria-health, etc.) for all operations — NOT exec commands. If you must exec run_skill.py, the ONLY correct path is: exec python3 skills/run_skill.py <skill> <function> '<args>'. NEVER use aria_mind/skills/run_skill.py (that path does not exist — aria_mind/ IS the workspace root). Check goals, pick highest priority, make progress, log activity, then run memory sync. After completion, log cron execution via api_client activity action='cron_execution' with details {'job':'work_cycle','estimated_tokens':150}."
```

**AFTER**
```yaml
text: "Read HEARTBEAT.md work_cycle section (including RUNTIME PATH MAP). Use TOOL CALLS (aria-api-client, aria-health, etc.) for all operations — NOT exec commands. If you must exec run_skill.py, the ONLY correct path is: exec python3 skills/run_skill.py <skill> <function> '<args>'. NEVER use aria_mind/skills/run_skill.py (that path does not exist — aria_mind/ IS the workspace root). Check goals, pick highest priority, make progress, log activity, then run memory sync. After completion, write ONE strict JSON artifact to aria_memories/logs/work_cycle_<YYYY-MM-DD_HHMM>.json with keys: timestamp, job, cycle.health_check, cycle.goal_check, cycle.agent_audit, cycle.memory_sync, cycle.artifact_log, summary. Do not write markdown into .json files. Then log cron execution via api_client activity action='cron_execution' with details {'job':'work_cycle','estimated_tokens':150}."
```

### Fix 4 — Align goal-priority ordering semantics
**File:** `src/api/routers/goals.py`  
**Line:** 69

**BEFORE**
```python
base = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc())
```

**AFTER**
```python
base = select(Goal).order_by(Goal.priority.desc(), Goal.created_at.desc())
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Changes keep DB access in API layer (`/sessions/stats`) and skill uses api_client only. |
| 2 | .env for secrets (zero in code) | ✅ | No secrets introduced; no `.env` edits. |
| 3 | models.yaml single source of truth | ✅ | Ticket does not introduce model-name constants. |
| 4 | Docker-first testing | ✅ | Verification includes docker-compose/local API checks. |
| 5 | aria_memories only writable path | ✅ | Artifact writes remain constrained to `aria_memories/`. |
| 6 | No soul modification | ✅ | No files in `aria_mind/soul/` touched. |

## Dependencies
- **None (blocking):** Ticket is non-duplicate and can run independently.
- **Recommended ordering:** Execute before analytics-heavy reporting (e.g., S-36) so dashboards consume consistent log/session data.

## Verification

> **Port setup — run once before all curl commands:**
> ```bash
> set -a && source stacks/brain/.env && set +a
> # Verify: echo $ARIA_API_PORT  → expected: 8000
> ```

```bash
# ── Fix 1: JSON validation guard ──────────────────────────────────────────

# 1a. Markdown content rejected for .json filename → must return 400
curl -sS -w "\nHTTP:%{http_code}" -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts" \
  -H "Content-Type: application/json" \
  -d '{"category":"logs","filename":"s39_bad.json","content":"# Not JSON\n- bullet"}' \
  | tee /tmp/s39_fix1a.txt | grep "HTTP:"
# EXPECTED: HTTP:400
grep -q 'Invalid JSON' /tmp/s39_fix1a.txt && echo 'PASS: error message correct' || echo 'FAIL'

# 1b. Valid JSON for .json filename → must return 200
curl -sS -w "\nHTTP:%{http_code}" -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts" \
  -H "Content-Type: application/json" \
  -d '{"category":"logs","filename":"s39_valid.json","content":"{\"ok\":true}"}' \
  | grep "HTTP:"
# EXPECTED: HTTP:200

# 1c. Markdown in .md file → still accepted (only .json gated)
curl -sS -w "\nHTTP:%{http_code}" -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts" \
  -H "Content-Type: application/json" \
  -d '{"category":"logs","filename":"s39_notes.md","content":"# Title\n- item"}' \
  | grep "HTTP:"
# EXPECTED: HTTP:200

# ── Fix 2: Session stats canonical source ─────────────────────────────────

# 2a. API stats endpoint returns active_sessions field
ARI_ACTIVE=$(curl -sS \
  "http://localhost:${ARIA_API_PORT:-8000}/api/sessions/stats?include_cron_events=true&include_runtime_events=true" \
  | jq '.active_sessions')
echo "API active_sessions: $ARI_ACTIVE"
# EXPECTED: a non-negative integer

# 2b. session_manager skill now returns source="engine_sessions_stats" (no longer local heuristics)
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/skills/session_manager/execute" \
  -H "Content-Type: application/json" \
  -d '{"function":"get_session_stats","args":{}}' \
  | jq -r '.result.source // .data.source'
# EXPECTED: engine_sessions_stats

# ── Fix 3: Cron prompt validation ─────────────────────────────────────────

# 3a. work_cycle text now contains strict JSON requirement
grep -c 'strict JSON artifact\|NEVER write Markdown into .json' aria_mind/cron_jobs.yaml
# EXPECTED: 1

# ── Fix 4: Goal ordering ──────────────────────────────────────────────────

# 4a. Goals API returns highest-priority-number items first
curl -sS "http://localhost:${ARIA_API_PORT:-8000}/api/goals?status=active&limit=5" \
  | jq 'if (.items | length) > 1 then (.items[0].priority >= .items[1].priority) else true end'
# EXPECTED: true

# 4b. Static grep confirms .desc() in goals router
grep -n 'priority.desc\|priority.asc' src/api/routers/goals.py
# EXPECTED: one line with priority.desc (no .asc)

# ── Unit tests ────────────────────────────────────────────────────────────

pytest tests/ -k "artifact or session_manager or goal" -v
# EXPECTED: all selected tests pass

# ── Cleanup test artifacts ─────────────────────────────────────────────────
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/logs/s39_bad.json"
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/logs/s39_valid.json"
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/logs/s39_notes.md"
```

### ARIA-to-ARIA Integration Test

> This test has Aria act on her own tools, then independently verifies the outcome via API (no SQL ever).

```bash
set -a && source stacks/brain/.env && set +a

# 1. Create an isolated test session
SESSION_ID=$(curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"[S-39 Integrity Integration Test]"}' \
  | jq -r '.id')
echo "Session: $SESSION_ID"

# 2. Ask Aria to write invalid JSON to a .json file
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-39 TEST] Use api_client__write_artifact to write the text `# Hello markdown` to filename `s39_aria_test.json` in category `logs`. Report the exact response status or error.","enable_tools":true}' \
  | jq -r '.content'
# EXPECTED: Aria reports a 400 error — Invalid JSON content

# 3. Ask Aria to write valid JSON to a .json file
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-39 TEST] Now use api_client__write_artifact to write valid JSON `{\"test\":true,\"ticket\":\"s39\"}` to filename `s39_aria_valid.json` in category `logs`. Report success or failure.","enable_tools":true}' \
  | jq -r '.content'
# EXPECTED: Aria confirms success and reports path

# 4. Verify independently via API (not SQL)
curl -sS "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/logs/s39_aria_valid.json" \
  | jq '{success,path,content}'
# EXPECTED: success=true, content contains {"test":true,"ticket":"s39"}

# 5. Ask Aria for session stats and verify source
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-39 TEST] Use session_manager__get_session_stats and tell me: (1) the active_sessions count and (2) the source field in the result.","enable_tools":true}' \
  | jq -r '.content'
# EXPECTED: Aria reports an integer for active_sessions and source=engine_sessions_stats

# 6. Cross-check stats against authoritative API (no SQL)
API_ACTIVE=$(curl -sS "http://localhost:${ARIA_API_PORT:-8000}/api/sessions/stats" | jq '.active_sessions')
echo "Authoritative API active_sessions: $API_ACTIVE (should match what Aria reported)"

# 7. Ask Aria how she feels about the guardrails
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-39 REFLECTION] The integrity guardrails are now in place. How do you feel about having proper JSON validation on your work-cycle artifacts? Do you think this will improve your self-auditing?","enable_tools":false}' \
  | jq -r '.content'

# 8. Clean up test session and artifacts
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}"
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/logs/s39_aria_valid.json"
```

## Prompt for Agent

You are implementing sprint ticket **S-39: Work-Cycle Log Integrity Guardrails** for the Aria project.

### Architecture Constraint Reminder
Aria uses a strict 5-layer architecture: `Database ↔ SQLAlchemy ORM ↔ FastAPI API ↔ api_client (httpx) ↔ Skills ↔ Agents`. No skill may use raw SQL or import SQLAlchemy. All DB reads go through REST API endpoints. Configuration lives in `stacks/brain/.env`.

Before any curl command: `set -a && source stacks/brain/.env && set +a`

### Files to Read First (exact line ranges)
1. `src/api/routers/artifacts.py` lines 1–90 — locate `ArtifactWriteRequest` (~lines 46–50) and `write_artifact()` (~lines 53–85); note the `with open(filepath, "w")` line (~73)
2. `aria_skills/session_manager/__init__.py` lines 240–285 — full `get_session_stats()` with stale-heuristic counting (`len(sessions) - stale_count` pattern)
3. `src/api/routers/sessions.py` lines 242–330 — `GET /sessions/stats` handler; response: `{total_sessions, active_sessions, by_agent, by_status, by_type, total_tokens, total_cost}`
4. `aria_mind/cron_jobs.yaml` lines 20–50 — `work_cycle` job; note the `text:` field (~line 36)
5. `src/api/routers/goals.py` lines 55–80 — `select(Goal).order_by(Goal.priority.asc()...)` (~line 69)
6. `aria_engine/prompts.py` lines 288–300 — `.order_by(Goal.priority.desc())` (~lines 293–295)
7. `tests/` — grep for existing artifact, session_manager, goal test files

### Exact Implementation Steps

**Step 1 — `src/api/routers/artifacts.py` line ~71–73: JSON validation guard**

Find `filepath = folder / body.filename` followed immediately by `with open(filepath, "w", encoding="utf-8") as f:`. Insert between them:
```python
if body.filename.lower().endswith(".json"):
    try:
        json.loads(body.content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON content for '{body.filename}': {exc.msg} (line {exc.lineno}, col {exc.colno})",
        )
```
`json` is already imported at line 8 — do NOT add a new import.

**Step 2 — `aria_skills/session_manager/__init__.py` lines 240–283: Replace `get_session_stats()`**

Replace the entire method body (keep the `@logged_method()` decorator and `async def` line, replace everything inside):
```python
    async def get_session_stats(self, **kwargs) -> SkillResult:
        """Get session statistics from the authoritative /sessions/stats API.

        Uses DB status-based counts (status='active'), not timestamp heuristics.
        ARCHITECTURE: calls /sessions/stats via api_client — never raw SQL.
        """
        try:
            result = await self._api.get(
                "/sessions/stats",
                params={
                    "include_cron_events": kwargs.get("include_cron_events", True),
                    "include_runtime_events": kwargs.get("include_runtime_events", True),
                },
            )
            if not result.success:
                return SkillResult.fail(f"Error getting session stats: {result.error}")
            data = result.data if isinstance(result.data, dict) else {}
            return SkillResult.ok({
                "total_sessions": data.get("total_sessions", 0),
                "active_sessions": data.get("active_sessions", 0),
                "total_tokens": data.get("total_tokens", 0),
                "total_cost": data.get("total_cost", 0.0),
                "by_agent": data.get("by_agent", []),
                "by_status": data.get("by_status", []),
                "by_type": data.get("by_type", []),
                "source": "engine_sessions_stats",
            })
        except Exception as e:
            return SkillResult.fail(f"Error getting session stats: {e}")
```

**Step 3 — `aria_mind/cron_jobs.yaml` ~line 36: Add JSON schema requirement**

Find the `work_cycle` job `text:` field. Append to the existing text value (before the closing `"`): `" After completion, write ONE strict JSON artifact to category='logs', filename='work_cycle_<YYYY-MM-DD_HHMM>.json' with schema: {timestamp, job, health_check:{status,notes}, goal_check:{goal,progress}, agent_audit:{total,active}, memory_sync:{synced}, artifact_log:{written}, summary}. NEVER write Markdown into .json files."`

Do NOT change `every`, `agent`, `session`, or `delivery` fields.

**Step 4 — `src/api/routers/goals.py` line ~69: Fix sort direction**

Change: `Goal.priority.asc()` → `Goal.priority.desc()`

This aligns with `aria_engine/prompts.py` line ~294 which already uses `.desc()`.

**Step 5 — Write tests**

Add to appropriate test file:
```python
def test_write_artifact_rejects_markdown_in_json(client, tmp_path):
    with patch("routers.artifacts.ARIA_MEMORIES_PATH", tmp_path / "memories"):
        r = client.post("/artifacts", json={"content": "# Not JSON", "filename": "test.json", "category": "logs"})
    assert r.status_code == 400
    assert "Invalid JSON" in r.json()["detail"]

def test_write_artifact_accepts_valid_json(client, tmp_path):
    with patch("routers.artifacts.ARIA_MEMORIES_PATH", tmp_path / "memories"):
        r = client.post("/artifacts", json={"content": '{"ok": true}', "filename": "test.json", "category": "logs"})
    assert r.status_code == 200

def test_get_session_stats_returns_canonical_source(session_manager_skill):
    # Mock _api.get to return what /sessions/stats would return
    mock_result = SkillResult.ok({"total_sessions": 5, "active_sessions": 3, "by_agent": [], "by_status": [], "by_type": [], "total_tokens": 100, "total_cost": 0.01})
    session_manager_skill._api.get = AsyncMock(return_value=mock_result)
    result = await session_manager_skill.get_session_stats()
    assert result.data["source"] == "engine_sessions_stats"
    assert result.data["active_sessions"] == 3
```

**Step 6 — Unit tests**
```bash
pytest tests/ -k "artifact or session_manager or goal" -v
# All must pass
```

**Step 7 — ARIA-to-ARIA integration test**

Run the full **ARIA-to-ARIA Integration Test** section:
- Step 2 must show Aria self-reporting a 400 error for markdown-in-json
- Step 5 must show Aria reporting `source=engine_sessions_stats`
- Capture and paste exact outputs

**Step 8 — `tasks/lessons.md`**
```
S-39 (2026-02-27): JSON validation must be enforced at the API write layer for
.json artifacts — cannot rely on caller discipline. Session stats must come from
/sessions/stats (DB status field), never timestamp-heuristic counting from skill
layer. Goal priority ordering must use .desc() in both prompts.py and goals.py —
mismatched directions silently corrupt autonomous goal prioritization.
```

### Hard Constraints (all 6)
- [ ] #1: No raw SQL or SQLAlchemy in skills; all DB access via REST API
- [ ] #2: No secrets in code; source `stacks/brain/.env` for ports
- [ ] #3: No model name constants (n/a to this ticket)
- [ ] #4: Test in Docker Compose stack
- [ ] #5: Writes only to `aria_memories/`
- [ ] #6: No soul files modified

### Definition of Done
- [ ] `.json` artifacts return HTTP 400 for non-JSON content
- [ ] `get_session_stats()` returns `source="engine_sessions_stats"` matching `/sessions/stats` count
- [ ] `work_cycle` cron prompt includes JSON schema + anti-markdown instruction
- [ ] `goals.py` sort is `.desc()` matching `prompts.py`
- [ ] All unit tests pass
- [ ] ARIA-to-ARIA integration test passes (8 steps)
- [ ] `tasks/lessons.md` updated
