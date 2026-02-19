"""
Unit tests for aria_engine.agent_pool — EngineAgent + AgentPool.

Tests:
- EngineAgent message processing
- EngineAgent context management
- AgentPool spawn/terminate lifecycle
- Pool concurrency limits
- Parallel task execution
- Pool status reporting
- Error recovery
"""
import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.agent_pool import AgentPool, EngineAgent, MAX_CONCURRENT_AGENTS
from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError
from aria_engine.llm_gateway import LLMResponse


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test",
        default_model="step-35-flash-free",
    )


@pytest.fixture
def mock_db_engine() -> AsyncMock:
    """Mock SQLAlchemy async engine."""
    engine = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=conn)
    return engine


@pytest.fixture
def mock_llm_gateway() -> AsyncMock:
    """Mock LLM gateway."""
    gw = AsyncMock()
    gw.complete = AsyncMock(return_value=LLMResponse(
        content="I understand.",
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
def pool(config, mock_db_engine, mock_llm_gateway) -> AgentPool:
    """Create AgentPool with mocked dependencies."""
    p = AgentPool(config, mock_db_engine, mock_llm_gateway)
    return p


@pytest.fixture
def sample_agent(mock_llm_gateway) -> EngineAgent:
    """Create a sample EngineAgent."""
    agent = EngineAgent(
        agent_id="main",
        display_name="Aria",
        model="step-35-flash-free",
        system_prompt="You are Aria.",
        temperature=0.7,
        max_tokens=4096,
    )
    agent._llm_gateway = mock_llm_gateway
    return agent


# ============================================================================
# EngineAgent Tests
# ============================================================================

class TestEngineAgent:
    """Tests for the EngineAgent dataclass."""

    async def test_process_returns_response(self, sample_agent: EngineAgent):
        """Agent.process() returns a structured response dict."""
        result = await sample_agent.process("Hello Aria!")

        assert result["content"] == "I understand."
        assert result["model"] == "step-35-flash-free"
        assert result["input_tokens"] == 50
        assert result["output_tokens"] == 20

    async def test_process_updates_status(self, sample_agent: EngineAgent):
        """Agent status transitions: idle -> busy -> idle after success."""
        assert sample_agent.status == "idle"

        result = await sample_agent.process("test")

        # After successful processing, status returns to idle
        assert sample_agent.status == "idle"
        assert sample_agent.consecutive_failures == 0
        assert sample_agent.last_active_at is not None

    async def test_process_appends_to_context(self, sample_agent: EngineAgent):
        """User and assistant messages are added to context."""
        initial_context_len = len(sample_agent._context)
        await sample_agent.process("Hello")

        # Should have user + assistant messages
        assert len(sample_agent._context) == initial_context_len + 2
        assert sample_agent._context[-2]["role"] == "user"
        assert sample_agent._context[-1]["role"] == "assistant"

    async def test_process_failure_increments_failures(self, sample_agent: EngineAgent, mock_llm_gateway):
        """Failed processing increments consecutive_failures."""
        mock_llm_gateway.complete.side_effect = Exception("LLM timeout")

        with pytest.raises(Exception):
            await sample_agent.process("test")

        assert sample_agent.consecutive_failures == 1

    async def test_process_3_failures_sets_error_status(self, sample_agent: EngineAgent, mock_llm_gateway):
        """3 consecutive failures set agent status to error."""
        mock_llm_gateway.complete.side_effect = Exception("LLM timeout")

        for _ in range(3):
            with pytest.raises(Exception):
                await sample_agent.process("test")

        assert sample_agent.status == "error"
        assert sample_agent.consecutive_failures == 3

    async def test_process_without_gateway_raises(self):
        """Processing without a gateway raises EngineError."""
        agent = EngineAgent(agent_id="no-gw")
        # _llm_gateway is None by default

        with pytest.raises(EngineError, match="has no LLM gateway"):
            await agent.process("test")

    def test_clear_context(self, sample_agent: EngineAgent):
        """clear_context() empties the context list."""
        sample_agent._context.append({"role": "user", "content": "test"})
        assert len(sample_agent._context) > 0

        sample_agent.clear_context()
        assert len(sample_agent._context) == 0

    def test_get_summary(self, sample_agent: EngineAgent):
        """get_summary() returns all expected fields."""
        summary = sample_agent.get_summary()

        assert summary["agent_id"] == "main"
        assert summary["display_name"] == "Aria"
        assert summary["model"] == "step-35-flash-free"
        assert summary["status"] == "idle"
        assert "pheromone_score" in summary
        assert "context_length" in summary

    async def test_process_includes_system_prompt(self, sample_agent: EngineAgent, mock_llm_gateway):
        """System prompt is included in messages sent to LLM."""
        await sample_agent.process("test")

        call_kwargs = mock_llm_gateway.complete.call_args[1]
        messages = call_kwargs["messages"]
        # First message should be the system prompt
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are Aria."


# ============================================================================
# AgentPool Spawn Tests
# ============================================================================

class TestAgentPoolSpawn:
    """Tests for agent spawning."""

    async def test_spawn_agent_creates_and_registers(self, pool: AgentPool, mock_db_engine):
        """Spawning an agent inserts to DB and registers in pool."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        agent = await pool.spawn_agent(
            agent_id="researcher",
            model="qwen3-mlx",
            system_prompt="You are a research agent.",
        )

        assert isinstance(agent, EngineAgent)
        assert agent.agent_id == "researcher"
        assert agent.model == "qwen3-mlx"
        assert pool.get_agent("researcher") is agent

    async def test_spawn_duplicate_raises(self, pool: AgentPool):
        """Spawning an agent with existing ID raises EngineError."""
        pool._agents["main"] = EngineAgent(agent_id="main")

        with pytest.raises(EngineError, match="already exists"):
            await pool.spawn_agent(agent_id="main")

    async def test_spawn_respects_max_concurrent(self, pool: AgentPool):
        """Cannot spawn more than MAX_CONCURRENT_AGENTS."""
        for i in range(MAX_CONCURRENT_AGENTS):
            pool._agents[f"agent-{i}"] = EngineAgent(agent_id=f"agent-{i}")

        with pytest.raises(EngineError, match="pool full"):
            await pool.spawn_agent(agent_id="one-too-many")


# ============================================================================
# AgentPool Terminate Tests
# ============================================================================

class TestAgentPoolTerminate:
    """Tests for agent termination."""

    async def test_terminate_agent_removes_from_pool(self, pool: AgentPool, mock_db_engine):
        """Terminating an agent removes it from the pool."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        pool._agents["test"] = EngineAgent(agent_id="test")

        result = await pool.terminate_agent("test")

        assert result is True
        assert pool.get_agent("test") is None

    async def test_terminate_nonexistent_returns_false(self, pool: AgentPool):
        """Terminating a non-existent agent returns False."""
        result = await pool.terminate_agent("nonexistent")
        assert result is False

    async def test_shutdown_terminates_all(self, pool: AgentPool, mock_db_engine):
        """Shutdown terminates all agents in the pool."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        for i in range(3):
            pool._agents[f"agent-{i}"] = EngineAgent(agent_id=f"agent-{i}")

        await pool.shutdown()
        assert len(pool._agents) == 0


# ============================================================================
# AgentPool Process Tests
# ============================================================================

class TestAgentPoolProcess:
    """Tests for processing messages via the pool."""

    async def test_process_with_agent(self, pool: AgentPool, mock_db_engine, mock_llm_gateway):
        """Process a message with a specific agent."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        agent = EngineAgent(agent_id="main", model="step-35-flash-free")
        agent._llm_gateway = mock_llm_gateway
        pool._agents["main"] = agent

        result = await pool.process_with_agent("main", "Hello!")
        assert result["content"] == "I understand."

    async def test_process_nonexistent_agent_raises(self, pool: AgentPool):
        """Processing with nonexistent agent raises EngineError."""
        with pytest.raises(EngineError, match="not found in pool"):
            await pool.process_with_agent("nonexistent", "test")

    async def test_process_disabled_agent_raises(self, pool: AgentPool):
        """Processing with disabled agent raises EngineError."""
        pool._agents["disabled"] = EngineAgent(agent_id="disabled", status="disabled")

        with pytest.raises(EngineError, match="is disabled"):
            await pool.process_with_agent("disabled", "test")


# ============================================================================
# Parallel Execution Tests
# ============================================================================

class TestParallelExecution:
    """Tests for running parallel agent tasks."""

    async def test_run_parallel(self, pool: AgentPool, mock_db_engine, mock_llm_gateway):
        """Multiple tasks execute in parallel and return results."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        for name in ("main", "researcher"):
            agent = EngineAgent(agent_id=name, model="step-35-flash-free")
            agent._llm_gateway = mock_llm_gateway
            pool._agents[name] = agent

        results = await pool.run_parallel([
            {"agent_id": "main", "message": "Task 1"},
            {"agent_id": "researcher", "message": "Task 2"},
        ])

        assert len(results) == 2
        for r in results:
            assert "content" in r

    async def test_parallel_error_doesnt_crash_pool(
        self, pool: AgentPool, mock_db_engine, mock_llm_gateway
    ):
        """A single agent error doesn't bring down the entire pool."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        good_gw = AsyncMock()
        good_gw.complete = AsyncMock(return_value=LLMResponse(
            content="OK", thinking=None, tool_calls=None,
            model="test", input_tokens=10, output_tokens=5,
            cost_usd=0.0, latency_ms=100, finish_reason="stop",
        ))
        bad_gw = AsyncMock()
        bad_gw.complete = AsyncMock(side_effect=Exception("Agent crashed"))

        good = EngineAgent(agent_id="good", model="test")
        good._llm_gateway = good_gw
        bad = EngineAgent(agent_id="bad", model="test")
        bad._llm_gateway = bad_gw

        pool._agents["good"] = good
        pool._agents["bad"] = bad

        results = await pool.run_parallel([
            {"agent_id": "good", "message": "OK"},
            {"agent_id": "bad", "message": "Fail"},
        ])

        assert len(results) == 2
        # Good agent succeeded
        good_result = [r for r in results if r.get("content") == "OK"]
        assert len(good_result) == 1
        # Bad agent has an error
        bad_result = [r for r in results if "error" in r]
        assert len(bad_result) == 1


# ============================================================================
# Pool Status Tests
# ============================================================================

class TestPoolStatus:
    """Tests for pool status reporting."""

    def test_empty_pool_status(self, pool: AgentPool):
        """Empty pool reports correct status."""
        status = pool.get_status()

        assert status["total_agents"] == 0
        assert status["max_concurrent"] == MAX_CONCURRENT_AGENTS

    def test_pool_status_with_agents(self, pool: AgentPool):
        """Pool with agents reports their states."""
        pool._agents["main"] = EngineAgent(agent_id="main", status="idle")
        pool._agents["researcher"] = EngineAgent(agent_id="researcher", status="busy")

        status = pool.get_status()

        assert status["total_agents"] == 2
        assert status["status_counts"]["idle"] == 1
        assert status["status_counts"]["busy"] == 1

    def test_list_agents(self, pool: AgentPool):
        """list_agents returns summaries of all agents."""
        pool._agents["main"] = EngineAgent(agent_id="main", display_name="Aria")
        pool._agents["researcher"] = EngineAgent(agent_id="researcher", display_name="Scholar")

        agents = pool.list_agents()
        assert len(agents) == 2
        agent_ids = [a["agent_id"] for a in agents]
        assert "main" in agent_ids
        assert "researcher" in agent_ids

    def test_get_agent_returns_none_for_unknown(self, pool: AgentPool):
        """get_agent returns None for unknown agent_id."""
        assert pool.get_agent("unknown") is None

    def test_get_agent_returns_agent(self, pool: AgentPool):
        """get_agent returns the agent for known agent_id."""
        agent = EngineAgent(agent_id="main")
        pool._agents["main"] = agent
        assert pool.get_agent("main") is agent
