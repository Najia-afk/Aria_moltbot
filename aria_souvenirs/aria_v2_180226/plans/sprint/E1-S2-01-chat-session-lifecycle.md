# S2-01: Chat Session Lifecycle (ChatEngine)
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 5 | **Phase:** 2

## Problem
There is no native chat engine for managing session lifecycle. Currently, chat sessions are managed by OpenClaw's Node.js gateway which writes `sessions.json` + `.jsonl` transcripts to the filesystem. The `session_manager` skill (`aria_skills/session_manager/__init__.py`) is tightly coupled to OpenClaw's filesystem layout (`/root/.openclaw/agents/`). We need a `ChatEngine` class that manages the full lifecycle — create, resume, end, send message — entirely via PostgreSQL using the `EngineChatSession` and `EngineChatMessage` ORM models created in S1-05.

## Root Cause
The session lifecycle was always owned by OpenClaw. The Python side only had read-only access via filesystem sync (`src/api/routers/sessions.py` lines 1-150: sync logic via `OPENCLAW_SESSIONS_INDEX_PATH`). The `session_manager` skill reads `sessions.json` from the mounted OpenClaw volume. No Python code has ever *created* or *managed* chat sessions natively. The S1-05 migration created the ORM models (`EngineChatSession`, `EngineChatMessage`), but no business logic exists to operate on them.

## Fix
### `aria_engine/chat_engine.py`
```python
"""
Chat Engine — Native session lifecycle management.

Replaces OpenClaw's session management with PostgreSQL-backed sessions.
Features:
- Create/resume/end sessions with full state tracking
- Send messages with LLM completion and tool calling
- Auto-generate session titles from first user message
- Track token counts and costs per message and per session
- Context window integration for conversation history
- Tool call loop: LLM → tool → result → LLM until done

Uses:
- EngineChatSession / EngineChatMessage ORM models (S1-05)
- LLMGateway for completions (S1-02)
- ToolRegistry for function calling (S1-04)
- ThinkingHandler for reasoning tokens (S1-03)
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SessionError, LLMError
from aria_engine.llm_gateway import LLMGateway, LLMResponse
from aria_engine.tool_registry import ToolRegistry, ToolResult
from aria_engine.thinking import extract_thinking_from_response, strip_thinking_from_content

logger = logging.getLogger("aria.engine.chat")


@dataclass
class ChatResponse:
    """Response from a chat message."""
    message_id: str
    session_id: str
    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "content": self.content,
            "thinking": self.thinking,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
        }


class ChatEngine:
    """
    Native chat session lifecycle manager.

    Usage:
        engine = ChatEngine(config, gateway, tool_registry, db_session_factory)

        # Create a new session:
        session = await engine.create_session(agent_id="main", model="qwen3-30b-mlx")

        # Send a message and get a response:
        response = await engine.send_message(session.id, "Hello, Aria!")

        # Resume an existing session:
        session = await engine.resume_session(session_id)

        # End a session:
        await engine.end_session(session_id)
    """

    # Maximum tool call iterations to prevent infinite loops
    MAX_TOOL_ITERATIONS = 10

    def __init__(
        self,
        config: EngineConfig,
        gateway: LLMGateway,
        tool_registry: ToolRegistry,
        db_session_factory,
    ):
        self.config = config
        self.gateway = gateway
        self.tools = tool_registry
        self._db_factory = db_session_factory  # async sessionmaker

    async def create_session(
        self,
        agent_id: str = "main",
        model: Optional[str] = None,
        session_type: str = "interactive",
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        context_window: int = 50,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new chat session.

        Args:
            agent_id: Agent owning this session.
            model: LLM model to use (defaults to config.default_model).
            session_type: 'interactive', 'cron', 'subagent', etc.
            system_prompt: Override system prompt (normally assembled by PromptAssembler).
            temperature: Override temperature.
            max_tokens: Override max tokens.
            context_window: Number of messages to keep in context.
            metadata: Arbitrary JSON metadata.

        Returns:
            Dict with session fields (id, agent_id, model, status, …).
        """
        # Import ORM models lazily to avoid circular imports at module level
        from db.models import EngineChatSession

        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        async with self._db_factory() as db:
            session = EngineChatSession(
                id=session_id,
                agent_id=agent_id,
                session_type=session_type,
                model=model or self.config.default_model,
                temperature=temperature or self.config.default_temperature,
                max_tokens=max_tokens or self.config.default_max_tokens,
                context_window=context_window,
                system_prompt=system_prompt,
                status="active",
                message_count=0,
                total_tokens=0,
                total_cost=0,
                metadata_json=metadata or {},
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

            logger.info(
                "Created session %s for agent=%s model=%s",
                session_id, agent_id, session.model,
            )

            return self._session_to_dict(session)

    async def resume_session(self, session_id: str | uuid.UUID) -> Dict[str, Any]:
        """
        Resume an existing session by ID.

        Raises SessionError if session not found or already ended.
        Returns session dict with message history.
        """
        from db.models import EngineChatSession, EngineChatMessage

        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id

        async with self._db_factory() as db:
            result = await db.execute(
                select(EngineChatSession).where(EngineChatSession.id == sid)
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise SessionError(f"Session {sid} not found")

            if session.status == "ended":
                raise SessionError(f"Session {sid} has already ended")

            # Load messages ordered by creation time
            msg_result = await db.execute(
                select(EngineChatMessage)
                .where(EngineChatMessage.session_id == sid)
                .order_by(EngineChatMessage.created_at.asc())
            )
            messages = msg_result.scalars().all()

            session_dict = self._session_to_dict(session)
            session_dict["messages"] = [self._message_to_dict(m) for m in messages]
            return session_dict

    async def end_session(self, session_id: str | uuid.UUID) -> Dict[str, Any]:
        """
        End (close) a session. Marks status='ended' and sets ended_at.

        Returns the final session dict.
        """
        from db.models import EngineChatSession

        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
        now = datetime.now(timezone.utc)

        async with self._db_factory() as db:
            result = await db.execute(
                select(EngineChatSession).where(EngineChatSession.id == sid)
            )
            session = result.scalar_one_or_none()

            if session is None:
                raise SessionError(f"Session {sid} not found")

            session.status = "ended"
            session.ended_at = now
            session.updated_at = now
            await db.commit()
            await db.refresh(session)

            logger.info("Ended session %s", sid)
            return self._session_to_dict(session)

    async def send_message(
        self,
        session_id: str | uuid.UUID,
        content: str,
        *,
        enable_thinking: bool = False,
        enable_tools: bool = True,
        context_messages: Optional[List[Dict[str, str]]] = None,
    ) -> ChatResponse:
        """
        Send a user message and get an assistant response.

        Flow:
        1. Persist user message to DB
        2. Build message list (system prompt + context window)
        3. Call LLMGateway.complete() with tools
        4. If tool_calls returned — execute each, append results, re-call LLM
        5. Persist assistant message (and tool messages) to DB
        6. Update session counters (message_count, total_tokens, total_cost)
        7. Auto-generate title from first user message if none set
        8. Return ChatResponse

        Args:
            session_id: Target session.
            content: User message text.
            enable_thinking: Request reasoning tokens from the model.
            enable_tools: Whether to provide tool definitions to the LLM.
            context_messages: Pre-built context (from ContextManager). If None,
                              loads last N messages from DB.

        Returns:
            ChatResponse with assistant content, thinking, tool_calls, usage.
        """
        from db.models import EngineChatSession, EngineChatMessage

        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
        overall_start = time.monotonic()

        async with self._db_factory() as db:
            # ── 1. Load session ───────────────────────────────────────────
            result = await db.execute(
                select(EngineChatSession).where(EngineChatSession.id == sid)
            )
            session = result.scalar_one_or_none()
            if session is None:
                raise SessionError(f"Session {sid} not found")
            if session.status == "ended":
                raise SessionError(f"Session {sid} has ended — create a new session")

            # ── 2. Persist user message ───────────────────────────────────
            user_msg_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            user_msg = EngineChatMessage(
                id=user_msg_id,
                session_id=sid,
                role="user",
                content=content,
                created_at=now,
            )
            db.add(user_msg)
            await db.flush()

            # ── 3. Build conversation context ─────────────────────────────
            if context_messages is not None:
                messages = list(context_messages)
            else:
                messages = await self._build_context(db, session, content)

            # ── 4. LLM completion with tool-call loop ─────────────────────
            tools_for_llm = self.tools.get_tools_for_llm() if enable_tools else None
            accumulated_tool_calls: List[Dict[str, Any]] = []
            accumulated_tool_results: List[Dict[str, Any]] = []
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost = 0.0
            final_content = ""
            final_thinking = None
            final_finish_reason = ""

            for iteration in range(self.MAX_TOOL_ITERATIONS):
                try:
                    llm_response: LLMResponse = await self.gateway.complete(
                        messages=messages,
                        model=session.model,
                        temperature=session.temperature,
                        max_tokens=session.max_tokens,
                        tools=tools_for_llm,
                        enable_thinking=enable_thinking,
                    )
                except LLMError as e:
                    logger.error("LLM call failed in session %s: %s", sid, e)
                    raise SessionError(f"LLM call failed: {e}") from e

                total_input_tokens += llm_response.input_tokens
                total_output_tokens += llm_response.output_tokens
                total_cost += llm_response.cost_usd
                final_content = llm_response.content
                final_thinking = llm_response.thinking or final_thinking
                final_finish_reason = llm_response.finish_reason

                # No tool calls — done
                if not llm_response.tool_calls:
                    break

                # ── 4a. Execute tool calls ────────────────────────────────
                accumulated_tool_calls.extend(llm_response.tool_calls)

                # Append assistant message with tool_calls to conversation
                messages.append({
                    "role": "assistant",
                    "content": llm_response.content or "",
                    "tool_calls": llm_response.tool_calls,
                })

                for tc in llm_response.tool_calls:
                    tool_result: ToolResult = await self.tools.execute(
                        tool_call_id=tc["id"],
                        function_name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    )
                    accumulated_tool_results.append({
                        "tool_call_id": tool_result.tool_call_id,
                        "name": tool_result.name,
                        "content": tool_result.content,
                        "success": tool_result.success,
                        "duration_ms": tool_result.duration_ms,
                    })

                    # Append tool result to conversation for next LLM turn
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result.tool_call_id,
                        "content": tool_result.content,
                    })

                    # Persist tool result as a message
                    tool_msg = EngineChatMessage(
                        id=uuid.uuid4(),
                        session_id=sid,
                        role="tool",
                        content=tool_result.content,
                        tool_results={"tool_call_id": tc["id"], "name": tc["function"]["name"]},
                        latency_ms=tool_result.duration_ms,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(tool_msg)

            # ── 5. Persist assistant message ──────────────────────────────
            elapsed_ms = int((time.monotonic() - overall_start) * 1000)
            assistant_msg_id = uuid.uuid4()
            assistant_msg = EngineChatMessage(
                id=assistant_msg_id,
                session_id=sid,
                role="assistant",
                content=final_content,
                thinking=final_thinking,
                tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                tool_results=accumulated_tool_results if accumulated_tool_results else None,
                model=session.model,
                tokens_input=total_input_tokens,
                tokens_output=total_output_tokens,
                cost=total_cost,
                latency_ms=elapsed_ms,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_msg)

            # ── 6. Update session counters ────────────────────────────────
            new_msg_count = 2  # user + assistant
            if accumulated_tool_results:
                new_msg_count += len(accumulated_tool_results)

            session.message_count = (session.message_count or 0) + new_msg_count
            session.total_tokens = (session.total_tokens or 0) + total_input_tokens + total_output_tokens
            session.total_cost = float(session.total_cost or 0) + total_cost
            session.updated_at = datetime.now(timezone.utc)

            # ── 7. Auto-generate title from first message ─────────────────
            if not session.title and session.message_count <= 2:
                session.title = self._generate_title(content)

            await db.commit()

            logger.info(
                "Message in session %s: in=%d out=%d cost=%.6f latency=%dms tools=%d",
                sid, total_input_tokens, total_output_tokens,
                total_cost, elapsed_ms, len(accumulated_tool_calls),
            )

            return ChatResponse(
                message_id=str(assistant_msg_id),
                session_id=str(sid),
                content=final_content,
                thinking=final_thinking,
                tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                tool_results=accumulated_tool_results if accumulated_tool_results else None,
                model=session.model or "",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_input_tokens + total_output_tokens,
                cost_usd=total_cost,
                latency_ms=elapsed_ms,
                finish_reason=final_finish_reason,
            )

    # ── Private helpers ───────────────────────────────────────────────────

    async def _build_context(
        self,
        db: AsyncSession,
        session,
        current_content: str,
    ) -> List[Dict[str, str]]:
        """
        Build conversation context from DB messages.

        Always includes:
        - System prompt (if set on session)
        - Last N messages up to context_window limit
        - Current user message
        """
        from db.models import EngineChatMessage

        messages: List[Dict[str, str]] = []

        # System prompt
        if session.system_prompt:
            messages.append({"role": "system", "content": session.system_prompt})

        # Load recent messages from DB (up to context_window)
        window = session.context_window or 50
        result = await db.execute(
            select(EngineChatMessage)
            .where(EngineChatMessage.session_id == session.id)
            .order_by(EngineChatMessage.created_at.desc())
            .limit(window)
        )
        db_messages = list(reversed(result.scalars().all()))

        for msg in db_messages:
            entry: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.role == "tool" and msg.tool_results:
                entry["tool_call_id"] = msg.tool_results.get("tool_call_id", "")
            messages.append(entry)

        # Append current user message
        messages.append({"role": "user", "content": current_content})

        return messages

    @staticmethod
    def _generate_title(first_message: str) -> str:
        """
        Generate a short session title from the first user message.
        Truncates to 80 chars and adds ellipsis if needed.
        """
        # Strip whitespace and newlines
        title = first_message.strip().replace("\n", " ").replace("\r", "")
        # Remove excessive whitespace
        title = " ".join(title.split())
        if len(title) > 80:
            title = title[:77] + "..."
        return title

    @staticmethod
    def _session_to_dict(session) -> Dict[str, Any]:
        """Convert ORM session to plain dict."""
        return {
            "id": str(session.id),
            "agent_id": session.agent_id,
            "session_type": session.session_type,
            "title": session.title,
            "model": session.model,
            "temperature": session.temperature,
            "max_tokens": session.max_tokens,
            "context_window": session.context_window,
            "status": session.status,
            "message_count": session.message_count,
            "total_tokens": session.total_tokens,
            "total_cost": float(session.total_cost or 0),
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "metadata": session.metadata_json if hasattr(session, "metadata_json") else {},
        }

    @staticmethod
    def _message_to_dict(msg) -> Dict[str, Any]:
        """Convert ORM message to plain dict."""
        return {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "role": msg.role,
            "content": msg.content,
            "thinking": msg.thinking,
            "tool_calls": msg.tool_calls,
            "tool_results": msg.tool_results,
            "model": msg.model,
            "tokens_input": msg.tokens_input,
            "tokens_output": msg.tokens_output,
            "cost": float(msg.cost) if msg.cost else None,
            "latency_ms": msg.latency_ms,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | ChatEngine operates at the engine layer, accesses DB via ORM only |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from env via EngineConfig |
| 3 | models.yaml single source of truth | ✅ | Model resolved through LLMGateway which uses models.yaml |
| 4 | Docker-first testing | ✅ | Uses async DB session factory — works in Docker |
| 5 | aria_memories only writable path | ❌ | Writes to PostgreSQL only (not filesystem) |
| 6 | No soul modification | ❌ | Reads system_prompt from session, never modifies soul |

## Dependencies
- S1-01 must complete first (aria_engine package structure)
- S1-02 must complete first (LLMGateway.complete)
- S1-04 must complete first (ToolRegistry.execute)
- S1-05 must complete first (EngineChatSession, EngineChatMessage ORM models)

## Verification
```bash
# 1. Module imports:
python -c "from aria_engine.chat_engine import ChatEngine, ChatResponse; print('OK')"
# EXPECTED: OK

# 2. ChatResponse dataclass:
python -c "
from aria_engine.chat_engine import ChatResponse
r = ChatResponse(message_id='m1', session_id='s1', content='Hello')
d = r.to_dict()
assert d['content'] == 'Hello'
assert d['total_tokens'] == 0
print('ChatResponse OK')
"
# EXPECTED: ChatResponse OK

# 3. Title generation:
python -c "
from aria_engine.chat_engine import ChatEngine
title = ChatEngine._generate_title('What is the meaning of life, the universe, and everything in the context of modern philosophy?')
assert len(title) <= 80
assert title.endswith('...')
print(f'Title: {title}')
"
# EXPECTED: Title: What is the meaning of life, the universe, and everything in the context...
```

## Prompt for Agent
```
Implement the ChatEngine — the core session lifecycle manager for Aria Engine.

FILES TO READ FIRST:
- aria_engine/config.py (EngineConfig — created in S1-01)
- aria_engine/exceptions.py (SessionError, LLMError — created in S1-01)
- aria_engine/llm_gateway.py (LLMGateway.complete, LLMResponse — created in S1-02)
- aria_engine/tool_registry.py (ToolRegistry.execute, ToolResult — created in S1-04)
- aria_engine/thinking.py (extract_thinking_from_response — created in S1-03)
- src/api/db/models.py (EngineChatSession, EngineChatMessage — created in S1-05)
- aria_skills/session_manager/__init__.py (lines 1-100 — understand current OpenClaw-coupled pattern)
- aria_mind/cognition.py (lines 152-300 — understand current process() flow for context)

STEPS:
1. Read all files above
2. Create aria_engine/chat_engine.py with ChatEngine class
3. Implement create_session() — creates EngineChatSession in DB
4. Implement resume_session() — loads session + messages from DB
5. Implement end_session() — marks session as ended
6. Implement send_message() — full LLM call loop with tool execution
7. Implement _build_context() — loads recent messages as conversation
8. Implement _generate_title() — auto-title from first message
9. Add ChatResponse dataclass with to_dict()
10. Run verification commands

CONSTRAINTS:
- Constraint 1: Access DB via ORM only — never raw SQL
- Constraint 2: DATABASE_URL from environment
- Constraint 3: Model comes from session.model, resolved via LLMGateway
- MAX_TOOL_ITERATIONS=10 to prevent infinite tool-call loops
```
