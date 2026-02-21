# S5-03: Session History API with Search and Pagination
**Epic:** E4 — Session Management | **Priority:** P1 | **Points:** 3 | **Phase:** 4

## Problem
The engine needs a comprehensive session history API that supports paginated browsing, full-text search across session titles and message content, date range filtering, agent filtering, and multiple sort options. The existing session manager (S5-01) has `list_sessions()` with basic filtering, but the API layer needs proper FastAPI endpoints with Pydantic validation, query parameter handling, and optimized database queries with proper indexes.

Reference: `aria_engine/session_manager.py` (S5-01) — `NativeSessionManager.list_sessions()` and `get_messages()`. `src/api/routers/engine_cron.py` (S3-03) — pattern for FastAPI routers with Pydantic models.

## Root Cause
The session listing in S5-01 does the heavy lifting at the manager layer, but there's no API router exposing these capabilities. The API needs to translate URL query parameters into manager calls, add proper input validation, handle edge cases (empty results, invalid dates), and ensure the database queries perform well under load with proper indexes.

## Fix
### `src/api/routers/engine_sessions.py`
```python
"""
Session History API — browse, search, and filter chat sessions.

Provides:
- GET /api/engine/sessions — paginated list with search/filter
- GET /api/engine/sessions/{session_id} — single session detail
- GET /api/engine/sessions/{session_id}/messages — session messages
- DELETE /api/engine/sessions/{session_id} — delete session
- POST /api/engine/sessions/{session_id}/end — end session
- GET /api/engine/sessions/stats — aggregate statistics
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from aria_engine.config import EngineConfig
from aria_engine.session_manager import NativeSessionManager

logger = logging.getLogger("aria.api.sessions")
router = APIRouter(
    prefix="/api/engine/sessions",
    tags=["engine-sessions"],
)


# ── Pydantic Models ──────────────────────────────────────────

class SessionResponse(BaseModel):
    """Session summary in list responses."""

    session_id: str
    title: str
    agent_id: str
    session_type: str = "chat"
    message_count: int = 0
    created_at: str
    updated_at: Optional[str] = None
    last_message_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionListResponse(BaseModel):
    """Paginated session list."""

    sessions: List[SessionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class MessageResponse(BaseModel):
    """Chat message in session view."""

    id: int
    session_id: str
    role: str
    content: str
    agent_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


class SessionDetailResponse(SessionResponse):
    """Full session detail with recent messages."""

    recent_messages: List[MessageResponse] = []


class SessionStatsResponse(BaseModel):
    """Aggregate session statistics."""

    total_sessions: int
    total_messages: int
    active_agents: int
    oldest_session: Optional[str] = None
    newest_activity: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────

async def _get_manager() -> NativeSessionManager:
    """Get NativeSessionManager instance."""
    config = EngineConfig()
    db = config.get_db_engine()
    return NativeSessionManager(db)


# ── Endpoints ─────────────────────────────────────────────────

@router.get("", response_model=SessionListResponse)
async def list_sessions(
    agent_id: Optional[str] = Query(
        default=None,
        description="Filter by agent ID",
    ),
    session_type: Optional[str] = Query(
        default=None,
        description="Filter by type (chat, roundtable, cron)",
    ),
    search: Optional[str] = Query(
        default=None,
        max_length=200,
        description="Search in titles and message content",
    ),
    date_from: Optional[str] = Query(
        default=None,
        description="Start date (ISO format, e.g., 2025-01-01)",
    ),
    date_to: Optional[str] = Query(
        default=None,
        description="End date (ISO format, e.g., 2025-12-31)",
    ),
    sort: str = Query(
        default="updated_at",
        description="Sort field (created_at, updated_at, title)",
    ),
    order: str = Query(
        default="desc",
        description="Sort order (asc, desc)",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    List chat sessions with filtering, search, and pagination.

    Supports:
    - Agent filtering: ?agent_id=aria-talk
    - Type filtering: ?session_type=chat
    - Full-text search: ?search=deployment (searches titles + messages)
    - Date range: ?date_from=2025-01-01&date_to=2025-01-31
    - Sort: ?sort=created_at&order=asc
    - Pagination: ?limit=20&offset=0
    """
    mgr = await _get_manager()

    # Pass standard filters to manager
    result = await mgr.list_sessions(
        agent_id=agent_id,
        session_type=session_type,
        search=search,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )

    # Apply date range filter at API level
    # (kept out of manager to avoid over-complicating the SQL builder)
    if date_from or date_to:
        sessions = result["sessions"]
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from).replace(
                    tzinfo=timezone.utc
                )
                sessions = [
                    s
                    for s in sessions
                    if datetime.fromisoformat(s["created_at"]) >= dt_from
                ]
            except ValueError:
                raise HTTPException(
                    400, f"Invalid date_from format: {date_from}"
                )

        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to).replace(
                    tzinfo=timezone.utc,
                    hour=23,
                    minute=59,
                    second=59,
                )
                sessions = [
                    s
                    for s in sessions
                    if datetime.fromisoformat(s["created_at"]) <= dt_to
                ]
            except ValueError:
                raise HTTPException(
                    400, f"Invalid date_to format: {date_to}"
                )

        result["sessions"] = sessions
        result["total"] = len(sessions)

    return SessionListResponse(**result)


@router.get("/stats", response_model=SessionStatsResponse)
async def get_session_stats():
    """Get aggregate session statistics."""
    mgr = await _get_manager()
    stats = await mgr.get_stats()
    return SessionStatsResponse(**stats)


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """Get session details with recent messages."""
    mgr = await _get_manager()

    session = await mgr.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    # Get recent messages (last 10 for overview)
    messages = await mgr.get_messages(session_id, limit=10)

    return SessionDetailResponse(
        **session,
        recent_messages=[
            MessageResponse(**m) for m in messages
        ],
    )


@router.get(
    "/{session_id}/messages",
    response_model=List[MessageResponse],
)
async def get_session_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    since: Optional[str] = Query(
        default=None,
        description="Only messages after this ISO datetime",
    ),
):
    """
    Get all messages for a session.

    Supports pagination and since-filter for incremental loading.
    """
    mgr = await _get_manager()

    # Verify session exists
    session = await mgr.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(400, f"Invalid since format: {since}")

    messages = await mgr.get_messages(
        session_id=session_id,
        limit=limit,
        offset=offset,
        since=since_dt,
    )

    return [MessageResponse(**m) for m in messages]


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages."""
    mgr = await _get_manager()

    deleted = await mgr.delete_session(session_id)
    if not deleted:
        raise HTTPException(404, f"Session {session_id} not found")

    return {"status": "deleted", "session_id": session_id}


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """
    Mark a session as ended.

    Does not delete — sets metadata.ended = true.
    """
    mgr = await _get_manager()

    ended = await mgr.end_session(session_id)
    if not ended:
        raise HTTPException(404, f"Session {session_id} not found")

    return {"status": "ended", "session_id": session_id}


### SQL indexes for performance (add via Alembic migration)
_INDEXES_SQL = """
-- Session listing performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_agent_id
    ON aria_engine.chat_sessions (agent_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at
    ON aria_engine.chat_sessions (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_type
    ON aria_engine.chat_sessions (session_type);

-- Message retrieval performance
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
    ON aria_engine.chat_messages (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_agent_id
    ON aria_engine.chat_messages (agent_id);

-- Full-text search (trigram for ILIKE)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_chat_sessions_title_trgm
    ON aria_engine.chat_sessions
    USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_chat_messages_content_trgm
    ON aria_engine.chat_messages
    USING gin (content gin_trgm_ops);
"""
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API router at API layer |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from config |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL with pg_trgm |
| 5 | aria_memories only writable path | ❌ | Read-only API |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S5-01 (NativeSessionManager — underlying CRUD)
- S1-05 (Alembic — index migration)
- S1-03 (FastAPI app — router registration)

## Verification
```bash
# 1. API imports:
python -c "
from src.api.routers.engine_sessions import router, SessionListResponse
print(f'Routes: {len(router.routes)}')
"
# EXPECTED: Routes: 6

# 2. Pydantic validation:
python -c "
from src.api.routers.engine_sessions import SessionResponse, MessageResponse
s = SessionResponse(
    session_id='abc123', title='Test', agent_id='main',
    message_count=5, created_at='2025-01-01T00:00:00+00:00',
)
print(s.model_dump_json(indent=2))
"
# EXPECTED: Valid JSON

# 3. Index SQL present:
python -c "
from src.api.routers.engine_sessions import _INDEXES_SQL
assert 'idx_chat_sessions_agent_id' in _INDEXES_SQL
assert 'pg_trgm' in _INDEXES_SQL
print('Indexes OK')
"
# EXPECTED: Indexes OK
```

## Prompt for Agent
```
Create the session history API with search, filtering, and pagination.

FILES TO READ FIRST:
- aria_engine/session_manager.py (S5-01 — NativeSessionManager.list_sessions())
- src/api/routers/engine_cron.py (S3-03 — FastAPI router pattern with Pydantic)
- MASTER_PLAN.md (lines 130-150 — chat_sessions + chat_messages DDL)

STEPS:
1. Read all files above
2. Create src/api/routers/engine_sessions.py
3. Define Pydantic models: SessionResponse, SessionListResponse, MessageResponse, etc.
4. Implement 6 endpoints:
   a. GET /api/engine/sessions — list with search/filter/pagination
   b. GET /api/engine/sessions/stats — aggregate statistics
   c. GET /api/engine/sessions/{id} — detail with recent messages
   d. GET /api/engine/sessions/{id}/messages — full message history
   e. DELETE /api/engine/sessions/{id} — delete
   f. POST /api/engine/sessions/{id}/end — end session
5. Add date range filtering (date_from, date_to query params)
6. Include SQL for database indexes (agent_id, updated_at, pg_trgm)
7. Register router in FastAPI app
8. Run verification commands

CONSTRAINTS:
- Pagination: limit (1-100), offset, has_more flag
- Search: ILIKE on title + EXISTS on messages (from manager)
- Sort: created_at, updated_at, title (with asc/desc)
- Indexes: agent_id, updated_at DESC, session_type, pg_trgm for ILIKE
- Date filtering validated with proper error messages
```
