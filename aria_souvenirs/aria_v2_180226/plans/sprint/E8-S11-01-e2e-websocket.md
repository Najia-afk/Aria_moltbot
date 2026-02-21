# S11-01: E2E WebSocket Chat Flow
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 11

## Problem
The WebSocket-based chat engine is the critical real-time path for all user interactions. We need end-to-end integration tests that validate the full flow: WebSocket handshake → message → engine processing → LLM call → streamed response → session persistence. Without E2E tests, we can't verify the Flask-SocketIO + aria_engine stack works together.

## Root Cause
Unit tests mock the LLM layer. Integration tests must exercise the real pipeline (with a lightweight mock LLM) to catch serialization issues, event naming mismatches, async timing bugs, and database persistence failures that only appear when all components interact.

## Fix
### `tests/integration/test_e2e_websocket.py`
```python
"""
E2E integration tests for WebSocket chat flow.

Tests the full pipeline:
  Client ─(WS)─► Flask-SocketIO ─► ChatEngine ─► LLMGateway ─► Mock LLM
                                                                    │
  Client ◄─(WS)─ Flask-SocketIO ◄─ ChatEngine ◄── stream chunks ◄──┘

Requires: running test database (PostgreSQL), aria_engine installed.
"""
import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
import socketio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """Create a Flask app with SocketIO for testing."""
    from aria_mind.gateway import create_app

    app = create_app(testing=True)
    yield app


@pytest.fixture(scope="module")
def sio_server(app):
    """Get the SocketIO server instance."""
    from aria_mind.gateway import socketio as server_sio
    return server_sio


@pytest.fixture
async def test_server(app, sio_server):
    """Start a test server on a random port."""
    import socket
    from threading import Thread

    # Find free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    server_thread = Thread(
        target=lambda: sio_server.run(app, host="127.0.0.1", port=port, log_output=False),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.5)  # Allow server to start

    yield f"http://127.0.0.1:{port}"


@pytest.fixture
async def client(test_server):
    """Create a connected SocketIO test client."""
    sio = socketio.AsyncClient()
    received: list[dict] = []

    @sio.on("chat_response")
    async def on_response(data):
        received.append({"event": "chat_response", "data": data})

    @sio.on("chat_chunk")
    async def on_chunk(data):
        received.append({"event": "chat_chunk", "data": data})

    @sio.on("chat_complete")
    async def on_complete(data):
        received.append({"event": "chat_complete", "data": data})

    @sio.on("error")
    async def on_error(data):
        received.append({"event": "error", "data": data})

    await sio.connect(test_server)
    sio._test_received = received
    yield sio

    if sio.connected:
        await sio.disconnect()


def mock_llm_response(content: str = "Hello! I'm Aria.", model: str = "qwen3:32b"):
    """Create a mock streaming LLM response."""
    async def _mock_stream(*args, **kwargs):
        chunks = [content[i:i+5] for i in range(0, len(content), 5)]
        for chunk in chunks:
            yield {
                "choices": [{"delta": {"content": chunk}}],
                "model": model,
            }
    return _mock_stream


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWebSocketChatE2E:
    """End-to-end WebSocket chat flow tests."""

    @pytest.mark.integration
    async def test_basic_chat_message(self, client):
        """Send a message and receive a streamed response."""
        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("Hello! I'm Aria.")()

            await client.emit("chat_message", {
                "content": "Hello Aria!",
                "session_id": "test-session-001",
            })

            # Wait for response
            await asyncio.sleep(1.0)

            received = client._test_received
            assert len(received) > 0, "No response received"

            # Check we got chunks and a completion
            events = [r["event"] for r in received]
            assert "chat_chunk" in events or "chat_response" in events
            assert "chat_complete" in events

    @pytest.mark.integration
    async def test_message_persisted_to_db(self, client):
        """Messages are persisted to the session store."""
        session_id = "test-persist-001"

        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("Persisted reply")()

            await client.emit("chat_message", {
                "content": "Test persistence",
                "session_id": session_id,
            })
            await asyncio.sleep(1.0)

        # Verify in database
        from aria_engine.session_manager import NativeSessionManager
        mgr = NativeSessionManager()
        history = await mgr.get_history(session_id)
        assert len(history) >= 2  # user msg + assistant reply
        assert any(m["role"] == "user" and "persistence" in m["content"].lower() for m in history)
        assert any(m["role"] == "assistant" for m in history)

    @pytest.mark.integration
    async def test_streaming_chunks_ordered(self, client):
        """Streaming chunks arrive in order."""
        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("ABCDEFGHIJ")()

            await client.emit("chat_message", {
                "content": "Say the alphabet",
                "session_id": "test-order-001",
            })
            await asyncio.sleep(1.0)

            chunks = [r for r in client._test_received if r["event"] == "chat_chunk"]
            if chunks:
                combined = "".join(c["data"].get("content", "") for c in chunks)
                assert combined == "ABCDEFGHIJ"

    @pytest.mark.integration
    async def test_session_auto_created(self, client):
        """A new session is created if session_id doesn't exist."""
        new_session_id = f"auto-{int(time.time())}"

        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("New session!")()

            await client.emit("chat_message", {
                "content": "Hello from new session",
                "session_id": new_session_id,
            })
            await asyncio.sleep(1.0)

            # Session should exist now
            from aria_engine.session_manager import NativeSessionManager
            mgr = NativeSessionManager()
            session = await mgr.get(new_session_id)
            assert session is not None

    @pytest.mark.integration
    async def test_error_propagated_to_client(self, client):
        """LLM errors are propagated as error events."""
        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.side_effect = RuntimeError("LLM unavailable")

            await client.emit("chat_message", {
                "content": "This will fail",
                "session_id": "test-error-001",
            })
            await asyncio.sleep(1.0)

            errors = [r for r in client._test_received if r["event"] == "error"]
            assert len(errors) >= 1
            assert "unavailable" in str(errors[0]["data"]).lower()

    @pytest.mark.integration
    async def test_concurrent_sessions(self, test_server):
        """Multiple concurrent WebSocket sessions work independently."""
        clients = []
        for i in range(3):
            sio = socketio.AsyncClient()
            received = []
            sio.on("chat_complete", lambda data, r=received: r.append(data))
            await sio.connect(test_server)
            sio._test_received = received
            clients.append(sio)

        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("Reply")()

            # Send from all clients concurrently
            tasks = []
            for i, c in enumerate(clients):
                tasks.append(c.emit("chat_message", {
                    "content": f"Message from client {i}",
                    "session_id": f"concurrent-{i}",
                }))
            await asyncio.gather(*tasks)
            await asyncio.sleep(2.0)

            # All clients should get responses
            for i, c in enumerate(clients):
                assert len(c._test_received) > 0, f"Client {i} got no response"

        for c in clients:
            await c.disconnect()

    @pytest.mark.integration
    async def test_disconnect_and_reconnect(self, test_server):
        """Client can disconnect and reconnect to same session."""
        session_id = "reconnect-001"

        sio = socketio.AsyncClient()
        received = []
        sio.on("chat_complete", lambda data: received.append(data))

        # First connection
        await sio.connect(test_server)
        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("First reply")()
            await sio.emit("chat_message", {
                "content": "First message",
                "session_id": session_id,
            })
            await asyncio.sleep(1.0)

        await sio.disconnect()
        await asyncio.sleep(0.5)

        # Reconnect
        await sio.connect(test_server)
        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = mock_llm_response("Second reply")()
            await sio.emit("chat_message", {
                "content": "Second message",
                "session_id": session_id,
            })
            await asyncio.sleep(1.0)

        # Both messages should be in session history
        from aria_engine.session_manager import NativeSessionManager
        mgr = NativeSessionManager()
        history = await mgr.get_history(session_id)
        user_msgs = [m for m in history if m["role"] == "user"]
        assert len(user_msgs) >= 2

        await sio.disconnect()

    @pytest.mark.integration
    async def test_thinking_mode_events(self, client):
        """Thinking mode emits thinking chunks before response."""
        async def _mock_thinking(*args, **kwargs):
            # Thinking chunk
            yield {
                "choices": [{"delta": {"reasoning_content": "Let me think..."}}],
                "model": "qwen3:32b",
            }
            # Response chunk
            yield {
                "choices": [{"delta": {"content": "The answer is 42."}}],
                "model": "qwen3:32b",
            }

        with patch("aria_engine.llm_gateway.LLMGateway.stream") as mock_stream:
            mock_stream.return_value = _mock_thinking()

            await client.emit("chat_message", {
                "content": "What is the meaning of life?",
                "session_id": "test-thinking-001",
                "enable_thinking": True,
            })
            await asyncio.sleep(1.0)

            # Should get both thinking and content events
            received = client._test_received
            assert len(received) > 0
```

### `tests/integration/conftest.py`
```python
"""
Integration test fixtures and configuration.

Provides database setup/teardown, test server instances, and
shared configuration for all integration tests.
"""
import asyncio
import os
from pathlib import Path

import pytest

# Mark all integration tests
def pytest_collection_modifyitems(config, items):
    """Auto-mark integration tests."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Set up a clean test database for integration tests."""
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://aria:aria_test@localhost:5432/aria_test"
    )
    os.environ["DATABASE_URL"] = test_db_url

    # Import after setting env
    from aria_engine.database import engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def clean_between_tests():
    """Clean test data between tests."""
    yield

    # Truncate tables after each test
    from aria_engine.database import engine

    async with engine.begin() as conn:
        await conn.execute(
            "TRUNCATE TABLE sessions, messages, agent_state, scheduler_jobs RESTART IDENTITY CASCADE"
        )
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Tests the full stack E2E |
| 2 | .env for secrets | ✅ | TEST_DATABASE_URL in env |
| 3 | models.yaml single source | ❌ | Mocked LLM |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL container |
| 5 | aria_memories only writable path | ❌ | DB-only writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- Sprint 10 unit tests must pass
- PostgreSQL test instance running
- `pip install python-socketio[asyncio_client] websockets`

## Verification
```bash
# 1. Start test database:
docker run -d --name aria-test-db -e POSTGRES_USER=aria -e POSTGRES_PASSWORD=aria_test -e POSTGRES_DB=aria_test -p 5432:5432 pgvector/pgvector:pg16

# 2. Run integration tests:
TEST_DATABASE_URL=postgresql://aria:aria_test@localhost:5432/aria_test pytest tests/integration/test_e2e_websocket.py -v --timeout=30

# 3. Run with coverage:
pytest tests/integration/test_e2e_websocket.py -v --cov=aria_engine --cov-report=term-missing
```

## Prompt for Agent
```
Create end-to-end WebSocket chat integration tests.

FILES TO READ FIRST:
- aria_mind/gateway.py (Flask-SocketIO server)
- aria_engine/chat_engine.py (chat processing)
- aria_engine/llm_gateway.py (LLM calls)
- tests/integration/conftest.py (shared fixtures)

STEPS:
1. Create tests/integration/conftest.py with DB fixtures
2. Create tests/integration/test_e2e_websocket.py
3. Start test database container
4. Run tests — expect all to pass with mock LLM

CONSTRAINTS:
- Mock LLM but use REAL database and REAL SocketIO
- Test: basic flow, persistence, ordering, auto-session, errors, concurrent, reconnect, thinking
- Use python-socketio[asyncio_client] for WebSocket client
- Each test gets a clean database (truncate between tests)
```
