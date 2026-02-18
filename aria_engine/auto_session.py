"""
Auto-Session Lifecycle — transparent session management.

Features:
- Auto-create session on first message (no explicit create step)
- Auto-title from first user message (truncated to 100 chars)
- Auto-close after configurable idle timeout (default 30 min)
- Auto-rotate after message limit or duration limit
- Background idle scanner (runs on scheduler)
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError
from aria_engine.session_manager import NativeSessionManager

logger = logging.getLogger("aria.engine.auto_session")

# Configurable limits
IDLE_TIMEOUT_MINUTES = 30
MAX_MESSAGES_PER_SESSION = 200
MAX_SESSION_DURATION_HOURS = 8
AUTO_TITLE_MAX_LENGTH = 100
IDLE_SCAN_INTERVAL_MINUTES = 5


def generate_auto_title(first_message: str) -> str:
    """
    Generate a session title from the first user message.

    Strips whitespace, truncates to 100 chars, adds ellipsis
    if truncated. Falls back to timestamp if message is empty.

    Args:
        first_message: The first user message content.

    Returns:
        Session title string.
    """
    text_clean = first_message.strip()
    if not text_clean:
        return f"Session {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    # Take first line only
    first_line = text_clean.split("\n")[0].strip()
    if not first_line:
        first_line = text_clean[:AUTO_TITLE_MAX_LENGTH]

    if len(first_line) > AUTO_TITLE_MAX_LENGTH:
        return first_line[: AUTO_TITLE_MAX_LENGTH - 3] + "..."

    return first_line


class AutoSessionManager:
    """
    Transparent session lifecycle manager.

    Wraps NativeSessionManager to add automatic session
    creation, titling, idle timeout, and rotation.

    Usage:
        auto = AutoSessionManager(db_engine, session_manager)

        # Just send a message — session created automatically
        result = await auto.ensure_session_and_message(
            agent_id="aria-talk",
            session_id=None,        # auto-create
            role="user",
            content="How's the weather?",
        )
        # result["session_id"] → newly created session
        # result["auto_created"] → True
        # Session titled "How's the weather?"

        # Subsequent messages use the returned session_id
        result2 = await auto.ensure_session_and_message(
            agent_id="aria-talk",
            session_id=result["session_id"],
            role="user",
            content="Follow-up question",
        )
        # result2["auto_created"] → False

        # Idle timeout: background scanner closes abandoned sessions
        stats = await auto.close_idle_sessions()
        # stats["closed_count"] → N sessions closed
    """

    def __init__(
        self,
        db_engine: AsyncEngine,
        session_manager: NativeSessionManager,
        idle_timeout_minutes: int = IDLE_TIMEOUT_MINUTES,
        max_messages: int = MAX_MESSAGES_PER_SESSION,
        max_duration_hours: int = MAX_SESSION_DURATION_HOURS,
    ):
        self._db = db_engine
        self._mgr = session_manager
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self._max_messages = max_messages
        self._max_duration = timedelta(hours=max_duration_hours)

    async def ensure_session_and_message(
        self,
        agent_id: str,
        role: str,
        content: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ensure a session exists and add a message to it.

        If session_id is None, auto-creates a new session.
        If session exists but needs rotation, creates a new one.
        Auto-titles new sessions from first user message.

        Args:
            agent_id: Owning agent.
            role: Message role ('user', 'assistant', 'system').
            content: Message content.
            session_id: Existing session ID, or None for auto-create.
            metadata: Optional message metadata.

        Returns:
            Dict with session_id, message_id, auto_created,
            rotated (if session was rotated to a new one).
        """
        auto_created = False
        rotated = False

        if session_id:
            # Check if session exists and needs rotation
            session = await self._mgr.get_session(session_id)

            if not session:
                # Session not found — create new
                session_id = None
            elif await self._needs_rotation(session):
                # Rotate: end old session, create new
                await self._mgr.end_session(session_id)
                session_id = None
                rotated = True
                logger.info(
                    "Rotated session %s (limit reached)",
                    session["session_id"],
                )

        if not session_id:
            # Auto-create
            title = (
                generate_auto_title(content)
                if role == "user"
                else None
            )
            session = await self._mgr.create_session(
                agent_id=agent_id,
                title=title,
                session_type="chat",
            )
            session_id = session["session_id"]
            auto_created = True

        # Add the message
        message = await self._mgr.add_message(
            session_id=session_id,
            role=role,
            content=content,
            agent_id=agent_id,
            metadata=metadata,
        )

        # Auto-title: if this is the first user message in an
        # existing session without a meaningful title
        if role == "user" and not auto_created:
            await self._maybe_auto_title(session_id, content)

        return {
            "session_id": session_id,
            "message_id": message["id"],
            "auto_created": auto_created,
            "rotated": rotated,
        }

    async def _needs_rotation(
        self,
        session: Dict[str, Any],
    ) -> bool:
        """
        Check if a session should be rotated to a new one.

        Rotation triggers:
        - Message count exceeds MAX_MESSAGES_PER_SESSION
        - Session duration exceeds MAX_SESSION_DURATION_HOURS
        - Session is marked as ended

        Args:
            session: Session dict from NativeSessionManager.

        Returns:
            True if session needs rotation.
        """
        # Already ended
        meta = session.get("metadata") or {}
        if meta.get("ended"):
            return True

        # Message count limit
        if session.get("message_count", 0) >= self._max_messages:
            return True

        # Duration limit
        created_str = session.get("created_at")
        if created_str:
            created = datetime.fromisoformat(created_str)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if (now - created) > self._max_duration:
                return True

        return False

    async def _maybe_auto_title(
        self,
        session_id: str,
        content: str,
    ) -> None:
        """
        Auto-title a session if it has a generic title.

        Only updates if the current title matches the auto-generated
        default pattern ("Session XXXXXXXX").
        """
        session = await self._mgr.get_session(session_id)
        if not session:
            return

        title = session.get("title", "")
        if title.startswith("Session ") and len(title) <= 16:
            new_title = generate_auto_title(content)
            await self._mgr.update_session(
                session_id=session_id,
                title=new_title,
            )

    async def close_idle_sessions(
        self,
        idle_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Close sessions that have been idle beyond the timeout.

        Called by the scheduler or manually. Sets ended=true in
        metadata for idle sessions.

        Args:
            idle_minutes: Override idle timeout (default from config).

        Returns:
            Dict with 'closed_count' and 'session_ids'.
        """
        timeout = timedelta(
            minutes=idle_minutes or self._idle_timeout.total_seconds() / 60
        )
        cutoff = datetime.now(timezone.utc) - timeout

        async with self._db.begin() as conn:
            # Find idle sessions that aren't already ended
            result = await conn.execute(
                text("""
                    SELECT s.session_id
                    FROM aria_engine.chat_sessions s
                    WHERE s.updated_at < :cutoff
                      AND (
                          s.metadata IS NULL
                          OR NOT (s.metadata ? 'ended')
                          OR s.metadata->>'ended' = 'false'
                      )
                      AND s.session_type = 'chat'
                """),
                {"cutoff": cutoff},
            )
            idle_ids = [row[0] for row in result.fetchall()]

            if idle_ids:
                placeholders = ", ".join(
                    f":s{i}" for i in range(len(idle_ids))
                )
                params = {
                    f"s{i}": sid for i, sid in enumerate(idle_ids)
                }

                await conn.execute(
                    text(f"""
                        UPDATE aria_engine.chat_sessions
                        SET metadata = COALESCE(metadata, '{{}}'::jsonb)
                            || '{{"ended": true, "end_reason": "idle_timeout"}}'::jsonb,
                            updated_at = NOW()
                        WHERE session_id IN ({placeholders})
                    """),
                    params,
                )

        if idle_ids:
            logger.info(
                "Closed %d idle sessions (>%d min inactive)",
                len(idle_ids),
                int(timeout.total_seconds() / 60),
            )

        return {
            "closed_count": len(idle_ids),
            "session_ids": idle_ids,
        }

    async def get_or_create_session(
        self,
        agent_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get an existing active session or create a new one.

        Convenience method for API handlers that need a session
        before the first message.

        Returns:
            Session dict (existing or newly created).
        """
        if session_id:
            session = await self._mgr.get_session(session_id)
            if session:
                meta = session.get("metadata") or {}
                if not meta.get("ended"):
                    return session

        # Create new
        return await self._mgr.create_session(
            agent_id=agent_id,
            session_type="chat",
        )
