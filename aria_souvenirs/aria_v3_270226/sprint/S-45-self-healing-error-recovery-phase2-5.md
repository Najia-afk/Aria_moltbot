# S-45: Self-Healing Error Recovery — Phase 2 Through 5 (Complete)
**Epic:** E20 — Resilience & Recovery | **Priority:** P1 | **Points:** 5 | **Phase:** 2  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

---

## Problem

Aria's `api_client` skill has a partial resilience layer (Phase 1 at ~25–70% depending on source):

**What exists:**
- ✅ `_is_circuit_open()` / `_record_failure()` / `_record_success()` — circuit breaker
- ✅ `_request_with_retry()` — exponential backoff with jitter
- ✅ Generic HTTP verbs (`get`, `post`, `patch`, `put`, `delete`) use `_request_with_retry`
- ✅ `retry_engine.py` + `error_classifier.py` at `aria_memories/exports/` (preserved in this sprint's souvenir)

**What's missing:**
- ❌ **20+ specific endpoint methods** still use direct `httpx` calls bypassing retry logic:  
  `get_activities`, `create_activity`, `get_security_events`, `create_security_event`,
  `get_thoughts`, `create_thought`, `get_goals`, `update_goal`, `get_memories`, `set_memory`,
  `get_heartbeats`, `create_heartbeat`, `get_sessions`, `create_session`, `get_artifacts`,
  `create_artifact`, `get_work_cycles`, `create_work_cycle`, `update_work_cycle`,
  `get_schedules`, `create_schedule`, `delete_schedule`, and all `search_*` methods
- ❌ No LLM fallback chain in `aria-llm` skill (primary: qwen3-mlx → fallback 1: trinity-free → fallback 2: qwen3-next-free)
- ❌ No health degradation modes in `aria-health` skill
- ❌ No chaos/integration tests for circuit breaker behavior

Evidence from `aria_souvenirs/aria_v3_270226/plans/self_healing_error_recovery.md`:
> "Many specific endpoint methods bypass `_request_with_retry` and use direct `httpx` calls"

Evidence from `aria_souvenirs/aria_v3_270226/plans/self_healing_progress_2026-02-20.md`:
> RetryEngine at `aria_memories/exports/retry_engine.py` is production-ready but not yet integrated with skills.

**Impact:** A single endpoint outage cascades — `create_activity` fails → heartbeat fails → work cycle logs lost → no trace for debugging.

### Problem Table

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `aria_skills/api_client/__init__.py` | ~50 methods | 20+ endpoint methods bypass `_request_with_retry` using direct `httpx.AsyncClient()` | 🔴 Critical |
| `aria_skills/llm/__init__.py` | — | No LLM fallback chain — single model, no circuit-breaker per model | ⚠️ High |
| `aria_skills/health/__init__.py` | — | No health degradation levels — crons continue at full rate when system degraded | ⚠️ Medium |
| `tests/` | — | No chaos/integration tests for circuit breaker behavior | ⚠️ Medium |

### Root Cause Table

| Symptom | Root Cause |
|---------|------------|
| `create_activity` fails without retry when API is slow | `api_client.create_activity()` uses `httpx.AsyncClient()` directly, bypassing `_request_with_retry()` |
| Single API outage cascades to full heartbeat failure | Each endpoint method is an independent HTTP call — no shared retry/circuit-breaker wrapper |
| LLM timeouts crash the work cycle | No fallback model chain — single model, no circuit breaker |
| Full cron load continues during degraded API | No health degradation levels to suspend non-critical crons |

---

## Fix

### Phase 2 — Migrate all api_client endpoint methods (50%)

**File:** `aria_skills/api_client/__init__.py`

For every specific endpoint method that currently does:
```python
async def create_activity(self, ...) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{self._base}/activities", json=payload)
        resp.raise_for_status()
        return resp.json()
```

Replace with:
```python
async def create_activity(self, ...) -> dict:
    return await self.post("/activities", json=payload)
    # self.post() already uses _request_with_retry with circuit breaker
```

**Priority order for migration:**
1. `create_activity` — most critical (called every heartbeat)
2. `get_goals` + `update_goal` — called every work_cycle  
3. `create_heartbeat` + `get_heartbeats` — just patched in S-42
4. `get_memories` + `set_memory` — deep memory access
5. All remaining 15+ methods

### Phase 3 — LLM Fallback Chain (75%)

**File:** `aria_skills/llm/__init__.py` (or equivalent LLM skill file)

Add fallback chain:
```python
LLM_FALLBACK_CHAIN = [
    {"model": "qwen3-mlx",      "type": "local",  "priority": 1},
    {"model": "trinity-free",   "type": "cloud",  "priority": 2},
    {"model": "qwen3-next-free","type": "cloud",  "priority": 3},
]

async def complete_with_fallback(self, messages: list, **kwargs) -> dict:
    """Try each model in fallback chain. Circuit breaker per endpoint."""
    for model_cfg in LLM_FALLBACK_CHAIN:
        if self._is_circuit_open(model_cfg["model"]):
            continue
        try:
            result = await self._complete_with_model(model_cfg["model"], messages, **kwargs)
            self._record_success(model_cfg["model"])
            return result
        except Exception as e:
            self._record_failure(model_cfg["model"])
            logger.warning("LLM %s failed, trying next: %s", model_cfg["model"], e)
    raise RuntimeError("All LLM models in fallback chain unavailable")
```

### Phase 4 — Health Degradation Modes (90%)

**File:** `aria_skills/health/__init__.py`

Add degradation tiers:
```python
class HealthDegradationLevel(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"      # 1-2 subsystems failing, core ops continue
    CRITICAL = "critical"      # 3+ subsystems failing, emergency mode
    RECOVERY = "recovery"      # Active recovery cycle running

async def check_degradation_level(self) -> HealthDegradationLevel:
    failing = sum(1 for s in await self.check_all_subsystems() if not s["healthy"])
    if failing == 0: return HealthDegradationLevel.HEALTHY
    if failing <= 2: return HealthDegradationLevel.DEGRADED
    return HealthDegradationLevel.CRITICAL

async def apply_degradation_mode(self, level: HealthDegradationLevel) -> None:
    """Disable non-essential features when degraded."""
    if level == HealthDegradationLevel.DEGRADED:
        # Suspend: moltbook_check, social_post
        # Continue: work_cycle, heartbeat, goals
        pass
    elif level == HealthDegradationLevel.CRITICAL:
        # Suspend: all cron except health_check
        # Alert Najia via fallback channel
        pass
```

### Phase 5 — Chaos Tests (100%)

**File:** `tests/test_self_healing.py`

Test scenarios:
```python
async def test_circuit_breaker_opens_after_5_failures():
    """Circuit opens, subsequent calls return cached/fallback immediately."""

async def test_retry_with_exponential_backoff():
    """Simulated 503 → retries with correct delay schedule."""

async def test_llm_fallback_chain_skips_open_circuit():
    """qwen3-mlx circuit open → skips to trinity-free without error."""

async def test_activity_logging_resilient_to_db_restart():
    """create_activity retries when API briefly unavailable."""
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | All changes in Skills layer only |
| 2 | `stacks/brain/.env` for all ports/secrets | ✅ | `$ARIA_API_PORT` in all verifications |
| 3 | No direct SQL / no `psql` | ✅ | Resilience is at HTTP client level |
| 4 | Docker-first testing | ✅ | Must test against live `aria-api` container |
| 5 | models.yaml for model references | ✅ | Fallback chain model names from models.yaml |
| 6 | `aria_memories/` only writable path | ✅ | No writeable files outside memories |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `SKILLS.md` | Self-Healing section | Phase 1 described only — no Phase 2-5 scope | Updated: Phase 2-5 adds retry migration, LLM fallback chain, health degradation levels, chaos tests |
| `CHANGELOG.md` | — | No S-45 entry | `- **S-45 (E20):** Self-Healing Phase 2-5 — api_client retry migration, LLM fallback chain, health degradation levels, chaos tests` |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. All critical methods use _request_with_retry (not direct httpx)
grep -n "httpx.AsyncClient\(\)" aria_skills/api_client/__init__.py \
  | grep -v "_request_with_retry\|def _request_with_retry"
# EXPECTED: 0 or only the internal retry method itself

# 2. Circuit breaker is per-model in LLM skill
grep -n "_is_circuit_open\|_record_failure\|_record_success" aria_skills/llm/__init__.py 2>/dev/null \
  || grep -rn "_is_circuit_open" aria_skills/
# EXPECTED: matches in LLM skill file

# 3. Health degradation levels defined
grep -n "DEGRADED\|CRITICAL\|RECOVERY\|HealthDegradationLevel" aria_skills/health/__init__.py 2>/dev/null
# EXPECTED: at least DEGRADED and CRITICAL defined

# 4. Tests exist
ls tests/test_self_healing.py
# EXPECTED: file exists

# 5. API healthy
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"

# 6. create_activity survives retry (simulate 1 bad call, confirm success)
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from aria_skills.api_client import get_api_client

async def test():
    api = await get_api_client()
    result = await api.create_activity(action='selfheal_test', details={'test': True})
    print('OK:', result.get('id','?'))

asyncio.run(test())
"
# EXPECTED: prints OK: <uuid>
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-45 self-healing validation"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Ask Aria about resilience
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read aria_skills/api_client/__init__.py. Tell me: (1) Does create_activity now use _request_with_retry? (2) How many methods still use direct httpx? (3) What is the circuit breaker threshold?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms create_activity uses retry, reports 0 direct httpx methods, cites threshold

# Step 3 — Ask Aria to simulate a degraded scenario
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read the health degradation modes in aria_skills/health/__init__.py. Describe what happens to Aria when the system enters DEGRADED mode vs CRITICAL mode. Which cron jobs get suspended?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria describes mode behavior accurately from the code

# Step 4 — Ask Aria to log a self-healing test activity
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Use aria-api-client to log a test activity with action=selfheal_s45_test and details={\"phase\":\"complete\",\"method\":\"create_activity\"}.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria calls create_activity, returns success

# Step 5 — Verify activity was logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=selfheal_s45_test&limit=1" \
  | jq '.[0] | {action, success, created_at}'
# EXPECTED: action=selfheal_s45_test, success=true

# Step 6 — Ask how Aria feels about being more resilient
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: How does having retry + circuit breaker on every api_client method change your experience of running work cycles? What happens now when the DB goes down briefly?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria describes continuity over fragility, retries silently logging

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-45 Self-Healing Error Recovery (Phase 2 through 5). Total changes: 4 files.**

### Architecture Constraints
- `api_client` is in the **Skills** layer — only HTTP-level changes, no DB schema
- Port: `stacks/brain/.env` → `$ARIA_API_PORT` — use in all tests
- All endpoint methods must use `self.post()` / `self.get()` etc. (which call `_request_with_retry`)
- Never add direct SQL; circuit breaker + retry operate at HTTP level only
- model names must match `aria_models/models.yaml`

### Files to Read First
1. `aria_skills/api_client/__init__.py` — full file, focus on:
   - `_request_with_retry()` method (the target all methods should call)
   - All specific endpoint methods that use `httpx.AsyncClient()` directly
2. `aria_souvenirs/aria_v3_270226/plans/self_healing_error_recovery.md` — gap analysis
3. `aria_souvenirs/aria_v3_270226/plans/self_healing_progress_2026-02-20.md` — prior work
4. `aria_models/models.yaml` — available models for fallback chain
5. `aria_skills/llm/__init__.py` — if it exists, understand current LLM call pattern
6. `aria_skills/health/__init__.py` — current health skill structure

### Steps — Phase 2
1. Read all files above
2. For each method in the priority list that has `httpx.AsyncClient()`:
   - Change body to `return await self.post(...)` (or `.get()`, etc.)
   - Remove the local `httpx` import if it's only used in that method
3. Priority order: `create_activity` → `get_goals`+`update_goal` → `create_heartbeat` → all others
4. After migrating all high-priority methods, globally search for remaining `httpx.AsyncClient()` calls in aria_skills/api_client/__init__.py and migrate each

### Steps — Phase 3
5. Open `aria_skills/llm/__init__.py` (or find the LLM gateway)
6. Add `LLM_FALLBACK_CHAIN` list referencing models from `aria_models/models.yaml`
7. Add `complete_with_fallback()` method with circuit breaker per model
8. Update any existing `complete()` or `chat()` method to call `complete_with_fallback()`

### Steps — Phase 4
9. Open `aria_skills/health/__init__.py`
10. Add `HealthDegradationLevel` enum
11. Add `check_degradation_level()` → count failing subsystems
12. Add `apply_degradation_mode()` → suspension logic per level
13. Add call to `check_degradation_level()` in `health_check_all()`

### Steps — Phase 5
14. Create `tests/test_self_healing.py` with the 4 test cases in the Fix section above
15. Run `pytest tests/test_self_healing.py -v` and confirm all pass

### Steps — Wrap Up
16. Run full verification block
17. Run ARIA-to-ARIA integration test (Steps 1-6)
18. **Update `SKILLS.md`** Self-Healing section: document Phase 2-5 scope (retry migration, LLM fallback chain, health degradation, chaos tests)
19. **Update `CHANGELOG.md`**: append `- **S-45 (E20):** Self-Healing Phase 2-5 — api_client retry migration, LLM fallback chain, health degradation levels, chaos tests`
20. Update SPRINT_OVERVIEW.md to mark S-45 Done
21. Append lesson to `tasks/lessons.md`: what pattern was established for resilient methods

### Hard Constraints Checklist
- [ ] Zero direct `httpx.AsyncClient()` in specific endpoint methods (only inside `_request_with_retry`)
- [ ] LLM fallback chain is circuit-breaker-aware (skips open circuits)
- [ ] Health degradation suspends non-critical crons, never disables heartbeat
- [ ] No changes to DB schema or ORM models
- [ ] All tests use mock/stub — no production data mutation in test suite
- [ ] Port is always from `$ARIA_API_PORT`

### Definition of Done
- [ ] `grep -n "httpx.AsyncClient()" aria_skills/api_client/__init__.py` → only `_request_with_retry` method
- [ ] `create_activity`, `get_goals`, `update_goal`, `create_heartbeat` all delegate to `self.post`/`self.get`
- [ ] LLM skill has `LLM_FALLBACK_CHAIN` with ≥2 models
- [ ] `HealthDegradationLevel.DEGRADED` and `CRITICAL` defined in health skill
- [ ] `pytest tests/test_self_healing.py` → all 4 tests pass (or skip if container unavailable)
- [ ] ARIA-to-ARIA: Aria confirms create_activity uses retry, logs selfheal_s45_test activity successfully
- [ ] `grep -i "phase 2\|phase 3\|phase 4\|phase 5\|LLM fallback\|health degradation" SKILLS.md` → matches in self-healing section
- [ ] `grep "S-45" CHANGELOG.md` → 1 match
- [ ] `git diff HEAD -- SKILLS.md` shows Phase 2-5 additions
- [ ] `git diff HEAD -- CHANGELOG.md` shows S-45 entry added
- [ ] SPRINT_OVERVIEW.md updated
