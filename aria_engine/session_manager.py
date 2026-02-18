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
from typing import Any
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
        title: str | None = None,
        session_type: str = "chat",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any] | None:
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
        agent_id: str | None = None,
        session_type: str | None = None,
        search: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        sort: str = "updated_at",
        order: str = "desc",
    ) -> dict[str, Any]:
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
        params: dict[str, Any] = {"limit": limit, "offset": offset}

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
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update session title and/or metadata."""
        sets = ["updated_at = NOW()"]
        params: dict[str, Any] = {"sid": session_id}

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
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
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
        params: dict[str, Any] = {
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
    ) -> dict[str, Any]:
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

    async def get_stats(self) -> dict[str, Any]:
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

    def _row_to_session(self, row) -> dict[str, Any]:
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
