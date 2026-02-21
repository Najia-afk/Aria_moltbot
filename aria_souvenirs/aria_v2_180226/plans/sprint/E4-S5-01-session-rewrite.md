# S5-01: Native Session Manager (PostgreSQL Rewrite)
**Epic:** E4 — Session Management | **Priority:** P0 | **Points:** 5 | **Phase:** 4

## Problem
The existing `aria_skills/session_manager/__init__.py` manages sessions via a `sessions.json` index file and per-session `.jsonl` log files stored on the filesystem. This works for single-instance setups but fails under multiple containers, has no referential integrity, relies on filesystem scanning for orphan cleanup, and can't support full-text search or pagination natively. The engine needs a `NativeSessionManager` backed entirely by PostgreSQL using the `chat_sessions` and `chat_messages` tables, with a backward-compatible API surface.

Reference: `aria_skills/session_manager/__init__.py` (542 lines) — `SessionManagerSkill` with create/get/list/delete/prune, two-layer delete, orphan cleanup, sessions.json index. `MASTER_PLAN.md` lines 130-150 — chat_sessions and chat_messages DDL.

## Root Cause
The filesystem-based session manager was designed before the engine had database persistence. The `.jsonl` + `sessions.json` approach requires mutex locks for concurrent access, doesn't scale across containers, and makes search/filter operations expensive (full scan per query). The engine's PostgreSQL schema already has the right tables — the session manager just needs to use them.

## Fix
### `aria_engine/session_manager.py`
```python
"""
Native Session Manager — PostgreSQL-backed session lifecycle.

Replaces aria_skills/session_manager with direct DB access:
- No sessions.json, no JSONL files
- Full CRUD via chat_sessions + chat_messages
- Native pagination, search, and filtering
- Backward-compatible method signatures
- Agent-scoped queries via agent_id parameter
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError

logger = logging.getLogger("aria.engine.session_manager")

# Defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_TITLE_LENGTH = 200
MAX_MESSAGE_LENGTH = 100_000  # 100KB per message


class NativeSessionManager:
    """
    PostgreSQL-backed session manager.

    Manages the full lifecycle of chat sessions and messages
    using aria_engine.chat_sessions and aria_engine.chat_messages.

    Usage:
        mgr = NativeSessionManager(db_engine)

        # Create session
        session = await mgr.create_session(
            agent_id="aria-talk",
            title="Morning chat",
        )

        # Add messages
        await mgr.add_message(
            session_id=session["session_id"],
            role="user",
            content="Hello!",
        )

        # Get full conversation
        messages = await mgr.get_messages(session["session_id"])

        # List sessions with search
        sessions = await mgr.list_sessions(
            agent_id="aria-talk",
            search="morning",
            limit=10,
        )
    """

    def __init__(self, db_engine: AsyncEngine):
        self._db = db_engine

    # ── Session CRUD ──────────────────────────────────────────

    async def create_session(
        self,
        agent_id: str = "main",
        title: Optional[str] = None,
        session_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new chat session.

        Args:
            agent_id: Owning agent ID.
            title: Session title (auto-generated if None).
            session_type: Type ('chat', 'roundtable', 'cron').
            metadata: Optional JSON metadata.

        Returns:
            Session dict with session_id, title, agent_id, etc.
        """
        session_id = uuid4().hex[:16]
        if not title:
            title = f"Session {session_id[:8]}"
        title = title[:MAX_TITLE_LENGTH]

        import json as _json

        meta_str = _json.dumps(metadata) if metadata else None

        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    INSERT INTO aria_engine.chat_sessions
                        (session_id, title, agent_id, session_type,
                         metadata)
                    VALUES
                        (:sid, :title, :agent, :stype,
                         :meta::jsonb)
                    RETURNING session_id, title, agent_id,
                              session_type, created_at
                """),
                {
                    "sid": session_id,
                    "title": title,
                    "agent": agent_id,
                    "stype": session_type,
                    "meta": meta_str,
                },
            )
            row = result.mappings().first()

        logger.info(
            "Created session %s for %s: %s",
            session_id, agent_id, title,
        )

        return {
            "session_id": row["session_id"],
            "title": row["title"],
            "agent_id": row["agent_id"],
            "session_type": row["session_type"],
            "created_at": row["created_at"].isoformat(),
            "message_count": 0,
        }

    async def get_session(
        self,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get session details by ID.

        Returns:
            Session dict or None if not found.
        """
        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        s.session_id, s.title, s.agent_id,
                        s.session_type, s.metadata, s.created_at,
                        s.updated_at,
                        COUNT(m.id) AS message_count,
                        MAX(m.created_at) AS last_message_at
                    FROM aria_engine.chat_sessions s
                    LEFT JOIN aria_engine.chat_messages m
                        ON m.session_id = s.session_id
                    WHERE s.session_id = :sid
                    GROUP BY s.session_id, s.title, s.agent_id,
                             s.session_type, s.metadata,
                             s.created_at, s.updated_at
                """),
                {"sid": session_id},
            )
            row = result.mappings().first()

        if not row:
            return None

        return self._row_to_session(row)

    async def list_sessions(
        self,
        agent_id: Optional[str] = None,
        session_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        sort: str = "updated_at",
        order: str = "desc",
    ) -> Dict[str, Any]:
        """
        List sessions with filtering, search, and pagination.

        Args:
            agent_id: Filter by agent.
            session_type: Filter by type ('chat', 'roundtable', 'cron').
            search: Full-text search in title and messages.
            limit: Page size (max 100).
            offset: Offset for pagination.
            sort: Sort field ('created_at', 'updated_at', 'title').
            order: Sort order ('asc', 'desc').

        Returns:
            Dict with 'sessions' list, 'total' count, pagination info.
        """
        limit = min(max(limit, 1), MAX_PAGE_SIZE)

        # Validate sort
        allowed_sorts = {"created_at", "updated_at", "title"}
        if sort not in allowed_sorts:
            sort = "updated_at"
        if order not in ("asc", "desc"):
            order = "desc"

        # Build WHERE clauses
        conditions = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if agent_id:
            conditions.append("s.agent_id = :agent_id")
            params["agent_id"] = agent_id

        if session_type:
            conditions.append("s.session_type = :stype")
            params["stype"] = session_type

        if search:
            conditions.append("""
                (s.title ILIKE :search
                 OR EXISTS (
                     SELECT 1 FROM aria_engine.chat_messages cm
                     WHERE cm.session_id = s.session_id
                       AND cm.content ILIKE :search
                 ))
            """)
            params["search"] = f"%{search}%"

        where = (
            "WHERE " + " AND ".join(conditions) if conditions else ""
        )

        async with self._db.begin() as conn:
            # Count total
            count_result = await conn.execute(
                text(f"""
                    SELECT COUNT(*) AS total
                    FROM aria_engine.chat_sessions s
                    {where}
                """),
                params,
            )
            total = count_result.scalar()

            # Fetch page
            result = await conn.execute(
                text(f"""
                    SELECT
                        s.session_id, s.title, s.agent_id,
                        s.session_type, s.metadata,
                        s.created_at, s.updated_at,
                        COUNT(m.id) AS message_count,
                        MAX(m.created_at) AS last_message_at
                    FROM aria_engine.chat_sessions s
                    LEFT JOIN aria_engine.chat_messages m
                        ON m.session_id = s.session_id
                    {where}
                    GROUP BY s.session_id, s.title, s.agent_id,
                             s.session_type, s.metadata,
                             s.created_at, s.updated_at
                    ORDER BY s.{sort} {order}
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )
            rows = result.mappings().all()

        return {
            "sessions": [self._row_to_session(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    async def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update session title and/or metadata."""
        sets = ["updated_at = NOW()"]
        params: Dict[str, Any] = {"sid": session_id}

        if title is not None:
            sets.append("title = :title")
            params["title"] = title[:MAX_TITLE_LENGTH]

        if metadata is not None:
            import json as _json

            sets.append("metadata = :meta::jsonb")
            params["meta"] = _json.dumps(metadata)

        async with self._db.begin() as conn:
            result = await conn.execute(
                text(f"""
                    UPDATE aria_engine.chat_sessions
                    SET {', '.join(sets)}
                    WHERE session_id = :sid
                    RETURNING session_id
                """),
                params,
            )
            if not result.first():
                return None

        return await self.get_session(session_id)

    async def delete_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Delete a session and all its messages.

        Uses CASCADE from chat_messages FK, but explicit delete
        handles cases where FK constraints don't exist yet.

        Returns:
            True if session existed and was deleted.
        """
        async with self._db.begin() as conn:
            # Delete messages first (safe even with CASCADE)
            await conn.execute(
                text("""
                    DELETE FROM aria_engine.chat_messages
                    WHERE session_id = :sid
                """),
                {"sid": session_id},
            )

            result = await conn.execute(
                text("""
                    DELETE FROM aria_engine.chat_sessions
                    WHERE session_id = :sid
                    RETURNING session_id
                """),
                {"sid": session_id},
            )
            deleted = result.first() is not None

        if deleted:
            logger.info("Deleted session %s", session_id)

        return deleted

    async def end_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Mark a session as ended (set updated_at, add end marker).

        Does not delete — just marks as inactive.

        Returns:
            True if session exists.
        """
        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    UPDATE aria_engine.chat_sessions
                    SET updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb)
                            || '{"ended": true}'::jsonb
                    WHERE session_id = :sid
                    RETURNING session_id
                """),
                {"sid": session_id},
            )
            return result.first() is not None

    # ── Message Operations ────────────────────────────────────

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a message to a session.

        Args:
            session_id: Session to add to.
            role: Message role ('user', 'assistant', 'system').
            content: Message content (max 100KB).
            agent_id: Agent that created the message.
            metadata: Optional JSON metadata (token_count, latency, etc).

        Returns:
            Message dict.

        Raises:
            EngineError: If session not found.
        """
        content = content[:MAX_MESSAGE_LENGTH]

        import json as _json

        meta_str = _json.dumps(metadata) if metadata else None

        async with self._db.begin() as conn:
            # Verify session exists
            check = await conn.execute(
                text("""
                    SELECT session_id FROM aria_engine.chat_sessions
                    WHERE session_id = :sid
                """),
                {"sid": session_id},
            )
            if not check.first():
                raise EngineError(f"Session {session_id} not found")

            result = await conn.execute(
                text("""
                    INSERT INTO aria_engine.chat_messages
                        (session_id, role, content, agent_id, metadata)
                    VALUES
                        (:sid, :role, :content, :agent,
                         :meta::jsonb)
                    RETURNING id, session_id, role, content,
                              agent_id, created_at
                """),
                {
                    "sid": session_id,
                    "role": role,
                    "content": content,
                    "agent": agent_id,
                    "meta": meta_str,
                },
            )
            row = result.mappings().first()

            # Touch session updated_at
            await conn.execute(
                text("""
                    UPDATE aria_engine.chat_sessions
                    SET updated_at = NOW()
                    WHERE session_id = :sid
                """),
                {"sid": session_id},
            )

        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "agent_id": row["agent_id"],
            "created_at": row["created_at"].isoformat(),
        }

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a session, ordered chronologically.

        Args:
            session_id: Session ID.
            limit: Max messages to return.
            offset: Offset for pagination.
            since: Only return messages after this datetime.

        Returns:
            List of message dicts.
        """
        params: Dict[str, Any] = {
            "sid": session_id,
            "limit": min(limit, 500),
            "offset": offset,
        }

        since_clause = ""
        if since:
            since_clause = "AND created_at > :since"
            params["since"] = since

        async with self._db.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT id, session_id, role, content,
                           agent_id, metadata, created_at
                    FROM aria_engine.chat_messages
                    WHERE session_id = :sid {since_clause}
                    ORDER BY created_at ASC
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )
            rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "agent_id": row["agent_id"],
                "metadata": dict(row["metadata"]) if row["metadata"] else None,
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]

    async def delete_message(
        self,
        message_id: int,
        session_id: str,
    ) -> bool:
        """Delete a single message (must match session_id for safety)."""
        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    DELETE FROM aria_engine.chat_messages
                    WHERE id = :mid AND session_id = :sid
                    RETURNING id
                """),
                {"mid": message_id, "sid": session_id},
            )
            return result.first() is not None

    # ── Maintenance ───────────────────────────────────────────

    async def prune_old_sessions(
        self,
        days: int = 30,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete sessions older than N days with no recent messages.

        Args:
            days: Sessions inactive for this many days are pruned.
            dry_run: If True, only count without deleting.

        Returns:
            Dict with 'pruned_count' and 'message_count'.
        """
        async with self._db.begin() as conn:
            # Find stale sessions
            result = await conn.execute(
                text("""
                    SELECT s.session_id, COUNT(m.id) AS msg_count
                    FROM aria_engine.chat_sessions s
                    LEFT JOIN aria_engine.chat_messages m
                        ON m.session_id = s.session_id
                    WHERE s.updated_at < NOW() - MAKE_INTERVAL(days => :days)
                    GROUP BY s.session_id
                """),
                {"days": days},
            )
            stale = result.mappings().all()

            if dry_run or not stale:
                return {
                    "pruned_count": len(stale),
                    "message_count": sum(
                        r["msg_count"] for r in stale
                    ),
                    "dry_run": dry_run,
                }

            stale_ids = [r["session_id"] for r in stale]
            placeholders = ", ".join(
                f":s{i}" for i in range(len(stale_ids))
            )
            sparams = {
                f"s{i}": sid for i, sid in enumerate(stale_ids)
            }

            msg_result = await conn.execute(
                text(f"""
                    DELETE FROM aria_engine.chat_messages
                    WHERE session_id IN ({placeholders})
                """),
                sparams,
            )
            msg_count = msg_result.rowcount

            await conn.execute(
                text(f"""
                    DELETE FROM aria_engine.chat_sessions
                    WHERE session_id IN ({placeholders})
                """),
                sparams,
            )

        logger.info(
            "Pruned %d sessions (%d messages, >%d days old)",
            len(stale_ids), msg_count, days,
        )

        return {
            "pruned_count": len(stale_ids),
            "message_count": msg_count,
            "dry_run": False,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(DISTINCT s.session_id) AS total_sessions,
                        COUNT(m.id) AS total_messages,
                        COUNT(DISTINCT s.agent_id) AS active_agents,
                        MIN(s.created_at) AS oldest_session,
                        MAX(s.updated_at) AS newest_activity
                    FROM aria_engine.chat_sessions s
                    LEFT JOIN aria_engine.chat_messages m
                        ON m.session_id = s.session_id
                """)
            )
            row = result.mappings().first()

        return {
            "total_sessions": row["total_sessions"],
            "total_messages": row["total_messages"],
            "active_agents": row["active_agents"],
            "oldest_session": (
                row["oldest_session"].isoformat()
                if row["oldest_session"]
                else None
            ),
            "newest_activity": (
                row["newest_activity"].isoformat()
                if row["newest_activity"]
                else None
            ),
        }

    # ── Internal Helpers ──────────────────────────────────────

    def _row_to_session(self, row) -> Dict[str, Any]:
        """Convert a DB row to a session dict."""
        return {
            "session_id": row["session_id"],
            "title": row["title"],
            "agent_id": row["agent_id"],
            "session_type": row["session_type"],
            "metadata": (
                dict(row["metadata"]) if row["metadata"] else None
            ),
            "message_count": row["message_count"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": (
                row["updated_at"].isoformat()
                if row["updated_at"]
                else None
            ),
            "last_message_at": (
                row["last_message_at"].isoformat()
                if row["last_message_at"]
                else None
            ),
        }
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Session manager at engine infrastructure layer |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from config |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL |
| 5 | aria_memories only writable path | ❌ | No filesystem writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-01 (DB Schema — chat_sessions + chat_messages tables)
- S1-05 (Alembic — migrations applied)

## Verification
```bash
# 1. Module imports:
python -c "
from aria_engine.session_manager import NativeSessionManager
print('OK')
"
# EXPECTED: OK

# 2. Backward-compatible API:
python -c "
import inspect
from aria_engine.session_manager import NativeSessionManager
methods = [m for m in dir(NativeSessionManager) if not m.startswith('_')]
required = ['create_session','get_session','list_sessions','delete_session',
            'add_message','get_messages','end_session','prune_old_sessions']
for r in required:
    assert r in methods, f'Missing: {r}'
print(f'All {len(required)} methods present')
"
# EXPECTED: All 8 methods present

# 3. Constants:
python -c "
from aria_engine.session_manager import MAX_MESSAGE_LENGTH, MAX_TITLE_LENGTH
print(f'Max message: {MAX_MESSAGE_LENGTH}, Max title: {MAX_TITLE_LENGTH}')
"
# EXPECTED: Max message: 100000, Max title: 200
```

## Prompt for Agent
```
Rewrite the session manager as PostgreSQL-native with no filesystem dependencies.

FILES TO READ FIRST:
- aria_skills/session_manager/__init__.py (full file — current filesystem implementation)
- MASTER_PLAN.md (lines 130-150 — chat_sessions + chat_messages DDL)
- aria_engine/session_isolation.py (S4-02 — agent-scoped session queries)

STEPS:
1. Read all files above
2. Create aria_engine/session_manager.py
3. Implement NativeSessionManager class
4. Port all public methods from SessionManagerSkill:
   - create_session → INSERT INTO chat_sessions
   - get_session → SELECT with message count JOIN
   - list_sessions → SELECT with WHERE, ILIKE search, pagination, sort
   - update_session → UPDATE title/metadata
   - delete_session → DELETE messages then session
   - end_session → UPDATE metadata with ended flag
   - add_message → INSERT INTO chat_messages + touch session updated_at
   - get_messages → SELECT with since filter and pagination
5. Add prune_old_sessions() for maintenance
6. Add get_stats() for dashboard
7. Run verification commands

CONSTRAINTS:
- No sessions.json, no JSONL files — everything in PostgreSQL
- Backward-compatible method signatures
- Session IDs: uuid4 hex[:16]
- Max message size: 100KB
- Max page size: 100
- Messages ordered chronologically (ASC)
- Delete messages before session (safe with or without CASCADE)
```
