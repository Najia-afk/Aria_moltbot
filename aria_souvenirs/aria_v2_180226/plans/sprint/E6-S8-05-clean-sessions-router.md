# S8-05: Rewrite Sessions Router — Remove OpenClaw Sync
**Epic:** E6 — OpenClaw Removal | **Priority:** P0 | **Points:** 5 | **Phase:** 8

## Problem
`src/api/routers/sessions.py` is 962 lines, of which approximately 80% (~750 lines) is OpenClaw session sync logic: parsing OpenClaw's filesystem JSON, normalizing live session data from the OpenClaw API, periodic background sync, and UUID namespace mapping. All of this must be removed and replaced with simple PostgreSQL-native CRUD against the `aria_engine.chat_sessions` and `aria_engine.chat_messages` tables.

## Root Cause
The sessions router was built to bridge two worlds: OpenClaw's file-based session storage and Aria's PostgreSQL database. It periodically read `/openclaw/agents/*/sessions/sessions.json` and synced records into the `agent_sessions` table. With the engine handling sessions natively in PostgreSQL, this entire sync layer is dead code.

## Fix

### 1. Rewritten `src/api/routers/sessions.py` (~200 lines)

```python
"""
Agent sessions endpoints — CRUD + stats.
Reads from aria_engine.chat_sessions / chat_messages (PostgreSQL-native).
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentSession
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Sessions"])


# ── List sessions ────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    status: Optional[str] = Query(None, description="Filter by status"),
    session_type: Optional[str] = Query(None, description="Filter by type"),
    search: Optional[str] = Query(None, description="Search label or metadata"),
    sort: str = Query("started_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List chat sessions with filtering, search, and pagination."""
    query = select(AgentSession)

    if agent_id:
        query = query.where(AgentSession.agent_id == agent_id)
    if status:
        query = query.where(AgentSession.status == status)
    if session_type:
        query = query.where(AgentSession.session_type == session_type)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            AgentSession.metadata_json["label"].astext.ilike(pattern)
            | AgentSession.agent_id.ilike(pattern)
        )

    # Sorting
    sort_col = getattr(AgentSession, sort, AgentSession.started_at)
    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    return await build_paginated_response(
        db, query, page=page, page_size=page_size
    )


# ── Get single session ──────────────────────────────────────────────────────

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single session by ID."""
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return _session_to_dict(session)


# ── Create session ───────────────────────────────────────────────────────────

@router.post("/sessions", status_code=201)
async def create_session(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new chat session."""
    session = AgentSession(
        agent_id=body.get("agent_id", "main"),
        session_type=body.get("session_type", "chat"),
        status="active",
        started_at=datetime.now(timezone.utc),
        metadata_json=body.get("metadata", {}),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)


# ── Update session ───────────────────────────────────────────────────────────

@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: UUID,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update session status, metadata, or end time."""
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if "status" in body:
        session.status = body["status"]
        if body["status"] in ("completed", "ended"):
            session.ended_at = datetime.now(timezone.utc)

    if "metadata" in body:
        existing = session.metadata_json or {}
        existing.update(body["metadata"])
        session.metadata_json = existing

    if "ended_at" in body:
        session.ended_at = datetime.fromisoformat(body["ended_at"])

    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)


# ── Delete session ───────────────────────────────────────────────────────────

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a session and its messages (cascade)."""
    result = await db.execute(
        delete(AgentSession).where(AgentSession.id == session_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.commit()


# ── Session stats ────────────────────────────────────────────────────────────

@router.get("/sessions/stats/summary")
async def session_stats(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregate session statistics."""
    result = await db.execute(
        select(
            func.count(AgentSession.id).label("total"),
            func.count().filter(AgentSession.status == "active").label("active"),
            func.count().filter(AgentSession.status == "completed").label("completed"),
            func.count().filter(AgentSession.status == "error").label("errored"),
        )
    )
    row = result.one()

    # Sessions per agent
    agent_result = await db.execute(
        select(
            AgentSession.agent_id,
            func.count(AgentSession.id).label("count"),
        )
        .group_by(AgentSession.agent_id)
        .order_by(func.count(AgentSession.id).desc())
        .limit(10)
    )

    return {
        "total": row.total,
        "active": row.active,
        "completed": row.completed,
        "errored": row.errored,
        "by_agent": [
            {"agent_id": r.agent_id, "count": r.count}
            for r in agent_result.all()
        ],
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _session_to_dict(session: AgentSession) -> dict[str, Any]:
    """Convert an AgentSession ORM object to a JSON-serializable dict."""
    return {
        "id": str(session.id),
        "agent_id": session.agent_id,
        "session_type": session.session_type,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "metadata": session.metadata_json or {},
    }
```

### 2. What was removed (~750 lines)

| Removed Code | Lines | Purpose |
|-------------|-------|---------|
| `_OPENCLAW_UUID_NAMESPACE` | 1 | UUID namespace for deterministic IDs |
| `_OPENCLAW_SESSIONS_UNAVAILABLE_UNTIL` | 1 | Backoff timer for OpenClaw API |
| `_LAST_OPENCLAW_SYNC_AT` | 1 | Last sync timestamp |
| `_OPENCLAW_SYNC_LOCK` | 1 | Async lock for sync |
| `_parse_iso_dt()` | 8 | Parse ISO dates from OpenClaw |
| `_parse_epoch_ms_dt()` | 12 | Parse epoch milliseconds |
| `_extract_live_session_id()` | 8 | Extract ID from various OpenClaw formats |
| `_extract_live_agent_id()` | 6 | Extract agent from OpenClaw session |
| `_extract_live_status()` | 8 | Normalize OpenClaw status strings |
| `_extract_live_label()` | 20 | Extract label from OpenClaw delivery context |
| `_extract_live_channel()` | 25 | Extract channel from OpenClaw origin |
| `_normalize_live_session()` | 50 | Full OpenClaw→PostgreSQL normalizer |
| `_extract_session_id_from_index_key()` | 12 | Parse OpenClaw index keys |
| `_load_index_sessions()` | ~80 | Read sessions.json from filesystem |
| `_sync_sessions_from_index()` | ~100 | Batch upsert from index file |
| `_fetch_live_sessions_from_openclaw()` | ~60 | HTTP call to OpenClaw gateway API |
| `_sync_live_sessions()` | ~80 | Sync live session data |
| `_ensure_openclaw_sessions_synced()` | ~40 | Periodic sync orchestrator |
| `GET /sessions/openclaw/sync` | ~20 | Manual trigger endpoint |
| `GET /sessions/openclaw/live` | ~30 | Proxy to OpenClaw live sessions |
| Various OpenClaw-specific endpoints | ~200 | Session detail from OpenClaw, message fetch, etc. |

### 3. Import cleanup

**Before (remove):**
```python
import json as json_lib
import asyncio
import glob
import os
import uuid

import httpx

from config import (
    OPENCLAW_SESSIONS_INDEX_PATH,
    OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS,
    OPENCLAW_AGENTS_ROOT,
    SERVICE_URLS,
)
from db.models import AgentSession, ModelUsage
from deps import get_db, get_litellm_db
```

**After (clean):**
```python
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentSession
from deps import get_db
from pagination import paginate_query, build_paginated_response
```

Removed: `json`, `asyncio`, `glob`, `os`, `uuid` (except UUID type), `httpx`, all OpenClaw config imports, `ModelUsage`, `get_litellm_db`.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Pure DB→ORM→API layer |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | N/A |
| 4 | Docker-first testing | ✅ | Test all endpoints with curl |
| 5 | aria_memories only writable path | ❌ | Writes to PostgreSQL only |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S8-04 (Clean config — OPENCLAW_* vars must be removed before this import cleanup works)
- S1-01 (Database schema — AgentSession model must exist)
- S2-01 (Chat sessions — engine session management must be working)

## Verification
```bash
# 1. File is ~200 lines (was 962):
wc -l src/api/routers/sessions.py
# EXPECTED: ~200

# 2. No openclaw references:
grep -ci "openclaw\|clawdbot" src/api/routers/sessions.py
# EXPECTED: 0

# 3. No httpx import:
grep -c "import httpx" src/api/routers/sessions.py
# EXPECTED: 0

# 4. CRUD endpoints work:
# List:
curl -s http://aria-api:8000/sessions | python -m json.tool | head -5
# Create:
curl -s -X POST http://aria-api:8000/sessions -H "Content-Type: application/json" -d '{"agent_id":"main"}' | python -m json.tool
# Get:
curl -s http://aria-api:8000/sessions/<id> | python -m json.tool
# Stats:
curl -s http://aria-api:8000/sessions/stats/summary | python -m json.tool

# 5. API starts without import errors:
docker compose up -d aria-api
docker compose logs aria-api --tail=10 | grep -c "ERROR\|ImportError"
# EXPECTED: 0
```

## Prompt for Agent
```
Rewrite the sessions router to remove all OpenClaw sync logic.

FILES TO READ FIRST:
- src/api/routers/sessions.py (FULL file — 962 lines, understand what to keep vs remove)
- src/api/config.py (cleaned in S8-04 — no more OPENCLAW_* vars)
- db/models.py (AgentSession model definition)
- deps.py (get_db dependency)

THE REWRITE:
Replace the ENTIRE file content with ~200 lines of clean PostgreSQL-native CRUD.

KEEP:
- GET /sessions (list with filtering + pagination)
- GET /sessions/{id} (single session)
- POST /sessions (create)
- PATCH /sessions/{id} (update status/metadata)
- DELETE /sessions/{id} (delete)
- GET /sessions/stats/summary (aggregate stats)
- _session_to_dict helper

DELETE:
- ALL _parse_*, _extract_*, _normalize_* helper functions (OpenClaw parsing)
- ALL _load_index_sessions, _sync_*, _fetch_* functions (OpenClaw sync)
- ALL /sessions/openclaw/* endpoints
- ALL global state variables (_OPENCLAW_*, _LAST_*, locks)
- httpx import (no more HTTP calls to OpenClaw)
- asyncio import (no more locks)
- glob, os imports (no more filesystem reads)
- config imports (OPENCLAW_* removed)

SAFETY:
- This is a FULL FILE REPLACEMENT — write the complete new file
- Verify all endpoints still have their route decorators
- The pagination helpers (paginate_query, build_paginated_response) are still used
- AgentSession model is unchanged
```
