# S-40: Artifact Path Resolution for Sub-Agents
**Epic:** E19 — Session & Artifact Integrity | **Priority:** P1 | **Points:** 3 | **Phase:** 1

## Problem
Sub-agent artifact lookups can return false `404 Not Found` or false-empty conclusions when nested artifact paths are requested with incomplete filenames.

Verified code evidence:
- `src/api/routers/artifacts.py` line 91 defines read route as `/artifacts/{category}/{filename:path}`.
- `src/api/routers/artifacts.py` line 96 resolves reads as `ARIA_MEMORIES_PATH / category / filename`.
- For artifacts stored at `aria_memories/memory/logs/*.json`, the read filename must include `logs/...` when category is `memory`.
- `aria_skills/api_client/__init__.py` line 1649 exposes `read_artifact(category, filename)` and passes `filename` directly to `/artifacts/{category}/{filename}` (line 1652), with no guard/help for nested-path cases.
- `aria_mind/MEMORY.md` lines 89-90 documents endpoint shape but does not explicitly call out nested-path usage examples for category + subfolder reads.

Observed runtime symptom pattern (from sub-agent execution transcript):
- Reads attempted as `/api/artifacts/memory/work_cycle_*.json` returned 404.
- Later reads succeeded when target existed under `memory/logs/`.
- This creates misleading “file missing” conclusions during autonomous investigations.

## Root Cause
1. API behavior is correct but strict: nested paths require explicit subpath in `filename:path`.
2. `api_client.read_artifact()` offers no helper that consumes canonical `path` from `list_artifacts()` and replays safe reads.
3. Documentation lacks a concrete nested-path example (e.g., category `memory`, filename `logs/work_cycle_*.json`), increasing operator/sub-agent error rate.

## Fix

### Fix 1 — Add read-by-path helper in api_client skill
**File:** `aria_skills/api_client/__init__.py`  
**Lines:** around 1649-1675

**BEFORE**
```python
async def read_artifact(self, category: str, filename: str) -> SkillResult:
    """Read a file artifact from aria_memories/<category>/<filename>."""
    try:
        resp = await self._client.get(f"/artifacts/{category}/{filename}")
        resp.raise_for_status()
        return SkillResult.ok(resp.json())
    except Exception as e:
        return SkillResult.fail(f"Failed to read artifact: {e}")
```

**AFTER**
```python
async def read_artifact(self, category: str, filename: str) -> SkillResult:
    """Read a file artifact from aria_memories/<category>/<filename>."""
    try:
        resp = await self._client.get(f"/artifacts/{category}/{filename}")
        resp.raise_for_status()
        return SkillResult.ok(resp.json())
    except Exception as e:
        return SkillResult.fail(f"Failed to read artifact: {e}")

async def read_artifact_by_path(self, path: str) -> SkillResult:
    """Read an artifact using canonical list_artifacts path, e.g. memory/logs/file.json."""
    try:
        clean = path.strip("/")
        if "/" not in clean:
            return SkillResult.fail("Path must include category and filename")
        category, filename = clean.split("/", 1)
        return await self.read_artifact(category=category, filename=filename)
    except Exception as e:
        return SkillResult.fail(f"Failed to read artifact by path: {e}")
```

### Fix 2 — Clarify nested-path contract in MEMORY.md
**File:** `aria_mind/MEMORY.md`  
**Lines:** 89-90 and below table

**BEFORE**
```markdown
| `/artifacts/{category}/{filename}` | GET | `api_client__read_artifact` | Read a file |
```

**AFTER**
```markdown
| `/artifacts/{category}/{filename:path}` | GET | `api_client__read_artifact` | Read a file (filename may include subfolders) |

Example:
- For `aria_memories/memory/logs/work_cycle_2026-02-27_0416.json`
- Use `category=memory` and `filename=logs/work_cycle_2026-02-27_0416.json`
```

### Fix 3 — Add regression tests for nested artifact read path
**File:** `tests/test_artifacts_router.py`

**BEFORE**
```python
def test_read_artifact_success(client, tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "test.log").write_text("line1\nline2")
    with patch("routers.artifacts.ARIA_MEMORIES_PATH", tmp_path):
        resp = client.get("/artifacts/logs/test.log")
```

**AFTER**
```python
def test_read_artifact_nested_path_success(client, tmp_path):
    (tmp_path / "memory" / "logs").mkdir(parents=True)
    (tmp_path / "memory" / "logs" / "work_cycle_2026-02-27_0416.json").write_text('{"ok": true}')
    with patch("routers.artifacts.ARIA_MEMORIES_PATH", tmp_path):
        resp = client.get("/artifacts/memory/logs/work_cycle_2026-02-27_0416.json")
    assert resp.status_code == 200
    assert resp.json()["path"] == "memory/logs/work_cycle_2026-02-27_0416.json"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Changes are API + api_client + docs/tests only; no cross-layer violation. |
| 2 | .env for secrets (zero in code) | ✅ | No secrets introduced or moved. |
| 3 | models.yaml single source of truth | ✅ | No model-name logic involved. |
| 4 | Docker-first testing | ✅ | Verification uses API routes and pytest in local compose/venv. |
| 5 | aria_memories only writable path | ✅ | Artifact logic still constrained to allowed categories under aria_memories. |
| 6 | No soul modification | ✅ | No soul files touched. |

## Dependencies
- **S-39 recommended first**: S-39 hardens artifact payload integrity; S-40 hardens artifact path retrieval ergonomics and docs/tests.
- No blocking dependencies otherwise.

## Verification

> **Port setup — run once before all curl commands:**
> ```bash
> set -a && source stacks/brain/.env && set +a
> # Verify: echo $ARIA_API_PORT  → expected: 8000
> ```

```bash
# ── Fix 1: read_artifact_by_path helper ───────────────────────────────────

# 1a. Helper exists in api_client
grep -n 'def read_artifact_by_path' aria_skills/api_client/__init__.py
# EXPECTED: one line showing async def read_artifact_by_path(self, path: str)

# 1b. Write a nested artifact first (create test file)
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts" \
  -H "Content-Type: application/json" \
  -d '{"content":"{\"source\":\"s40_test\"}","filename":"logs/s40_nested_test.json","category":"memory","subfolder":"logs"}' \
  | jq -e '.success == true'
# EXPECTED: true

# 1c. Read via nested path through REST route
curl -sS \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/memory/logs/s40_nested_test.json" \
  | jq -r '.success'
# EXPECTED: true

# 1d. Path field in response includes subfolder
curl -sS \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/memory/logs/s40_nested_test.json" \
  | jq -r '.path'
# EXPECTED: memory/logs/s40_nested_test.json

# ── Fix 2: MEMORY.md documentation ────────────────────────────────────────

# 2a. MEMORY.md now shows filename:path and nested example
grep -c 'filename:path\|nested\|logs/work_cycle' aria_mind/MEMORY.md
# EXPECTED: at least 2 matches

# ── Fix 3: Regression tests ───────────────────────────────────────────────

# 3a. Nested path router tests pass
pytest tests/ -k "nested_path or read_artifact_by_path" -v
# EXPECTED: selected tests pass

# 3b. Full api_client artifact tests pass
pytest tests/ -k "artifact" -v
# EXPECTED: all pass

# ── Cleanup ────────────────────────────────────────────────────────────────
curl -sS -X DELETE \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/memory/logs/s40_nested_test.json"
```

### ARIA-to-ARIA Integration Test

> Have Aria list, then read a real nested artifact using the new helper, then reflect.

```bash
set -a && source stacks/brain/.env && set +a

# 1. Create test session
SESSION_ID=$(curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"[S-40 Path Resolution Test]"}' \
  | jq -r '.id')
echo "Session: $SESSION_ID"

# 2. Ask Aria to write a nested artifact
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-40 TEST] Use api_client__write_artifact to write {\"s40\": true} to filename=\"logs/s40_aria_path_test.json\" in category=\"memory\". Tell me the path returned.","enable_tools":true}' \
  | jq -r '.content'
# EXPECTED: Aria reports path = memory/logs/s40_aria_path_test.json

# 3. Ask Aria to list artifacts in memory category
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-40 TEST] Use api_client__list_artifacts with category=memory to list artifacts. Find the path for the file containing s40_aria_path_test.json and tell me its exact path value.","enable_tools":true}' \
  | jq -r '.content'
# EXPECTED: Aria finds and reports path = memory/logs/s40_aria_path_test.json

# 4. Ask Aria to read it back by path using the new helper
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-40 TEST] Now use api_client__read_artifact_by_path with path=\"memory/logs/s40_aria_path_test.json\" to read back the file. Tell me the content.","enable_tools":true}' \
  | jq -r '.content'
# EXPECTED: Aria reports content {"s40": true}

# 5. Verify independently via REST (no SQL)
curl -sS \
  "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/memory/logs/s40_aria_path_test.json" \
  | jq '{success,path,content}'
# EXPECTED: success=true, path=memory/logs/s40_aria_path_test.json

# 6. Ask Aria how she feels about nested path resolution
curl -sS -X POST \
  "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"[S-40 REFLECTION] You just successfully used read_artifact_by_path to navigate your own nested memory structure. How does it feel to have a more reliable path resolution tool? Will this help you avoid the false 404 errors you were getting before?","enable_tools":false}' \
  | jq -r '.content'

# 7. Clean up
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/engine/chat/sessions/${SESSION_ID}"
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT:-8000}/api/artifacts/memory/logs/s40_aria_path_test.json"
```

## Prompt for Agent

You are implementing sprint ticket **S-40: Artifact Path Resolution for Sub-Agents** for the Aria project.

### Architecture Constraint Reminder
Aria uses a strict 5-layer architecture: `Database ↔ SQLAlchemy ORM ↔ FastAPI API ↔ api_client (httpx) ↔ Skills ↔ Agents`. No skill may access the filesystem directly or use raw SQL. The new `read_artifact_by_path()` helper must live in the `api_client` skill and call the FastAPI REST layer only. Configuration (ports) lives in `stacks/brain/.env`.

Before any curl command: `set -a && source stacks/brain/.env && set +a`

### Files to Read First (exact ranges)
1. `src/api/routers/artifacts.py` lines 88–125 — confirm route `@router.get("/artifacts/{category}/{filename:path}")` and how `ARIA_MEMORIES_PATH / category / filename` resolves (~line 96)
2. `aria_skills/api_client/__init__.py` lines 1640–1690 — read `write_artifact()`, `read_artifact()` (line 1649), `list_artifacts()` (line 1658); insertion point for new method is between lines 1657 and 1658
3. `aria_mind/MEMORY.md` lines 83–110 — find endpoint table (~line 89); note that `read_artifact` row shows `{filename}` not `{filename:path}` and lacks nested examples
4. `tests/` — grep for artifact router tests and api_client skill tests to understand fixture patterns

### Exact Implementation Steps

**Step 1 — `aria_skills/api_client/__init__.py` after line 1657: Add `read_artifact_by_path()`**

Insert this method after `read_artifact()` ends (~line 1657), before `list_artifacts` (~line 1658):
```python
    async def read_artifact_by_path(self, path: str) -> SkillResult:
        """Read an artifact using its canonical list path, e.g. 'memory/logs/file.json'.

        Splits path into category + filename components and calls read_artifact().
        Use this when you have a `path` value from list_artifacts() response.

        Args:
            path: Full path relative to aria_memories/, e.g. 'memory/logs/file.json'

        Returns:
            SkillResult with artifact content or failure if path format is invalid.

        Architecture: calls self.read_artifact() only — never touches filesystem directly.
        """
        try:
            clean = path.strip("/")
            if not clean or "/" not in clean:
                return SkillResult.fail(
                    f"Path '{path}' must include category and filename, "
                    "e.g. 'memory/logs/file.json'"
                )
            category, filename = clean.split("/", 1)
            return await self.read_artifact(category=category, filename=filename)
        except Exception as e:
            return SkillResult.fail(f"Failed to read artifact by path: {e}")
```

**Step 2 — `aria_mind/MEMORY.md` line ~89: Update endpoint table and add examples**

Find: `| /artifacts/{category}/{filename} | GET | api_client__read_artifact | Read a file |`

Replace with:
```markdown
| `/artifacts/{category}/{filename:path}` | GET | `api_client__read_artifact` | Read a file (filename may include subfolder path) |
| *(convenience)* | — | `api_client__read_artifact_by_path` | Read using canonical `path` from `list_artifacts` result |
```

Add below the table:
```markdown
> **Nested path example:**
> For `aria_memories/memory/logs/work_cycle_2026-02-27.json`, use:
> - `api_client__read_artifact(category="memory", filename="logs/work_cycle_2026-02-27.json")`
> - Or: `api_client__read_artifact_by_path(path="memory/logs/work_cycle_2026-02-27.json")`
>
> **⚠ Never** try `/api/artifacts/memory/work_cycle_2026-02-27.json` — the file lives
> under `logs/`; omitting the subfolder returns 404.
```

**Step 3 — `tests/`: Add regression tests**

```python
def test_read_artifact_nested_path_success(client, tmp_path):
    (tmp_path / "memory" / "logs").mkdir(parents=True)
    (tmp_path / "memory" / "logs" / "work_cycle_test.json").write_text('{"ok": true}')
    with patch("routers.artifacts.ARIA_MEMORIES_PATH", tmp_path):
        resp = client.get("/artifacts/memory/logs/work_cycle_test.json")
    assert resp.status_code == 200
    assert resp.json()["path"] == "memory/logs/work_cycle_test.json"

async def test_read_artifact_by_path_splits_correctly(api_client_skill):
    api_client_skill.read_artifact = AsyncMock(return_value=SkillResult.ok({"content": "ok"}))
    result = await api_client_skill.read_artifact_by_path("memory/logs/test.json")
    api_client_skill.read_artifact.assert_called_once_with(
        category="memory", filename="logs/test.json"
    )
    assert result.success

async def test_read_artifact_by_path_flat_path_fails(api_client_skill):
    result = await api_client_skill.read_artifact_by_path("just_a_filename.json")
    assert not result.success
    assert "must include category and filename" in result.error
```

**Step 4 — Run unit tests**
```bash
pytest tests/ -k "artifact or nested_path or read_artifact_by_path" -v
# All must pass
```

**Step 5 — Run ARIA-to-ARIA integration test**
Run every step in the **ARIA-to-ARIA Integration Test** section above.
Capture and verify:
- Step 2: Aria writes to `memory/logs/s40_aria_path_test.json`
- Step 4: Aria reads it back using `api_client__read_artifact_by_path` and reports content `{"s40": true}`
- Step 5: Independent REST verification confirms `success=true` and correct path

**Step 6 — Update `tasks/lessons.md`**
```
S-40 (2026-02-27): FastAPI {filename:path} captures nested paths correctly.
Always use read_artifact_by_path() when consuming `path` values from list_artifacts()
results — never assume a flat filename. Document nested-path semantics in MEMORY.md.
Sub-agents getting 404 on nested artifacts almost always means the subfolder was
omitted from the filename parameter.
```

### Hard Constraints
- [ ] #1: `read_artifact_by_path()` only calls `self.read_artifact()` — no direct filesystem access
- [ ] #2: No secrets in code; source `stacks/brain/.env` for ports
- [ ] #3: No model name constants (n/a)
- [ ] #4: Test in Docker Compose stack
- [ ] #5: Test artifact written to `aria_memories/memory/logs/` — within allowed paths
- [ ] #6: `MEMORY.md` is in `aria_mind/` as documentation — not a soul file; update permitted

### Definition of Done
- [ ] `read_artifact_by_path(path)` added to `api_client` between `read_artifact()` and `list_artifacts()`
- [ ] Method delegates to `read_artifact()` only — never accesses filesystem directly
- [ ] Method returns descriptive error for flat paths (no `/`)
- [ ] `MEMORY.md` updated: `:path` notation, new helper row, nested-path example with warning
- [ ] Regression tests: nested route (200 + correct path field), path split test, flat-path error test
- [ ] All unit tests pass
- [ ] ARIA-to-ARIA test: Aria reads nested artifact via `read_artifact_by_path` in step 4
- [ ] `tasks/lessons.md` updated
