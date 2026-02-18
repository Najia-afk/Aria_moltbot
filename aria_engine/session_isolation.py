"""
Per-Agent Session Isolation — ensures agents only see their own sessions.

Provides:
- Agent-scoped session factory for DB operations
- Session creation with automatic agent_id binding
- Query filters that enforce agent boundaries
- Shared resource management via dependency injection
- No cross-agent message leaking

All session operations go through AgentSessionScope, which transparently
adds agent_id filters to every query.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError

logger = logging.getLogger("aria.engine.session_isolation")


class AgentSessionScope:
    """
    Scoped session manager for a specific agent.

    All operations are automatically filtered by agent_id — an agent
    can never access another agent's sessions or messages.

    Usage:
        scope = AgentSessionScope("main", db_engine)
        sessions = await scope.list_sessions()
        session = await scope.create_session(title="Work Cycle")
        messages = await scope.get_messages(session_id)
    """

    def __init__(
        self,
        agent_id: str,
        db_engine: AsyncEngine,
        config: Optional[EngineConfig] = None,
    ):
        self.agent_id = agent_id
        self._db_engine = db_engine
        self._config = config

    async def create_session(
        self,
        title: Optional[str] = None,
        session_type: str = "interactive",
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 50,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new session scoped to this agent.

        The session is automatically bound to self.agent_id.

        Args:
            title: Session title (auto-generated if None).
            session_type: 'interactive', 'cron', 'roundtable', etc.
            model: LLM model override.
            system_prompt: System prompt override.
            temperature: LLM temperature.
            max_tokens: LLM max tokens.
            context_window: Number of messages to include in context.
            metadata: Additional metadata dict.

        Returns:
            Dict with the created session's fields.
        """
        session_id = str(uuid4())

        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO aria_engine.chat_sessions
                        (id, agent_id, session_type, title, system_prompt,
                         model, temperature, max_tokens, context_window,
                         status, metadata)
                    VALUES
                        (:id, :agent_id, :session_type, :title, :system_prompt,
                         :model, :temperature, :max_tokens, :context_window,
                         'active', :metadata)
                """),
                {
                    "id": session_id,
                    "agent_id": self.agent_id,
                    "session_type": session_type,
                    "title": title,
                    "system_prompt": system_prompt,
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "context_window": context_window,
                    "metadata": metadata or {},
                },
            )

        logger.info(
            "Created session %s for agent %s (type=%s)",
            session_id,
            self.agent_id,
            session_type,
        )

        return {
            "id": session_id,
            "agent_id": self.agent_id,
            "session_type": session_type,
            "title": title,
            "model": model,
            "status": "active",
        }

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID — only if it belongs to this agent.

        Returns None if the session doesn't exist or belongs to
        another agent (enforcing isolation).
        """
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, agent_id, session_type, title, system_prompt,
                           model, temperature, max_tokens, context_window,
                           status, message_count, total_tokens, total_cost,
                           metadata, created_at, updated_at, ended_at
                    FROM aria_engine.chat_sessions
                    WHERE id = :session_id
                      AND agent_id = :agent_id
                """),
                {"session_id": session_id, "agent_id": self.agent_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def list_sessions(
        self,
        status: Optional[str] = None,
        session_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List sessions for this agent only.

        Args:
            status: Filter by status ('active', 'ended', etc.).
            session_type: Filter by type ('interactive', 'cron', etc.).
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of session dicts, always filtered by agent_id.
        """
        conditions = ["agent_id = :agent_id"]
        params: Dict[str, Any] = {
            "agent_id": self.agent_id,
            "limit": limit,
            "offset": offset,
        }

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if session_type:
            conditions.append("session_type = :session_type")
            params["session_type"] = session_type

        where = " AND ".join(conditions)

        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT id, agent_id, session_type, title, status,
                           model, message_count, total_tokens, total_cost,
                           created_at, updated_at
                    FROM aria_engine.chat_sessions
                    WHERE {where}
                    ORDER BY updated_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )
            return [dict(row) for row in result.mappings().all()]

    async def end_session(self, session_id: str) -> bool:
        """
        End a session (mark as ended). Only works for this agent's sessions.

        Returns:
            True if the session was ended.
        """
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    UPDATE aria_engine.chat_sessions
                    SET status = 'ended',
                        ended_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :session_id
                      AND agent_id = :agent_id
                      AND status = 'active'
                """),
                {"session_id": session_id, "agent_id": self.agent_id},
            )
            ended = result.rowcount > 0

        if ended:
            logger.info(
                "Ended session %s for agent %s", session_id, self.agent_id
            )
        return ended

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages. Only for this agent.

        Returns:
            True if the session was deleted.
        """
        async with self._db_engine.begin() as conn:
            # Messages cascade-delete via FK
            result = await conn.execute(
                text("""
                    DELETE FROM aria_engine.chat_sessions
                    WHERE id = :session_id
                      AND agent_id = :agent_id
                """),
                {"session_id": session_id, "agent_id": self.agent_id},
            )
            return result.rowcount > 0

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_calls: Optional[Any] = None,
        tool_results: Optional[Any] = None,
        model: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        cost: Optional[float] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a message to a session.

        Validates that the session belongs to this agent before writing.

        Args:
            session_id: Target session.
            role: Message role (user, assistant, system, tool).
            content: Message content.
            thinking: Reasoning tokens (if any).
            tool_calls: Tool call payloads.
            tool_results: Tool execution results.
            model: Model used for this message.
            tokens_input: Input token count.
            tokens_output: Output token count.
            cost: Cost in USD.
            latency_ms: Response latency.
            metadata: Additional metadata.

        Returns:
            The message UUID.

        Raises:
            EngineError: If session doesn't belong to this agent.
        """
        # Verify session ownership
        session = await self.get_session(session_id)
        if session is None:
            raise EngineError(
                f"Session {session_id} not found for agent {self.agent_id}"
            )

        message_id = str(uuid4())

        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO aria_engine.chat_messages
                        (id, session_id, role, content, thinking,
                         tool_calls, tool_results, model,
                         tokens_input, tokens_output, cost,
                         latency_ms, metadata)
                    VALUES
                        (:id, :session_id, :role, :content, :thinking,
                         :tool_calls, :tool_results, :model,
                         :tokens_input, :tokens_output, :cost,
                         :latency_ms, :metadata)
                """),
                {
                    "id": message_id,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "thinking": thinking,
                    "tool_calls": tool_calls,
                    "tool_results": tool_results,
                    "model": model,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "cost": cost,
                    "latency_ms": latency_ms,
                    "metadata": metadata or {},
                },
            )

            # Update session counters
            await conn.execute(
                text("""
                    UPDATE aria_engine.chat_sessions
                    SET message_count = message_count + 1,
                        total_tokens = total_tokens + COALESCE(:tokens, 0),
                        total_cost = total_cost + COALESCE(:cost, 0),
                        updated_at = NOW()
                    WHERE id = :session_id
                      AND agent_id = :agent_id
                """),
                {
                    "session_id": session_id,
                    "agent_id": self.agent_id,
                    "tokens": (tokens_input or 0) + (tokens_output or 0),
                    "cost": cost,
                },
            )

        return message_id

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a session belonging to this agent.

        Returns:
            List of message dicts, ordered by created_at.

        Raises:
            EngineError: If session doesn't belong to this agent.
        """
        # Verify session ownership
        session = await self.get_session(session_id)
        if session is None:
            raise EngineError(
                f"Session {session_id} not found for agent {self.agent_id}"
            )

        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, session_id, role, content, thinking,
                           tool_calls, tool_results, model,
                           tokens_input, tokens_output, cost,
                           latency_ms, metadata, created_at
                    FROM aria_engine.chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at ASC
                    LIMIT :limit OFFSET :offset
                """),
                {
                    "session_id": session_id,
                    "limit": limit,
                    "offset": offset,
                },
            )
            return [dict(row) for row in result.mappings().all()]


class SessionIsolationFactory:
    """
    Factory for creating agent-scoped session managers.

    Shared resources (DB pool, config) are injected once;
    per-agent scopes are created on demand.

    Usage:
        factory = SessionIsolationFactory(db_engine, config)
        main_scope = factory.for_agent("main")
        talk_scope = factory.for_agent("aria-talk")
        # main_scope and talk_scope share the DB pool but
        # have completely isolated session views.
    """

    def __init__(
        self,
        db_engine: AsyncEngine,
        config: Optional[EngineConfig] = None,
    ):
        self._db_engine = db_engine
        self._config = config
        self._scopes: Dict[str, AgentSessionScope] = {}

    def for_agent(self, agent_id: str) -> AgentSessionScope:
        """
        Get or create an AgentSessionScope for the given agent.

        Scopes are cached for reuse within the same process.
        """
        if agent_id not in self._scopes:
            self._scopes[agent_id] = AgentSessionScope(
                agent_id=agent_id,
                db_engine=self._db_engine,
                config=self._config,
            )
        return self._scopes[agent_id]

    def list_scopes(self) -> List[str]:
        """List all agent IDs with active scopes."""
        return list(self._scopes.keys())
