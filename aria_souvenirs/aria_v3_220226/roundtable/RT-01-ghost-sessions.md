# RT-01: Ghost Sessions Accumulate Forever

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P0 🔴 | **Points:** 3 | **Phase:** 1

---

## Roundtable Exchange

**SM:** Shiva opened a session `7d4953a6-...` — it was completely empty. How many of these exist?

**Aria (PO):** Every time a user navigates to `/chat` a new `EngineChatSession` row is created
immediately on page load (or when the `POST /api/engine/chat/stream` first hits the engine).
If they navigate away without typing, the session stays with `message_count = 0`.
The `prune_old_sessions` uses `updated_at < NOW() - 30 days` — a fresh ghost is 30 seconds old,
so it won't be pruned for a month.

**SM:** Acceptance criteria?

**Aria (PO):**
1. Ghost sessions (message_count = 0) older than **15 minutes** must be auto-deleted.
2. The cleanup must run on a **background task every 10 minutes** inside the API lifespan.
3. A manual endpoint `DELETE /api/engine/sessions/ghosts` must exist for immediate purge.
4. The chat page must NOT create a session on load — session creation deferred to first message sent.

---

## Problem

`NativeSessionManager.create_session()` is called eagerly when the chat page loads.
Any page visit without a message leaves a ghost.

**Evidence:**
- `aria_engine/chat_engine.py` calls `create_session` at stream start
- `src/api/main.py` lines 207–216: prune cron runs every 6h with `days=30`
- A 0-message session from this morning will survive until March 24th

---

## Root Cause

1. Session created before user sends first message (eager creation pattern)
2. Prune cutoff is 30 days — far too long for zero-value ghost rows
3. No `message_count = 0` fast-path in the pruner

---

## Fix Plan

### Step 1 — Deferred session creation (preferred, elegant)
Instead of creating a DB session on page load, the chat engine should create the session
only when the **first message is received**.

```python
# aria_engine/chat_engine.py — defer until message arrives
# BEFORE: session = await mgr.create_session(...)  # at stream init
# AFTER:  session created inside handle_message() on first call only
```

### Step 2 — Ghost purge background task (safety net)
Add to `src/api/main.py` lifespan:

```python
async def _purge_ghost_sessions():
    """Delete sessions with 0 messages older than 15 minutes, every 10 min."""
    while True:
        await asyncio.sleep(600)  # 10 minutes
        try:
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
                result = await db.execute(
                    delete(EngineChatSession)
                    .where(
                        EngineChatSession.message_count == 0,
                        EngineChatSession.created_at < cutoff,
                    )
                )
                await db.commit()
                if result.rowcount:
                    logger.info("Ghost purge: deleted %d empty sessions", result.rowcount)
        except Exception as e:
            logger.warning("Ghost purge failed: %s", e)
```

### Step 3 — Manual purge endpoint
```python
@router.delete("/ghosts")
async def purge_ghost_sessions(older_than_minutes: int = 15):
    """Delete all sessions with 0 messages older than N minutes."""
    ...
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Fix is in API layer only |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml single source of truth | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Verify in local compose |
| 5 | aria_memories only writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. After fix — count ghost sessions (should be 0 after 15 min):
docker compose exec aria-db psql -U aria -d aria -c \
  "SELECT COUNT(*) FROM engine_chat_sessions WHERE message_count=0 AND created_at < NOW() - INTERVAL '15 minutes';"
# EXPECTED: count = 0

# 2. Manual purge endpoint:
curl -X DELETE "http://localhost:8000/api/engine/sessions/ghosts?older_than_minutes=1"
# EXPECTED: {"deleted": N, "status": "ok"}

# 3. Page load doesn't create session:
# Open /chat, do NOT type, wait 5s, check DB — no new rows with 0 messages
```

---

## Prompt for Agent

Read: `aria_engine/chat_engine.py` (full), `aria_engine/session_manager.py` lines 554–700,
`src/api/main.py` lines 195–230, `src/api/routers/engine_sessions.py` lines 400–452.

Steps:
1. In `chat_engine.py`, defer `create_session()` to first message received (lazy init)
2. In `src/api/main.py` lifespan, add `_purge_ghost_sessions` background task (asyncio.create_task)
3. In `engine_sessions.py`, add `DELETE /ghosts` endpoint using ORM delete
4. Run verification commands above

Constraints: 1 (stay in API/engine layers), 4 (test in Docker).
Dependencies: None.
