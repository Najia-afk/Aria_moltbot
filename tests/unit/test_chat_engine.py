"""
Unit tests for aria_engine.chat_engine.ChatEngine.

Tests:
- Session lifecycle (create, resume, end)
- Message sending and persistence
- Auto-title generation
- Context window assembly
- Tool call loop
- Token tracking and cost calculation
"""
import sys
import uuid
from datetime import datetime, timezone
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SessionError, LLMError

# ── Mock db.models BEFORE importing ChatEngine ──────────────────────────
# ChatEngine uses lazy imports: `from db.models import EngineChatSession, EngineChatMessage`
# We create mock ORM classes so those imports resolve.

_mock_db_module = ModuleType("db")
_mock_db_models = ModuleType("db.models")


class _FakeSession:
    """Mock ORM session model."""

    # Class-level attributes to mimic SQLAlchemy Column descriptors.
    # These allow expressions like `EngineChatSession.id == sid` to not raise
    # AttributeError when select() is already mocked.
    id = MagicMock()
    agent_id = MagicMock()
    session_id = MagicMock()
    status = MagicMock()

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        # Defaults
        self.id = kwargs.get("id", uuid.uuid4())
        self.agent_id = kwargs.get("agent_id", "main")
        self.session_type = kwargs.get("session_type", "interactive")
        self.model = kwargs.get("model", "step-35-flash-free")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)
        self.context_window = kwargs.get("context_window", 50)
        self.system_prompt = kwargs.get("system_prompt", None)
        self.status = kwargs.get("status", "active")
        self.title = kwargs.get("title", None)
        self.message_count = kwargs.get("message_count", 0)
        self.total_tokens = kwargs.get("total_tokens", 0)
        self.total_cost = kwargs.get("total_cost", 0)
        self.metadata_json = kwargs.get("metadata_json", {})
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
        self.ended_at = kwargs.get("ended_at", None)


class _FakeMessage:
    """Mock ORM message model."""

    # Class-level attributes to mimic SQLAlchemy Column descriptors.
    id = MagicMock()
    session_id = MagicMock()
    created_at = MagicMock()
    role = MagicMock()

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.id = kwargs.get("id", uuid.uuid4())
        self.session_id = kwargs.get("session_id", uuid.uuid4())
        self.role = kwargs.get("role", "user")
        self.content = kwargs.get("content", "")
        self.thinking = kwargs.get("thinking", None)
        self.tool_calls = kwargs.get("tool_calls", None)
        self.tool_results = kwargs.get("tool_results", None)
        self.model = kwargs.get("model", None)
        self.tokens_input = kwargs.get("tokens_input", None)
        self.tokens_output = kwargs.get("tokens_output", None)
        self.cost = kwargs.get("cost", None)
        self.latency_ms = kwargs.get("latency_ms", None)
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))


_mock_db_models.EngineChatSession = _FakeSession
_mock_db_models.EngineChatMessage = _FakeMessage
_mock_db_module.models = _mock_db_models

sys.modules.setdefault("db", _mock_db_module)
sys.modules.setdefault("db.models", _mock_db_models)

from aria_engine.chat_engine import ChatEngine, ChatResponse
from aria_engine.llm_gateway import LLMResponse
from aria_engine.tool_registry import ToolResult


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def _patch_sqlalchemy_select():
    """
    Patch SQLAlchemy's select/update/func in chat_engine so that our fake ORM
    classes (_FakeSession / _FakeMessage) are never validated by SQLAlchemy Core.
    Since db.execute is fully mocked, the actual SQL object doesn't matter.
    """
    mock_select = MagicMock()
    mock_update = MagicMock()
    mock_func = MagicMock()
    with patch("aria_engine.chat_engine.select", return_value=mock_select), \
         patch("aria_engine.chat_engine.update", return_value=mock_update), \
         patch("aria_engine.chat_engine.func", mock_func):
        yield

@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test",
        default_model="step-35-flash-free",
        default_temperature=0.7,
        default_max_tokens=4096,
        models_yaml_path="aria_models/models.yaml",
    )


@pytest.fixture
def mock_gateway() -> AsyncMock:
    """Mock LLMGateway."""
    gw = AsyncMock()
    gw.complete = AsyncMock(return_value=LLMResponse(
        content="Hello! How can I help?",
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
def mock_tool_registry() -> MagicMock:
    """Mock ToolRegistry."""
    registry = MagicMock()
    registry.get_tools_for_llm.return_value = []
    registry.execute = AsyncMock(return_value=ToolResult(
        tool_call_id="call_123",
        name="test_tool",
        content="Tool result",
        success=True,
        duration_ms=50,
    ))
    return registry


@pytest.fixture
def mock_db_factory():
    """Mock async DB session factory."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.execute = AsyncMock()

    # Context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def chat_engine(config, mock_gateway, mock_tool_registry, mock_db_factory) -> ChatEngine:
    """Create ChatEngine with mocked dependencies."""
    engine = ChatEngine(config, mock_gateway, mock_tool_registry, mock_db_factory)
    return engine


@pytest.fixture
def sample_session_id() -> uuid.UUID:
    return uuid.uuid4()


# ============================================================================
# Session Lifecycle Tests
# ============================================================================

class TestSessionLifecycle:
    """Tests for create/resume/end session flow."""

    async def test_create_session_defaults(self, chat_engine: ChatEngine, mock_db_factory):
        """Creating a session with defaults populates all required fields."""
        mock_db = mock_db_factory.return_value
        mock_db.refresh = AsyncMock()

        session = await chat_engine.create_session()

        assert session["agent_id"] == "main"
        assert session["status"] == "active"
        assert session["model"] == "step-35-flash-free"
        # Verify add was called (ORM model persisted)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_create_session_custom_params(self, chat_engine: ChatEngine, mock_db_factory):
        """Creating a session with custom parameters passes them through."""
        mock_db = mock_db_factory.return_value
        mock_db.refresh = AsyncMock()

        session = await chat_engine.create_session(
            agent_id="researcher",
            session_type="cron",
            model="qwen3-mlx",
            temperature=0.3,
            max_tokens=8192,
            system_prompt="You are a research agent.",
        )

        assert session["agent_id"] == "researcher"
        assert session["model"] == "qwen3-mlx"
        assert session["session_type"] == "cron"

    async def test_resume_session_loads_history(self, chat_engine: ChatEngine, sample_session_id, mock_db_factory):
        """Resuming a session loads existing messages."""
        mock_db = mock_db_factory.return_value

        fake_session = _FakeSession(
            id=sample_session_id,
            agent_id="main",
            status="active",
            message_count=2,
        )

        fake_messages = [
            _FakeMessage(role="user", content="Hi", session_id=sample_session_id),
            _FakeMessage(role="assistant", content="Hello!", session_id=sample_session_id),
        ]

        # First execute returns session, second returns messages
        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = fake_session

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = fake_messages

        mock_db.execute = AsyncMock(side_effect=[session_result, msg_result])

        session = await chat_engine.resume_session(sample_session_id)

        assert session["id"] == str(sample_session_id)
        assert len(session["messages"]) == 2

    async def test_resume_nonexistent_session_raises(self, chat_engine: ChatEngine, mock_db_factory):
        """Resuming a non-existent session raises SessionError."""
        mock_db = mock_db_factory.return_value
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(SessionError, match="not found"):
            await chat_engine.resume_session(uuid.uuid4())

    async def test_end_session_updates_status(self, chat_engine: ChatEngine, sample_session_id, mock_db_factory):
        """Ending a session sets status to 'ended' and sets ended_at."""
        mock_db = mock_db_factory.return_value
        fake_session = _FakeSession(id=sample_session_id, status="active")

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_session
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.refresh = AsyncMock()

        session = await chat_engine.end_session(sample_session_id)

        assert session["status"] == "ended"
        assert session["ended_at"] is not None

    async def test_end_nonexistent_session_raises(self, chat_engine: ChatEngine, mock_db_factory):
        """Ending a non-existent session raises SessionError."""
        mock_db = mock_db_factory.return_value
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(SessionError, match="not found"):
            await chat_engine.end_session(uuid.uuid4())


# ============================================================================
# Message Sending Tests
# ============================================================================

class TestSendMessage:
    """Tests for sending messages and receiving responses."""

    async def test_send_message_returns_chat_response(
        self, chat_engine: ChatEngine, sample_session_id, mock_db_factory, mock_gateway
    ):
        """Sending a message returns a ChatResponse."""
        mock_db = mock_db_factory.return_value
        fake_session = _FakeSession(
            id=sample_session_id,
            agent_id="main",
            model="step-35-flash-free",
            status="active",
            message_count=0,
            total_tokens=0,
            total_cost=0,
            system_prompt=None,
            context_window=50,
        )

        # First execute returns session, second returns messages for context
        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = fake_session

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[session_result, msg_result])
        mock_db.flush = AsyncMock()

        response = await chat_engine.send_message(
            session_id=sample_session_id,
            content="Hello!",
        )

        assert isinstance(response, ChatResponse)
        assert response.content == "Hello! How can I help?"
        assert response.model == "step-35-flash-free"
        assert response.input_tokens == 50
        assert response.output_tokens == 20

    async def test_send_message_persists_user_and_assistant(
        self, chat_engine: ChatEngine, sample_session_id, mock_db_factory
    ):
        """Both user message and assistant response are persisted."""
        mock_db = mock_db_factory.return_value
        fake_session = _FakeSession(
            id=sample_session_id,
            status="active",
            message_count=0,
            total_tokens=0,
            total_cost=0,
            system_prompt=None,
            context_window=50,
        )

        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = fake_session

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[session_result, msg_result])

        await chat_engine.send_message(
            session_id=sample_session_id,
            content="Hi",
        )

        # Should have added user message + assistant message (at minimum 2 add calls)
        assert mock_db.add.call_count >= 2
        mock_db.commit.assert_called_once()


# ============================================================================
# Auto-Title Tests
# ============================================================================

class TestAutoTitle:
    """Tests for automatic session title generation."""

    def test_generate_title_short_message(self):
        """Short messages become the title directly."""
        title = ChatEngine._generate_title("Tell me about Python 3.13")
        assert title == "Tell me about Python 3.13"

    def test_generate_title_long_message_truncated(self):
        """Long messages are truncated to 80 chars with ellipsis."""
        long_msg = "A" * 100
        title = ChatEngine._generate_title(long_msg)
        assert len(title) == 80
        assert title.endswith("...")

    def test_generate_title_strips_whitespace(self):
        """Title generation strips leading/trailing whitespace."""
        title = ChatEngine._generate_title("  Hello world  \n  ")
        assert title == "Hello world"

    def test_generate_title_collapses_whitespace(self):
        """Multiple spaces/newlines in title are collapsed."""
        title = ChatEngine._generate_title("Hello\n\n world   test")
        assert "  " not in title


# ============================================================================
# Context Window Tests
# ============================================================================

class TestContextWindow:
    """Tests for context window management."""

    async def test_context_includes_system_prompt(
        self, chat_engine: ChatEngine, mock_db_factory
    ):
        """System prompt is always first in the context."""
        mock_db = mock_db_factory.return_value

        fake_session = _FakeSession(
            system_prompt="You are Aria Blue.",
            context_window=50,
        )

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=msg_result)

        context = await chat_engine._build_context(
            mock_db, fake_session, "Hello"
        )

        assert context[0]["role"] == "system"
        assert context[0]["content"] == "You are Aria Blue."

    async def test_context_ends_with_user_message(
        self, chat_engine: ChatEngine, mock_db_factory
    ):
        """Current user message is always last in the context."""
        mock_db = mock_db_factory.return_value

        fake_session = _FakeSession(system_prompt=None, context_window=50)

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=msg_result)

        context = await chat_engine._build_context(
            mock_db, fake_session, "My question"
        )

        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "My question"


# ============================================================================
# Tool Call Loop Tests
# ============================================================================

class TestToolCallLoop:
    """Tests for tool calling integration."""

    async def test_tool_call_triggers_execution(
        self, chat_engine: ChatEngine, sample_session_id,
        mock_db_factory, mock_gateway, mock_tool_registry
    ):
        """When LLM returns tool_calls, they are executed and fed back."""
        tool_response = LLMResponse(
            content="",
            thinking=None,
            tool_calls=[{
                "id": "call_123",
                "function": {
                    "name": "search_knowledge",
                    "arguments": '{"query": "test"}',
                },
            }],
            model="step-35-flash-free",
            input_tokens=50, output_tokens=30,
            cost_usd=0.002, latency_ms=300, finish_reason="tool_calls",
        )
        final_response = LLMResponse(
            content="Based on the search results...",
            thinking=None, tool_calls=None,
            model="step-35-flash-free",
            input_tokens=100, output_tokens=50,
            cost_usd=0.003, latency_ms=400, finish_reason="stop",
        )

        mock_gateway.complete = AsyncMock(
            side_effect=[tool_response, final_response]
        )

        # Mock tool execution
        mock_tool_registry.execute = AsyncMock(return_value=ToolResult(
            tool_call_id="call_123",
            name="search_knowledge",
            content='{"result": "Found: test data"}',
            success=True,
            duration_ms=100,
        ))

        mock_db = mock_db_factory.return_value
        fake_session = _FakeSession(
            id=sample_session_id,
            status="active",
            message_count=0,
            total_tokens=0,
            total_cost=0,
            system_prompt=None,
            context_window=50,
        )

        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = fake_session

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[session_result, msg_result])

        response = await chat_engine.send_message(
            session_id=sample_session_id,
            content="Search for test",
        )

        # Tool was executed
        mock_tool_registry.execute.assert_called_once()
        # Final response after tool execution
        assert response.content == "Based on the search results..."
        # Gateway called twice (tool_calls + final)
        assert mock_gateway.complete.call_count == 2


# ============================================================================
# Token Tracking Tests
# ============================================================================

class TestTokenTracking:
    """Tests for token counting and cost calculation."""

    async def test_token_stats_accumulated(
        self, chat_engine: ChatEngine, sample_session_id,
        mock_db_factory, mock_gateway
    ):
        """Token counts and costs accumulate in ChatResponse."""
        mock_db = mock_db_factory.return_value
        fake_session = _FakeSession(
            id=sample_session_id,
            status="active",
            message_count=0,
            total_tokens=0,
            total_cost=0,
            system_prompt=None,
            context_window=50,
        )

        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = fake_session

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[session_result, msg_result])

        response = await chat_engine.send_message(
            session_id=sample_session_id,
            content="test",
        )

        assert response.input_tokens == 50
        assert response.output_tokens == 20
        assert response.total_tokens == 70
        assert response.cost_usd == 0.001


# ============================================================================
# Static Helper Tests
# ============================================================================

class TestStaticHelpers:
    """Tests for static helper methods."""

    def test_session_to_dict(self):
        """_session_to_dict converts ORM session to plain dict."""
        session = _FakeSession(
            id=uuid.uuid4(),
            agent_id="main",
            session_type="interactive",
            model="step-35-flash-free",
        )
        result = ChatEngine._session_to_dict(session)

        assert "id" in result
        assert result["agent_id"] == "main"
        assert result["model"] == "step-35-flash-free"
        assert "created_at" in result

    def test_message_to_dict(self):
        """_message_to_dict converts ORM message to plain dict."""
        msg = _FakeMessage(
            role="assistant",
            content="Hello!",
            tokens_input=50,
            tokens_output=20,
        )
        result = ChatEngine._message_to_dict(msg)

        assert result["role"] == "assistant"
        assert result["content"] == "Hello!"
        assert result["tokens_input"] == 50
