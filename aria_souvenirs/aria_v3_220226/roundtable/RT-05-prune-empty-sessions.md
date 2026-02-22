# RT-05: Prune Cron Fires But Empty Sessions Survive 30 Days

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P1 🟡 | **Points:** 2 | **Phase:** 2

---

## Roundtable Exchange

**SM:** The prune cron exists in `src/api/main.py` (runs every 6 hours, 30-day cutoff).
There's also a cron job in `cron_jobs.yaml`. But the observed sessions are fresh ghosts
(seconds to minutes old) — the prune will never touch them.

**Aria (PO):** Two separate improvements needed:
1. The existing 30-day prune is fine for old conversations — keep it.
2. We need a **separate fast-path**: delete sessions with `message_count = 0` after **15 minutes**.
   These are pure noise — no conversation ever happened.
Acceptance: no session with 0 messages shall exist in the DB after 15 minutes of inactivity.

---

## Problem

`src/api/main.py` lines 207–216 — the periodic prune:
```python
async def _prune_sessions_task():
    """Prune stale sessions (>30 days) every 6 hours."""
    while True:
        await asyncio.sleep(6 * 3600)
        result = await mgr.prune_old_sessions(days=30, dry_run=False)
```

`NativeSessionManager.prune_old_sessions()` in `session_manager.py` line 580:
```python
stale_stmt = select(...).where(EngineChatSession.updated_at < cutoff)
```
No `message_count` filter — even 0-message sessions must wait 30 days.

---

## Root Cause

The prune function was designed for archiving old conversations, not for garbage-collecting
empty sessions. A single `message_count = 0` WHERE clause would fix the fast-path.

---

## Fix Plan

Add a `delete_ghost_sessions(older_than_minutes: int = 15)` method to `NativeSessionManager`:

```python
async def delete_ghost_sessions(self, older_than_minutes: int = 15) -> int:
    """Delete sessions with 0 messages older than N minutes. Returns count deleted."""
    cutoff = func.now() - func.make_interval(0, 0, 0, 0, older_than_minutes)
    async with self._async_session() as session:
        async with session.begin():
            result = await session.execute(
                delete(EngineChatSession)
                .where(
                    EngineChatSession.message_count == 0,
                    EngineChatSession.created_at < cutoff,
                )
            )
            return result.rowcount
```

In `src/api/main.py` lifespan, add a fast ghost-purge task running every 10 minutes.
(Or reuse the task added in RT-01 — these two tickets are complementary.)

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Change in session_manager + API lifespan |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Verify ghost count drops in DB |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Create a test ghost, wait 1s, run purge:
curl -X POST http://localhost:8000/api/engine/sessions \
  -H "Content-Type: application/json" -d '{"agent_id":"test","title":"ghost-test"}'
# Wait... then:
curl -X DELETE "http://localhost:8000/api/engine/sessions/ghosts?older_than_minutes=0"
# EXPECTED: {"deleted": 1, "status": "ok"}

# 2. Verify 0-message sessions count after 10 min background task runs:
docker compose exec aria-db psql -U aria -d aria -c \
  "SELECT COUNT(*) FROM engine_chat_sessions WHERE message_count=0;"
# EXPECTED: count = 0  (or only sessions created in the last 15 minutes)
```

---

## Prompt for Agent

Read: `aria_engine/session_manager.py` lines 554–600, `src/api/main.py` lines 195–230.

Steps:
1. Add `delete_ghost_sessions(older_than_minutes)` method to `NativeSessionManager`
2. Add `DELETE /sessions/ghosts?older_than_minutes=15` endpoint in `engine_sessions.py`
3. Wire into the 10-min background task in `src/api/main.py` (or reuse RT-01 task)

Constraints: 1 (ORM), 4 (Docker). Dependencies: RT-01 (can share background task).
