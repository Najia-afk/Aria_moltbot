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

Uses SQLAlchemy ORM models (EngineChatSession, EngineChatMessage) — no raw SQL.
"""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, insert, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError
from db.models import EngineChatSession, EngineChatMessage

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
        config: EngineConfig | None = None,
    ):
        self.agent_id = agent_id
        self._db_engine = db_engine
        self._config = config
        self._async_session = async_sessionmaker(
            db_engine, expire_on_commit=False,
        )

    async def create_session(
        self,
        title: str | None = None,
        session_type: str = "interactive",
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        context_window: int = 50,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new session scoped to this agent.

        The session is automatically bound to self.agent_id.
        """
        session_id = str(uuid4())

        async with self._async_session() as session:
            async with session.begin():
                obj = EngineChatSession(
                    id=session_id,
                    agent_id=self.agent_id,
                    session_type=session_type,
                    title=title,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    context_window=context_window,
                    metadata_json=metadata or {},
                )
                session.add(obj)

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

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Get a session by ID — only if it belongs to this agent.

        Returns None if the session doesn't exist or belongs to
        another agent (enforcing isolation).
        """
        stmt = (
            select(EngineChatSession)
            .where(
                and_(
                    EngineChatSession.id == session_id,
                    EngineChatSession.agent_id == self.agent_id,
                )
            )
        )

        async with self._async_session() as session:
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()

        if obj is None:
            return None

        return {
            "id": str(obj.id),
            "agent_id": obj.agent_id,
            "session_type": obj.session_type,
            "title": obj.title,
            "system_prompt": obj.system_prompt,
            "model": obj.model,
            "temperature": float(obj.temperature) if obj.temperature else 0.7,
            "max_tokens": obj.max_tokens,
            "context_window": obj.context_window,
            "status": obj.status,
            "message_count": obj.message_count,
            "total_tokens": obj.total_tokens,
            "total_cost": float(obj.total_cost) if obj.total_cost else 0,
            "metadata": dict(obj.metadata_json) if obj.metadata_json else {},
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
            "ended_at": obj.ended_at.isoformat() if obj.ended_at else None,
        }

    async def list_sessions(
        self,
        status: str | None = None,
        session_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List sessions for this agent only.
        """
        conditions = [EngineChatSession.agent_id == self.agent_id]
        if status:
            conditions.append(EngineChatSession.status == status)
        if session_type:
            conditions.append(EngineChatSession.session_type == session_type)

        stmt = (
            select(EngineChatSession)
            .where(and_(*conditions))
            .order_by(EngineChatSession.updated_at.desc())
            .limit(min(limit, 100))
            .offset(offset)
        )

        async with self._async_session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "agent_id": r.agent_id,
                "session_type": r.session_type,
                "title": r.title,
                "status": r.status,
                "model": r.model,
                "message_count": r.message_count,
                "total_tokens": r.total_tokens,
                "total_cost": float(r.total_cost) if r.total_cost else 0,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    async def end_session(self, session_id: str) -> bool:
        """
        End a session (mark as ended). Only works for this agent's sessions.
        """
        stmt = (
            update(EngineChatSession)
            .where(
                and_(
                    EngineChatSession.id == session_id,
                    EngineChatSession.agent_id == self.agent_id,
                    EngineChatSession.status == "active",
                )
            )
            .values(
                status="ended",
                ended_at=func.now(),
                updated_at=func.now(),
            )
        )

        async with self._async_session() as session:
            async with session.begin():
                result = await session.execute(stmt)
                ended = result.rowcount > 0

        if ended:
            logger.info(
                "Ended session %s for agent %s", session_id, self.agent_id
            )
        return ended

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages. Only for this agent.
        Messages cascade-delete via FK.
        """
        stmt = (
            delete(EngineChatSession)
            .where(
                and_(
                    EngineChatSession.id == session_id,
                    EngineChatSession.agent_id == self.agent_id,
                )
            )
        )

        async with self._async_session() as session:
            async with session.begin():
                result = await session.execute(stmt)
                return result.rowcount > 0

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        thinking: str | None = None,
        tool_calls: Any | None = None,
        tool_results: Any | None = None,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        cost: float | None = None,
        latency_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Add a message to a session.

        Validates that the session belongs to this agent before writing.
        """
        # Verify session ownership
        sess = await self.get_session(session_id)
        if sess is None:
            raise EngineError(
                f"Session {session_id} not found for agent {self.agent_id}"
            )

        message_id = str(uuid4())

        async with self._async_session() as session:
            async with session.begin():
                msg = EngineChatMessage(
                    id=message_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    thinking=thinking,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    model=model,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost=cost,
                    latency_ms=latency_ms,
                    metadata_json=metadata or {},
                )
                session.add(msg)

                # Update session counters
                total_tok = (tokens_input or 0) + (tokens_output or 0)
                await session.execute(
                    update(EngineChatSession)
                    .where(
                        and_(
                            EngineChatSession.id == session_id,
                            EngineChatSession.agent_id == self.agent_id,
                        )
                    )
                    .values(
                        message_count=EngineChatSession.message_count + 1,
                        total_tokens=EngineChatSession.total_tokens + total_tok,
                        total_cost=EngineChatSession.total_cost + (cost or 0),
                        updated_at=func.now(),
                    )
                )

        return message_id

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get messages for a session belonging to this agent.
        """
        # Verify session ownership
        sess = await self.get_session(session_id)
        if sess is None:
            raise EngineError(
                f"Session {session_id} not found for agent {self.agent_id}"
            )

        stmt = (
            select(EngineChatMessage)
            .where(EngineChatMessage.session_id == session_id)
            .order_by(EngineChatMessage.created_at.asc())
            .limit(min(limit, 500))
            .offset(offset)
        )

        async with self._async_session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "session_id": str(r.session_id),
                "role": r.role,
                "content": r.content,
                "thinking": r.thinking,
                "tool_calls": r.tool_calls,
                "tool_results": r.tool_results,
                "model": r.model,
                "tokens_input": r.tokens_input,
                "tokens_output": r.tokens_output,
                "cost": float(r.cost) if r.cost else None,
                "latency_ms": r.latency_ms,
                "metadata": dict(r.metadata_json) if r.metadata_json else {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


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
        config: EngineConfig | None = None,
    ):
        self._db_engine = db_engine
        self._config = config
        self._scopes: dict[str, AgentSessionScope] = {}

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

    def list_scopes(self) -> list[str]:
        """List all agent IDs with active scopes."""
        return list(self._scopes.keys())
