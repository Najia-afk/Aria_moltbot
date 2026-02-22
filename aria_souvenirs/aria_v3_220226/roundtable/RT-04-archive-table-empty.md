# RT-04: Archive Endpoint Soft-Deletes Only — Archive Table Stays Empty

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P1 🟡 | **Points:** 3 | **Phase:** 2

---

## Roundtable Exchange

**SM:** `POST /api/engine/sessions/{id}/archive` sets `status='archived'` but doesn't move
anything to `EngineChatSessionArchive`. The archive table only gets data from
`prune_old_sessions`. Users clicking "Archive" expect the session to move out of the main
list and into a real archive.

**Aria (PO):** The `/archive` endpoint should do a **full physical archive**:
1. Copy session row + all messages to the archive tables
2. Delete from working tables
3. Return `{"status": "archived", "archived_at": "..."}`
Acceptance: after calling `/archive`, the session is NOT visible in `GET /sessions` by default,
and IS visible in a new `GET /sessions/archive` list.

---

## Problem

`src/api/routers/engine_sessions.py` line ~380–410: `archive_session` endpoint
only sets `status = 'archived'` using SQLAlchemy ORM. It does not call
`NativeSessionManager.prune_old_sessions()` or any copy-to-archive logic.

`EngineChatSessionArchive` table exists and has proper INSERT ON CONFLICT DO NOTHING logic
inside `prune_old_sessions` (session_manager.py lines 600–670) but this is only called
by the cleanup cron.

---

## Root Cause

The archive endpoint was implemented as a soft-delete (status flag) while the physical
archive mechanism was built separately into the prune flow. The two were never connected.

---

## Fix Plan

Refactor `archive_session` endpoint to call a new `NativeSessionManager.archive_session()` method:

```python
# aria_engine/session_manager.py — new method
async def archive_session(self, session_id: str) -> bool:
    """Move session + messages to archive tables, then delete from working tables."""
    await self._ensure_archive_tables()
    # Re-use the archive INSERT logic from prune_old_sessions but for a single ID
    # 1. Copy session row to EngineChatSessionArchive
    # 2. Copy all messages to EngineChatMessageArchive
    # 3. Delete messages, then delete session
    # Returns True if found + archived, False if not found
```

Update the API endpoint:
```python
# src/api/routers/engine_sessions.py
@router.post("/{session_id}/archive")
async def archive_session(session_id: str):
    mgr = await _get_manager()
    archived = await mgr.archive_session(session_id)
    if not archived:
        raise HTTPException(404, f"Session {session_id} not found")
    return {"status": "archived", "session_id": session_id}
```

Add read endpoint for archived sessions:
```python
@router.get("/archive", response_model=SessionListResponse)
async def list_archived_sessions(limit: int = 20, offset: int = 0):
    """List physically archived sessions from EngineChatSessionArchive."""
    ...
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Change in session_manager (engine) + API router |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Verify archive table population in DB |
| 5 | aria_memories writable path | ❌ | DB tables, not files |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Archive a session:
curl -X POST http://localhost:8000/api/engine/sessions/TEST-SESSION-ID/archive
# EXPECTED: {"status": "archived", "session_id": "TEST-SESSION-ID"}

# 2. Verify it's gone from working table:
docker compose exec aria-db psql -U aria -d aria -c \
  "SELECT id FROM engine_chat_sessions WHERE id='TEST-SESSION-ID';"
# EXPECTED: 0 rows

# 3. Verify it's in archive table:
docker compose exec aria-db psql -U aria -d aria -c \
  "SELECT id, archived_at FROM engine_chat_session_archive WHERE id='TEST-SESSION-ID';"
# EXPECTED: 1 row with archived_at timestamp
```

---

## Prompt for Agent

Read: `aria_engine/session_manager.py` lines 540–700, `src/api/routers/engine_sessions.py`
lines 370–452, `db/models.py` (EngineChatSessionArchive, EngineChatMessageArchive).

Steps:
1. In `session_manager.py`, add `archive_session(session_id)` that reuses INSERT logic from `prune_old_sessions`
2. Update `/archive` endpoint to call `mgr.archive_session()` instead of raw ORM status update
3. Add `GET /sessions/archive` endpoint to list archived sessions
4. Run verification commands

Constraints: 1 (ORM only, no raw SQL), 4 (Docker test).
Dependencies: None.
