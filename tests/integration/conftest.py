"""
Integration test fixtures and configuration.

Provides database setup/teardown, mock factories, and shared
configuration for all Sprint 11 integration tests.

Adapts to real PostgreSQL when available (Docker), otherwise
falls back to mocked database for CI/local runs.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Ensure db.models is importable with mock ORM classes
# ---------------------------------------------------------------------------

_mock_db_module = ModuleType("db")
_mock_db_models = ModuleType("db.models")


class FakeSession:
    """Mock ORM EngineChatSession model."""
    id = MagicMock()
    agent_id = MagicMock()
    session_id = MagicMock()
    status = MagicMock()

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
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


class FakeMessage:
    """Mock ORM EngineChatMessage model."""
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
        self.metadata_json = kwargs.get("metadata_json", {})
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))


class FakeAgentState:
    """Mock ORM EngineAgentState model."""
    def __init__(self, **kwargs):
        self.agent_id = kwargs.get("agent_id", "main")
        self.display_name = kwargs.get("display_name", "Aria")
        self.focus_type = kwargs.get("focus_type", None)
        self.status = kwargs.get("status", "idle")
        self.pheromone_score = kwargs.get("pheromone_score", 0.5)
        self.consecutive_failures = kwargs.get("consecutive_failures", 0)
        self.last_active_at = kwargs.get("last_active_at", None)


class FakeGoal:
    """Mock ORM Goal model."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_mock_db_models.EngineChatSession = FakeSession
_mock_db_models.EngineChatMessage = FakeMessage
_mock_db_models.EngineAgentState = FakeAgentState
_mock_db_models.Goal = FakeGoal
_mock_db_module.models = _mock_db_models

sys.modules.setdefault("db", _mock_db_module)
sys.modules.setdefault("db.models", _mock_db_models)


# ---------------------------------------------------------------------------
# Auto-mark integration tests
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    """Auto-mark integration tests."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# ---------------------------------------------------------------------------
# Session-scoped event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Engine config fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def engine_config():
    """Standard test engine config — no external services."""
    from aria_engine.config import EngineConfig
    return EngineConfig(
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test-key",
        default_model="step-35-flash-free",
        default_temperature=0.7,
        default_max_tokens=4096,
        models_yaml_path="aria_models/models.yaml",
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
    )


# ---------------------------------------------------------------------------
# Mock database engine
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_engine():
    """Mock SQLAlchemy async engine for integration tests."""
    engine = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=MagicMock(
        mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        scalar_one_or_none=MagicMock(return_value=None),
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
    ))
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=conn)
    return engine


# ---------------------------------------------------------------------------
# Mock LLM gateway
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_gateway():
    """Mock LLM gateway that returns predictable responses."""
    from aria_engine.llm_gateway import LLMResponse

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


# ---------------------------------------------------------------------------
# Mock DB session factory (for ORM-based code)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session_factory():
    """Mock async sessionmaker for ORM usage."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()

    factory = MagicMock()
    factory.__call__ = MagicMock(return_value=session)
    factory.return_value = session
    # Support async context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    return factory
