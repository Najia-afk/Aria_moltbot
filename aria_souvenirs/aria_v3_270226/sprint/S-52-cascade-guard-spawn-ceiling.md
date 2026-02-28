# S-52: Cascade Guard — Spawn Ceiling, CB Spawn Gate & Sub-Agent Fast Prune

**Epic:** E20 — Incident Hardening | **Priority:** P0 | **Points:** 5 | **Phase:** 1

---

## Problem

**The Midnight Cascade (Feb 27–28, 2026):** Between 23:15 UTC and 01:52 UTC, Aria spawned
**135 sessions** (71 sub-devsecops) in a self-reinforcing loop triggered by an open API circuit
breaker. Three concurrent engine files lack any protection:

1. `aria_engine/agent_pool.py` line 300: `spawn_agent()` checks only
   `len(self._agents) >= MAX_CONCURRENT_AGENTS` (in-memory count = 5), **not** the
   accumulated count of sub-* type agents persisted in `EngineAgentState`. Each cron cycle
   spawns fresh agents that register in DB; the in-memory pool turns over; the ceiling is
   bypassed per-iteration. 135 agents registered across 10 cron cycles with zero rejection.

2. `aria_engine/circuit_breaker.py`: has no method to signal "do not spawn sub-agents
   while I am OPEN". Callers query `is_open()` but there is no spawn-specific guard
   that makes the CB the authority on whether spawning is safe. Work cycle proceeds
   to spawn regardless of CB state.

3. `aria_engine/auto_session.py` line 32: `IDLE_TIMEOUT_MINUTES = 30`, but the pruning
   query on line 283 only matches `session_type == "chat"` with no agent-type
   differentiation. Sub-agent sessions that are *actively burning tokens* (not idle) are
   not pruned. At 01:29: `active_sessions: 21` — all exempt from idle prune because
   they had recent `updated_at` timestamps from their CB-hit attempts.

## Root Cause

**CB open → work_cycle enters fallback path → `agent_pool.spawn_agent(sub-devsecops-N)` called**

- `spawn_agent()` at line 299 checks `len(self._agents) >= 5`. At any given moment
  the in-memory pool has ≤ 5 agents; check passes. New agent DB row inserted. Old agents
  kicked from in-memory pool by next cycle. No per-type DB-level count check exists.
- `CircuitBreaker.is_open()` gates API calls but is never consulted at spawn-decision time.
  No `spawn_gate()` method exists to make this relationship explicit.
- `close_idle_sessions()` uses one universal timeout. Sub-agents running CB-retry loops
  update their `updated_at` on every failed attempt, resetting the idle clock. They appear
  "active" and are never pruned during the incident window.

## Fix

### Change 1 — `aria_engine/agent_pool.py`: Add `MAX_SUB_AGENTS_PER_TYPE` ceiling

**BEFORE** (line 31):
```python
MAX_CONCURRENT_AGENTS = 5
```

**AFTER**:
```python
MAX_CONCURRENT_AGENTS = 5

# Hard ceiling on active sub-agents by type prefix (last-resort cascade guard).
# Primary defence is CB-aware spawn logic in the work cycle.
# These limits prevent runaway spawning when that logic fails or is bypassed.
MAX_SUB_AGENTS_PER_TYPE: dict[str, int] = {
    "sub-devsecops": 10,
    "sub-social": 10,
    "sub-orchestrator": 5,
    "sub-aria": 5,
}
```

**BEFORE** (`spawn_agent()` at line 299):
```python
        if len(self._agents) >= MAX_CONCURRENT_AGENTS:
            raise EngineError(
                f"Agent pool full ({MAX_CONCURRENT_AGENTS} max). "
                "Terminate an agent first."
            )
```

**AFTER**:
```python
        if len(self._agents) >= MAX_CONCURRENT_AGENTS:
            raise EngineError(
                f"Agent pool full ({MAX_CONCURRENT_AGENTS} max). "
                "Terminate an agent first."
            )

        # Per-type ceiling: query DB for current sub-agent count before spawning.
        # Uses rsplit to extract prefix: "sub-devsecops-7" → "sub-devsecops"
        type_prefix = agent_id.rsplit("-", 1)[0] if "-" in agent_id else agent_id
        if type_prefix in MAX_SUB_AGENTS_PER_TYPE:
            async with self._db_engine.begin() as _check:
                count_q = (
                    select(func.count())
                    .select_from(EngineAgentState)
                    .where(
                        EngineAgentState.agent_id.like(f"{type_prefix}-%"),
                        EngineAgentState.status != "disabled",
                    )
                )
                _result = await _check.execute(count_q)
                current_count: int = _result.scalar_one()
            ceiling = MAX_SUB_AGENTS_PER_TYPE[type_prefix]
            if current_count >= ceiling:
                raise EngineError(
                    f"Sub-agent ceiling reached: {type_prefix!r} has "
                    f"{current_count}/{ceiling} active agents. "
                    "Circuit breaker must reset or stale agents must be terminated first."
                )
```

---

### Change 2 — `aria_engine/circuit_breaker.py`: Add `spawn_gate()` method

**BEFORE** (after `record_failure()`, at line ~101):
```python
    def reset(self) -> None:
        """Force-reset the circuit breaker to CLOSED state."""
        self._failures = 0
        self._opened_at = None
```

**AFTER**:
```python
    def spawn_gate(self) -> None:
        """Raise EngineError if this CB is OPEN, blocking sub-agent spawning.

        Call this before any sub-agent creation that would be used as a CB
        fallback path. Prevents cascade: if the CB that triggered the spawn
        decision is still OPEN, spawning another agent to retry is futile.

        Usage:
            cb.spawn_gate()          # raises if open
            await pool.spawn_agent(...)  # only reached if CB closed/half-open
        """
        if self.is_open():
            from aria_engine.exceptions import EngineError
            raise EngineError(
                f"Circuit breaker '{self.name}' is OPEN — "
                "spawning a sub-agent as fallback is blocked until the CB resets. "
                "Accept degraded state for this cycle."
            )

    def reset(self) -> None:
        """Force-reset the circuit breaker to CLOSED state."""
        self._failures = 0
        self._opened_at = None
```

---

### Change 3 — `aria_engine/auto_session.py`: Add `close_stale_subagent_sessions()`

**BEFORE** (line 29):
```python
IDLE_TIMEOUT_MINUTES = 30
MAX_MESSAGES_PER_SESSION = 200
MAX_SESSION_DURATION_HOURS = 8
```

**AFTER**:
```python
IDLE_TIMEOUT_MINUTES = 30
MAX_MESSAGES_PER_SESSION = 200
MAX_SESSION_DURATION_HOURS = 8
SUB_AGENT_STALE_HOURS = 1   # sub-* sessions pruned after 1h regardless of activity
```

**BEFORE** (end of `close_idle_sessions()` method, before `get_or_create_session()`):
```python
        return {
            "closed_count": len(idle_ids),
            "session_ids": idle_ids,
        }

    async def get_or_create_session(
```

**AFTER**:
```python
        return {
            "closed_count": len(idle_ids),
            "session_ids": idle_ids,
        }

    async def close_stale_subagent_sessions(
        self,
        stale_hours: int = SUB_AGENT_STALE_HOURS,
    ) -> dict[str, Any]:
        """Close sub-agent sessions older than stale_hours (default 1h).

        Unlike close_idle_sessions() which is reset by any activity,
        this prune is wall-clock based: a sub-* session that has been
        running for >1h is considered stale regardless of activity.
        This prevents cascade agents from hiding behind frequent updates.

        Should be called alongside close_idle_sessions() in the scheduler.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
        async with self._db.begin() as conn:
            stmt = (
                select(EngineChatSession.id)
                .where(
                    and_(
                        EngineChatSession.created_at < cutoff,
                        EngineChatSession.agent_id.like("sub-%"),
                        or_(
                            EngineChatSession.metadata_json.is_(None),
                            not_(
                                EngineChatSession.metadata_json.has_key("ended")
                            ),
                            EngineChatSession.metadata_json["ended"].astext
                            == "false",
                        ),
                    )
                )
            )
            result = await conn.execute(stmt)
            stale_ids = [row[0] for row in result.fetchall()]

            if stale_ids:
                await conn.execute(
                    update(EngineChatSession)
                    .where(EngineChatSession.id.in_(stale_ids))
                    .values(
                        metadata_json=func.coalesce(
                            EngineChatSession.metadata_json,
                            cast("{}", PG_JSONB),
                        ).op("||")(
                            cast(
                                {
                                    "ended": True,
                                    "end_reason": "sub_agent_stale_prune",
                                },
                                PG_JSONB,
                            )
                        ),
                        updated_at=func.now(),
                    )
                )

        if stale_ids:
            logger.info(
                "Stale-pruned %d sub-agent sessions (created >%dh ago)",
                len(stale_ids),
                stale_hours,
            )

        return {"closed_count": len(stale_ids), "session_ids": stale_ids}

    async def get_or_create_session(
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | All changes are in `aria_engine/` layer — no layer violation |
| 2 | .env for secrets | ✅ | No secrets. New constants are code-level limits, not credentials |
| 3 | models.yaml single source of truth | ✅ | No model references added |
| 4 | Docker-first testing | ✅ | Verification runs inside Docker Compose stack |
| 5 | aria_memories only writable path | ✅ | Only DB mutations (PostgreSQL), no filesystem writes outside aria_memories |
| 6 | No soul modification | ✅ | No files in `aria_mind/soul/` touched |

---

## Dependencies

- **None** — all three changed files are self-contained engine components.
- Recommended to run after **S-39** (Work-Cycle Log Integrity Guardrails) which hardens
  artifact writes; S-52 hardens the spawning path upstream of that.

---

## Verification

```bash
# 1. Type ceiling constant present in agent_pool
grep -n "MAX_SUB_AGENTS_PER_TYPE" aria_engine/agent_pool.py
# EXPECTED:
# 33: MAX_SUB_AGENTS_PER_TYPE: dict[str, int] = {

# 2. DB-count ceiling check present in spawn_agent()
grep -n "type_prefix\|scalar_one\|current_count" aria_engine/agent_pool.py
# EXPECTED:
# ~312: type_prefix = agent_id.rsplit("-", 1)[0] if "-" in agent_id else agent_id
# ~313: if type_prefix in MAX_SUB_AGENTS_PER_TYPE:
# ~321:                 _result = await _check.execute(count_q)
# ~322:                 current_count: int = _result.scalar_one()

# 3. spawn_gate() method present in circuit_breaker
grep -n "spawn_gate" aria_engine/circuit_breaker.py
# EXPECTED:
# ~102: def spawn_gate(self) -> None:

# 4. SUB_AGENT_STALE_HOURS constant present
grep -n "SUB_AGENT_STALE_HOURS\|close_stale_subagent" aria_engine/auto_session.py
# EXPECTED:
# 32: SUB_AGENT_STALE_HOURS = 1
# ~330: async def close_stale_subagent_sessions(

# 5. Unit tests pass
pytest tests/ -k "agent_pool or circuit_breaker or auto_session" -v --tb=short
# EXPECTED: all collected tests pass

# 6. Spawn ceiling rejection smoke-test (in Docker):
docker compose exec aria-engine python3 -c "
import asyncio
from aria_engine.agent_pool import MAX_SUB_AGENTS_PER_TYPE
assert 'sub-devsecops' in MAX_SUB_AGENTS_PER_TYPE
assert MAX_SUB_AGENTS_PER_TYPE['sub-devsecops'] == 10
print('PASS: ceiling constants correct')
"
# EXPECTED: PASS: ceiling constants correct

# 7. CB spawn_gate smoke-test:
docker compose exec aria-engine python3 -c "
from aria_engine.circuit_breaker import CircuitBreaker
cb = CircuitBreaker(name='test', threshold=1, reset_after=999)
cb.record_failure()
try:
    cb.spawn_gate()
    print('FAIL: should have raised')
except Exception as e:
    print('PASS:', e)
"
# EXPECTED: PASS: Circuit breaker 'test' is OPEN — spawning a sub-agent as fallback is blocked...

# 8. close_stale_subagent_sessions signature check:
docker compose exec aria-engine python3 -c "
import inspect
from aria_engine.auto_session import AutoSessionManager
assert hasattr(AutoSessionManager, 'close_stale_subagent_sessions')
print('PASS: method exists')
"
# EXPECTED: PASS: method exists
```

---

## Prompt for Agent

You are applying a 3-file patch to harden Aria's engine against the recursive sub-agent
spawning cascade documented in the The Midnight Cascade incident (Feb 27–28, 2026).

**Files to read first:**
- `aria_engine/agent_pool.py` (lines 1–50 for constants, lines 270–360 for `spawn_agent()`)
- `aria_engine/circuit_breaker.py` (full file, 121 lines)
- `aria_engine/auto_session.py` (lines 25–35 for constants, lines 257–349 for prune methods)
- `aria_engine/exceptions.py` (to confirm `EngineError` class name)

**Constraints:** 1 (5-layer), 4 (Docker-first), 5 (aria_memories only writable)

**Steps:**

1. In `aria_engine/agent_pool.py`:
   - Add `MAX_SUB_AGENTS_PER_TYPE` dict after `MAX_CONCURRENT_AGENTS = 5` (line 31)
   - Inside `spawn_agent()`, after the `if len(self._agents) >= MAX_CONCURRENT_AGENTS:` block,
     add the type-prefix DB-count ceiling check (see Fix above for exact code)

2. In `aria_engine/circuit_breaker.py`:
   - Add `spawn_gate()` method between `record_failure()` and `reset()` (around line 101)
   - Do NOT import `EngineError` at module level — use a local import inside `spawn_gate()` to
     avoid a circular import (circuit_breaker has no aria_engine imports currently)

3. In `aria_engine/auto_session.py`:
   - Add `SUB_AGENT_STALE_HOURS = 1` after `MAX_SESSION_DURATION_HOURS = 8` (line 32)
   - Add `close_stale_subagent_sessions()` method immediately after `close_idle_sessions()`
     (before `get_or_create_session()`)
   - The method uses `EngineChatSession.created_at` (not `updated_at`) as the cutoff — this
     is the key difference from `close_idle_sessions()` which uses `updated_at`

4. Run all verification commands. All 8 checks must pass.

5. Update `tasks/lessons.md` with:
   - Pattern: "Sub-agent type ceiling in agent_pool prevents cascade spawning"
   - Pattern: "CB.spawn_gate() must be called before any sub-agent spawn as fallback"
   - Pattern: "Sub-agent sessions need wall-clock prune (created_at), not idle prune (updated_at)"

---

## Incident Reference

- **Postmortem:** `articles/article_the_midnight_cascade.html` (local) /
  published at `https://najia.dev/articles/article_the_midnight_cascade.html`
- **Source logs:** `aria_souvenirs/aria_v3_270226/logs/` /
  `https://github.com/Najia-afk/Aria_moltbot/tree/main/aria_souvenirs/aria_v3_270226/logs`
- **Root cause:** `aria_engine/circuit_breaker.py` — `record_success()` never called →
  CB stays OPEN across 10 cron cycles → 71 sub-devsecops spawned → 27.2M tokens burned
