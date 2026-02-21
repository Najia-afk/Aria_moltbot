# S2-03: WebSocket Streaming (StreamManager)
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 5 | **Phase:** 2

## Problem
Chat responses must stream in real-time — token by token — so the dashboard feels responsive. OpenClaw handled streaming internally; the Python side never received streaming tokens. We need a `StreamManager` that bridges `LLMGateway.stream()` to a FastAPI WebSocket connection, with a well-defined protocol for content tokens, thinking tokens, tool call events, and error handling.

## Root Cause
The `LLMGateway.stream()` (S1-02) returns an async generator of `StreamChunk` objects, but there's nothing to consume it and forward chunks to a client over WebSocket. FastAPI supports WebSocket endpoints natively, but no WebSocket infrastructure exists in the codebase. The existing session API (`src/api/routers/sessions.py`) is entirely REST-based. The dashboard's `/clawdbot/` chat page connects to OpenClaw's WebSocket — that endpoint disappears when we remove OpenClaw.

## Fix
### `aria_engine/streaming.py`
```python
"""
Stream Manager — WebSocket streaming for chat responses.

Bridges LLMGateway.stream() to FastAPI WebSocket connections with:
- Structured JSON protocol (token, thinking, tool_call, tool_result, done, error)
- Full response accumulation for DB persistence after stream completes
- Graceful disconnection handling (saves partial response)
- Ping/pong keepalive every 30 seconds
- Connection lifecycle management

Protocol:
  Client → Server:
    {"type": "message", "content": "Hello!", "enable_thinking": false}
    {"type": "ping"}

  Server → Client:
    {"type": "token", "content": "Hello"}
    {"type": "thinking", "content": "Let me consider..."}
    {"type": "tool_call", "name": "search", "arguments": {"q": "..."}, "id": "tc_1"}
    {"type": "tool_result", "name": "search", "content": "...", "id": "tc_1", "success": true}
    {"type": "usage", "input_tokens": 100, "output_tokens": 50, "cost": 0.001}
    {"type": "done", "message_id": "uuid", "finish_reason": "stop"}
    {"type": "error", "message": "..."}
    {"type": "pong"}
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SessionError, LLMError
from aria_engine.llm_gateway import LLMGateway, StreamChunk
from aria_engine.tool_registry import ToolRegistry, ToolResult

logger = logging.getLogger("aria.engine.stream")


@dataclass
class StreamAccumulator:
    """Accumulates a full response from stream chunks for DB persistence."""
    content: str = ""
    thinking: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    finish_reason: str = ""
    started_at: float = 0.0
    model: str = ""

    @property
    def latency_ms(self) -> int:
        if self.started_at:
            return int((time.monotonic() - self.started_at) * 1000)
        return 0


class StreamManager:
    """
    Manages WebSocket streaming chat sessions.

    Usage:
        manager = StreamManager(config, gateway, tool_registry, db_factory)

        # In a FastAPI WebSocket endpoint:
        @app.websocket("/ws/chat/{session_id}")
        async def chat_ws(websocket: WebSocket, session_id: str):
            await manager.handle_connection(websocket, session_id)
    """

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
        self._db_factory = db_session_factory
        self._active_connections: Dict[str, WebSocket] = {}

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        """
        Handle a WebSocket connection for a chat session.

        Lifecycle:
        1. Accept connection
        2. Validate session exists and is active
        3. Start keepalive task
        4. Listen for messages and stream responses
        5. Clean up on disconnect
        """
        await websocket.accept()
        connection_id = f"{session_id}:{uuid.uuid4().hex[:8]}"
        self._active_connections[connection_id] = websocket

        logger.info("WebSocket connected: %s", connection_id)

        # Start keepalive task
        keepalive_task = asyncio.create_task(
            self._keepalive(websocket, connection_id)
        )

        try:
            # Validate session
            await self._validate_session(session_id)

            # Listen for messages
            while True:
                try:
                    raw = await websocket.receive_text()
                    data = json.loads(raw)

                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await self._send_json(websocket, {"type": "pong"})

                    elif msg_type == "message":
                        content = data.get("content", "").strip()
                        if not content:
                            await self._send_json(websocket, {
                                "type": "error",
                                "message": "Empty message content",
                            })
                            continue

                        enable_thinking = data.get("enable_thinking", False)
                        enable_tools = data.get("enable_tools", True)

                        await self._handle_message(
                            websocket=websocket,
                            session_id=session_id,
                            content=content,
                            enable_thinking=enable_thinking,
                            enable_tools=enable_tools,
                        )

                    else:
                        await self._send_json(websocket, {
                            "type": "error",
                            "message": f"Unknown message type: {msg_type}",
                        })

                except json.JSONDecodeError:
                    await self._send_json(websocket, {
                        "type": "error",
                        "message": "Invalid JSON",
                    })

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: %s", connection_id)
        except Exception as e:
            logger.error("WebSocket error in %s: %s", connection_id, e)
            try:
                await self._send_json(websocket, {
                    "type": "error",
                    "message": str(e),
                })
            except Exception:
                pass
        finally:
            keepalive_task.cancel()
            self._active_connections.pop(connection_id, None)
            logger.info("WebSocket cleaned up: %s", connection_id)

    async def _handle_message(
        self,
        websocket: WebSocket,
        session_id: str,
        content: str,
        enable_thinking: bool = False,
        enable_tools: bool = True,
    ) -> None:
        """
        Handle a single chat message: persist user msg, stream LLM response,
        handle tool calls, persist assistant msg.
        """
        from db.models import EngineChatSession, EngineChatMessage

        accumulator = StreamAccumulator(started_at=time.monotonic())

        async with self._db_factory() as db:
            # Load session
            from sqlalchemy import select
            result = await db.execute(
                select(EngineChatSession).where(
                    EngineChatSession.id == uuid.UUID(session_id)
                )
            )
            session = result.scalar_one_or_none()
            if session is None:
                await self._send_json(websocket, {
                    "type": "error",
                    "message": f"Session {session_id} not found",
                })
                return

            if session.status == "ended":
                await self._send_json(websocket, {
                    "type": "error",
                    "message": f"Session {session_id} has ended",
                })
                return

            accumulator.model = session.model or self.config.default_model

            # Persist user message
            user_msg_id = uuid.uuid4()
            user_msg = EngineChatMessage(
                id=user_msg_id,
                session_id=uuid.UUID(session_id),
                role="user",
                content=content,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user_msg)
            await db.flush()

            # Build conversation context
            messages = await self._build_context(db, session, content)
            tools_for_llm = self.tools.get_tools_for_llm() if enable_tools else None

            # ── Stream LLM response ───────────────────────────────────────
            max_tool_iterations = 10
            for iteration in range(max_tool_iterations):
                try:
                    async for chunk in self.gateway.stream(
                        messages=messages,
                        model=session.model,
                        temperature=session.temperature,
                        max_tokens=session.max_tokens,
                        tools=tools_for_llm,
                        enable_thinking=enable_thinking,
                    ):
                        if not await self._is_connected(websocket):
                            logger.warning("Client disconnected during stream")
                            break

                        # Stream thinking tokens
                        if chunk.thinking:
                            accumulator.thinking += chunk.thinking
                            await self._send_json(websocket, {
                                "type": "thinking",
                                "content": chunk.thinking,
                            })

                        # Stream content tokens
                        if chunk.content:
                            accumulator.content += chunk.content
                            await self._send_json(websocket, {
                                "type": "token",
                                "content": chunk.content,
                            })

                        # Capture finish reason
                        if chunk.finish_reason:
                            accumulator.finish_reason = chunk.finish_reason

                except LLMError as e:
                    await self._send_json(websocket, {
                        "type": "error",
                        "message": f"LLM error: {e}",
                    })
                    break

                # Check for tool calls in accumulated content
                # (For streaming, tool calls come via the gateway's finish data)
                # If the model requested tool calls, we re-call non-streaming
                if accumulator.finish_reason == "tool_calls":
                    # Fall back to non-streaming for tool call execution
                    try:
                        llm_response = await self.gateway.complete(
                            messages=messages,
                            model=session.model,
                            temperature=session.temperature,
                            max_tokens=session.max_tokens,
                            tools=tools_for_llm,
                            enable_thinking=enable_thinking,
                        )
                    except LLMError as e:
                        await self._send_json(websocket, {
                            "type": "error",
                            "message": f"Tool call LLM error: {e}",
                        })
                        break

                    if not llm_response.tool_calls:
                        # No tool calls after all — use the response content
                        accumulator.content = llm_response.content
                        accumulator.thinking = llm_response.thinking or accumulator.thinking
                        break

                    # Execute tool calls
                    accumulator.tool_calls.extend(llm_response.tool_calls)
                    messages.append({
                        "role": "assistant",
                        "content": llm_response.content or "",
                        "tool_calls": llm_response.tool_calls,
                    })

                    for tc in llm_response.tool_calls:
                        # Notify client about tool call
                        await self._send_json(websocket, {
                            "type": "tool_call",
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                            "id": tc["id"],
                        })

                        # Execute tool
                        tool_result: ToolResult = await self.tools.execute(
                            tool_call_id=tc["id"],
                            function_name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        )

                        accumulator.tool_results.append({
                            "tool_call_id": tool_result.tool_call_id,
                            "name": tool_result.name,
                            "content": tool_result.content,
                            "success": tool_result.success,
                            "duration_ms": tool_result.duration_ms,
                        })

                        # Notify client about tool result
                        await self._send_json(websocket, {
                            "type": "tool_result",
                            "name": tool_result.name,
                            "content": tool_result.content,
                            "id": tool_result.tool_call_id,
                            "success": tool_result.success,
                        })

                        # Add to messages for next LLM turn
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_result.tool_call_id,
                            "content": tool_result.content,
                        })

                        # Persist tool message
                        tool_msg = EngineChatMessage(
                            id=uuid.uuid4(),
                            session_id=uuid.UUID(session_id),
                            role="tool",
                            content=tool_result.content,
                            tool_results={
                                "tool_call_id": tc["id"],
                                "name": tc["function"]["name"],
                            },
                            latency_ms=tool_result.duration_ms,
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(tool_msg)

                    # Reset accumulator content for next stream
                    accumulator.content = ""
                    accumulator.finish_reason = ""
                    continue  # Re-stream with tool results

                # No tool calls — done
                break

            # ── Persist assistant message ─────────────────────────────────
            assistant_msg_id = uuid.uuid4()
            assistant_msg = EngineChatMessage(
                id=assistant_msg_id,
                session_id=uuid.UUID(session_id),
                role="assistant",
                content=accumulator.content,
                thinking=accumulator.thinking or None,
                tool_calls=accumulator.tool_calls if accumulator.tool_calls else None,
                tool_results=accumulator.tool_results if accumulator.tool_results else None,
                model=accumulator.model,
                tokens_input=accumulator.input_tokens,
                tokens_output=accumulator.output_tokens,
                cost=accumulator.cost_usd,
                latency_ms=accumulator.latency_ms,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_msg)

            # ── Update session counters ───────────────────────────────────
            msg_count = 2 + len(accumulator.tool_results)
            session.message_count = (session.message_count or 0) + msg_count
            session.total_tokens = (
                (session.total_tokens or 0)
                + accumulator.input_tokens
                + accumulator.output_tokens
            )
            session.total_cost = float(session.total_cost or 0) + accumulator.cost_usd
            session.updated_at = datetime.now(timezone.utc)

            # Auto-title on first message
            if not session.title and (session.message_count or 0) <= msg_count:
                title = content.strip().replace("\n", " ")
                title = " ".join(title.split())
                if len(title) > 80:
                    title = title[:77] + "..."
                session.title = title

            await db.commit()

            # ── Send usage + done ─────────────────────────────────────────
            await self._send_json(websocket, {
                "type": "usage",
                "input_tokens": accumulator.input_tokens,
                "output_tokens": accumulator.output_tokens,
                "cost": accumulator.cost_usd,
            })

            await self._send_json(websocket, {
                "type": "done",
                "message_id": str(assistant_msg_id),
                "finish_reason": accumulator.finish_reason,
            })

    async def _validate_session(self, session_id: str) -> None:
        """Validate that a session exists and is active."""
        from db.models import EngineChatSession
        from sqlalchemy import select

        async with self._db_factory() as db:
            result = await db.execute(
                select(EngineChatSession.status).where(
                    EngineChatSession.id == uuid.UUID(session_id)
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise SessionError(f"Session {session_id} not found")
            if row == "ended":
                raise SessionError(f"Session {session_id} has ended")

    async def _build_context(
        self,
        db,
        session,
        current_content: str,
    ) -> List[Dict[str, Any]]:
        """Build conversation context from DB messages (same as ChatEngine)."""
        from db.models import EngineChatMessage
        from sqlalchemy import select

        messages: List[Dict[str, Any]] = []

        if session.system_prompt:
            messages.append({"role": "system", "content": session.system_prompt})

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

        messages.append({"role": "user", "content": current_content})
        return messages

    async def _keepalive(self, websocket: WebSocket, connection_id: str) -> None:
        """Send ping every ws_ping_interval seconds to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(self.config.ws_ping_interval)
                if await self._is_connected(websocket):
                    await self._send_json(websocket, {"type": "pong"})
                else:
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    @staticmethod
    async def _is_connected(websocket: WebSocket) -> bool:
        """Check if WebSocket is still connected."""
        return websocket.client_state == WebSocketState.CONNECTED

    @staticmethod
    async def _send_json(websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Send JSON data over WebSocket, silently catching disconnection."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps(data))
        except Exception:
            pass  # Client disconnected — swallow

    @property
    def active_connections(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._active_connections)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | StreamManager accesses DB via ORM, calls LLMGateway + ToolRegistry |
| 2 | .env for secrets (zero in code) | ✅ | All config via EngineConfig from env |
| 3 | models.yaml single source of truth | ✅ | Model resolved via LLMGateway |
| 4 | Docker-first testing | ✅ | WebSocket runs in FastAPI container |
| 5 | aria_memories only writable path | ❌ | Writes to PostgreSQL only |
| 6 | No soul modification | ❌ | Reads system_prompt from session |

## Dependencies
- S1-01 must complete first (aria_engine package)
- S1-02 must complete first (LLMGateway.stream)
- S1-04 must complete first (ToolRegistry)
- S1-05 must complete first (ORM models)
- S2-01 should complete first (ChatEngine pattern for context building)

## Verification
```bash
# 1. Module imports:
python -c "from aria_engine.streaming import StreamManager, StreamAccumulator; print('OK')"
# EXPECTED: OK

# 2. StreamAccumulator:
python -c "
import time
from aria_engine.streaming import StreamAccumulator
acc = StreamAccumulator(started_at=time.monotonic())
acc.content = 'Hello'
acc.thinking = 'Let me think...'
assert acc.content == 'Hello'
assert acc.latency_ms >= 0
print('StreamAccumulator OK')
"
# EXPECTED: StreamAccumulator OK

# 3. Protocol message types are documented:
python -c "
import ast, inspect
from aria_engine import streaming
source = inspect.getsource(streaming)
for msg_type in ['token', 'thinking', 'tool_call', 'tool_result', 'done', 'error', 'pong', 'usage']:
    assert f'\"type\": \"{msg_type}\"' in source or f\"'type': '{msg_type}'\" in source or f'\"{msg_type}\"' in source, f'Missing {msg_type}'
print('All protocol types present')
"
# EXPECTED: All protocol types present
```

## Prompt for Agent
```
Implement WebSocket streaming for Aria Engine chat responses.

FILES TO READ FIRST:
- aria_engine/config.py (EngineConfig — ws_ping_interval, ws_ping_timeout — created in S1-01)
- aria_engine/llm_gateway.py (LLMGateway.stream, StreamChunk — created in S1-02)
- aria_engine/tool_registry.py (ToolRegistry.execute — created in S1-04)
- aria_engine/chat_engine.py (ChatEngine — created in S2-01, reference for context building)
- src/api/db/models.py (EngineChatSession, EngineChatMessage — created in S1-05)

STEPS:
1. Read all files above
2. Create aria_engine/streaming.py with StreamManager class
3. Implement handle_connection() — WebSocket lifecycle manager
4. Implement _handle_message() — stream LLM response with tool call handling
5. Implement StreamAccumulator for response accumulation
6. Implement _keepalive() — ping/pong every 30s
7. Implement _validate_session() — DB session check
8. Implement _build_context() — conversation history loading
9. Run verification commands

CONSTRAINTS:
- Protocol: JSON messages with well-defined types
- Always persist full response to DB after stream completes
- Handle disconnection gracefully — save partial response
- Keepalive ping every config.ws_ping_interval seconds (default 30)
- Max 10 tool call iterations to prevent infinite loops
```
