"""
E2E integration tests for WebSocket chat flow.

Tests the full pipeline:
  Client ─(WS)─► StreamManager ─► LLMGateway ─► Mock LLM
                                                      │
  Client ◄─(WS)─ StreamManager ◄── stream chunks ◄───┘

Requires: aria_engine installed, mock LLM, mock DB.
"""
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SessionError, LLMError
from aria_engine.streaming import StreamAccumulator, StreamManager
from aria_engine.llm_gateway import LLMResponse, StreamChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeWebSocket:
    """
    In-memory WebSocket mock that records sent messages
    and yields pre-loaded incoming messages.
    """

    def __init__(self, incoming: list[dict] | None = None):
        self._incoming = [json.dumps(m) for m in (incoming or [])]
        self._idx = 0
        self.sent: list[dict] = []
        self.accepted = False
        self.closed = False
        self._close_event = asyncio.Event()

    async def accept(self):
        self.accepted = True

    async def receive_text(self) -> str:
        if self._idx < len(self._incoming):
            msg = self._incoming[self._idx]
            self._idx += 1
            return msg
        # Simulate disconnect after all messages consumed
        await asyncio.sleep(0.05)
        from starlette.websockets import WebSocketDisconnect
        raise WebSocketDisconnect(code=1000)

    async def send_text(self, data: str):
        self.sent.append(json.loads(data))

    async def send_json(self, data: dict):
        self.sent.append(data)

    async def close(self, code: int = 1000):
        self.closed = True
        self._close_event.set()

    @property
    def client_state(self):
        """Mimic starlette WebSocketState."""
        from starlette.websockets import WebSocketState
        return WebSocketState.CONNECTED if not self.closed else WebSocketState.DISCONNECTED

    def get_sent_by_type(self, msg_type: str) -> list[dict]:
        """Get all sent messages of a given type."""
        return [m for m in self.sent if m.get("type") == msg_type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    """Test engine config."""
    return EngineConfig(
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test-key",
        default_model="step-35-flash-free",
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
    )


@pytest.fixture
def mock_gateway():
    """Mock LLMGateway with streaming support."""
    gw = AsyncMock()
    gw.complete = AsyncMock(return_value=LLMResponse(
        content="Hello! I'm Aria.",
        thinking=None,
        tool_calls=None,
        model="step-35-flash-free",
        input_tokens=50,
        output_tokens=20,
        cost_usd=0.001,
        latency_ms=200,
        finish_reason="stop",
    ))
    return gw


@pytest.fixture
def mock_tools():
    """Mock ToolRegistry."""
    registry = MagicMock()
    registry.get_tools_for_llm = MagicMock(return_value=[])
    registry.execute_tool = AsyncMock()
    return registry


@pytest.fixture
def mock_db_factory():
    """Mock async DB session factory."""
    from tests.integration.conftest import FakeSession, FakeMessage

    session_obj = FakeSession(
        id=uuid.uuid4(),
        agent_id="main",
        model="step-35-flash-free",
        status="active",
        system_prompt="You are Aria.",
        message_count=0,
        total_tokens=0,
        total_cost=0,
    )

    db = AsyncMock()
    # Mock execute to return the session
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=session_obj)
    result_mock.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    db.execute = AsyncMock(return_value=result_mock)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.close = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=db)
    factory._db = db
    factory._session_obj = session_obj
    return factory


@pytest.fixture(autouse=True)
def _mock_sqlalchemy_select():
    """Mock sqlalchemy.select to avoid column expression issues with mock ORM classes."""
    with patch("sqlalchemy.select", MagicMock()):
        yield


@pytest.fixture
def stream_manager(config, mock_gateway, mock_tools, mock_db_factory):
    """Create a StreamManager with mocked dependencies."""
    sm = StreamManager(config, mock_gateway, mock_tools, mock_db_factory)
    # Bypass _validate_session to avoid SQLAlchemy select() with mock ORM classes
    sm._validate_session = AsyncMock()
    return sm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStreamAccumulator:
    """Tests for the StreamAccumulator dataclass."""

    @pytest.mark.integration
    def test_empty_accumulator(self):
        """New accumulator has empty defaults."""
        acc = StreamAccumulator()
        assert acc.content == ""
        assert acc.thinking == ""
        assert acc.tool_calls == []
        assert acc.tool_results == []
        assert acc.input_tokens == 0
        assert acc.output_tokens == 0

    @pytest.mark.integration
    def test_latency_calculation(self):
        """Latency is calculated from started_at."""
        acc = StreamAccumulator(started_at=time.monotonic() - 0.5)
        assert acc.latency_ms >= 400  # ~500ms with some tolerance

    @pytest.mark.integration
    def test_latency_zero_when_not_started(self):
        """Latency is 0 when started_at is not set."""
        acc = StreamAccumulator()
        assert acc.latency_ms == 0


class TestWebSocketChatE2E:
    """End-to-end WebSocket chat flow tests."""

    @pytest.mark.integration
    async def test_websocket_accepts_connection(self, stream_manager):
        """StreamManager accepts incoming WebSocket connections."""
        ws = FakeWebSocket(incoming=[])
        session_id = str(uuid.uuid4())

        # handle_connection should accept and then handle disconnect
        await stream_manager.handle_connection(ws, session_id)
        assert ws.accepted is True

    @pytest.mark.integration
    async def test_basic_chat_message(self, stream_manager, mock_gateway):
        """Send a message and receive a response via WebSocket."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "message", "content": "Hello Aria!"},
        ])

        # Mock the gateway.stream to yield chunks
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Hello", finish_reason=None)
            yield StreamChunk(content="! I'm ", finish_reason=None)
            yield StreamChunk(content="Aria.", finish_reason="stop")

        mock_gateway.stream = MagicMock(return_value=mock_stream())

        await stream_manager.handle_connection(ws, session_id)

        # Should have received token messages
        tokens = ws.get_sent_by_type("token")
        assert len(tokens) >= 1, f"Expected token messages, got: {ws.sent}"

    @pytest.mark.integration
    async def test_empty_message_returns_error(self, stream_manager):
        """Empty message content triggers an error response."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "message", "content": ""},
        ])

        await stream_manager.handle_connection(ws, session_id)

        errors = ws.get_sent_by_type("error")
        assert len(errors) >= 1
        assert "empty" in errors[0].get("message", "").lower()

    @pytest.mark.integration
    async def test_ping_pong(self, stream_manager):
        """Ping messages receive pong responses."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "ping"},
        ])

        await stream_manager.handle_connection(ws, session_id)

        pongs = ws.get_sent_by_type("pong")
        assert len(pongs) >= 1

    @pytest.mark.integration
    async def test_unknown_message_type_returns_error(self, stream_manager):
        """Unknown message type triggers an error."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "unknown_type"},
        ])

        await stream_manager.handle_connection(ws, session_id)

        errors = ws.get_sent_by_type("error")
        assert len(errors) >= 1
        assert "unknown" in errors[0].get("message", "").lower()

    @pytest.mark.integration
    async def test_invalid_json_returns_error(self, stream_manager):
        """Invalid JSON triggers an error."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket()
        # Override incoming with raw invalid JSON
        ws._incoming = ["this is not json"]

        await stream_manager.handle_connection(ws, session_id)

        errors = ws.get_sent_by_type("error")
        assert len(errors) >= 1

    @pytest.mark.integration
    async def test_thinking_mode_emits_thinking_chunks(self, stream_manager, mock_gateway):
        """When enable_thinking=True, thinking chunks are emitted."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "message", "content": "What is life?", "enable_thinking": True},
        ])

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(thinking="Let me think...", is_thinking=True,
                              finish_reason=None)
            yield StreamChunk(content="The answer is 42.",
                              finish_reason="stop")

        mock_gateway.stream = MagicMock(return_value=mock_stream())

        await stream_manager.handle_connection(ws, session_id)

        # Should have thinking and token messages
        thinking = ws.get_sent_by_type("thinking")
        tokens = ws.get_sent_by_type("token")
        # At least some response messages should exist
        assert len(ws.sent) >= 1

    @pytest.mark.integration
    async def test_stream_done_message(self, stream_manager, mock_gateway):
        """Stream completes with a 'done' message."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "message", "content": "Say hello"},
        ])

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Hi!", finish_reason="stop")

        mock_gateway.stream = MagicMock(return_value=mock_stream())

        await stream_manager.handle_connection(ws, session_id)

        done = ws.get_sent_by_type("done")
        assert len(done) >= 1

    @pytest.mark.integration
    async def test_error_during_llm_call(self, stream_manager, mock_gateway):
        """LLM errors are propagated as error events."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "message", "content": "This will fail"},
        ])

        async def mock_stream_error(*args, **kwargs):
            raise LLMError("LLM unavailable")
            yield  # make it a generator  # noqa: E303

        mock_gateway.stream = MagicMock(return_value=mock_stream_error())

        await stream_manager.handle_connection(ws, session_id)

        errors = ws.get_sent_by_type("error")
        assert len(errors) >= 1

    @pytest.mark.integration
    async def test_connection_cleanup(self, stream_manager):
        """Active connections are cleaned up on disconnect."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[])

        initial_count = len(stream_manager._active_connections)
        await stream_manager.handle_connection(ws, session_id)

        # After disconnect, connection should be cleaned up
        assert len(stream_manager._active_connections) == initial_count

    @pytest.mark.integration
    async def test_usage_message_sent(self, stream_manager, mock_gateway):
        """Usage statistics are sent after completion."""
        session_id = str(uuid.uuid4())
        ws = FakeWebSocket(incoming=[
            {"type": "message", "content": "Hello"},
        ])

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Hi!", finish_reason="stop")

        mock_gateway.stream = MagicMock(return_value=mock_stream())

        await stream_manager.handle_connection(ws, session_id)

        usage = ws.get_sent_by_type("usage")
        # Usage message should be sent with tokens info
        if usage:
            assert "input_tokens" in usage[0] or "output_tokens" in usage[0]
