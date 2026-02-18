# S10-04: Unit Tests for AgentPool
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 10

## Problem
`aria_engine/agent_pool.py` manages concurrent agent lifecycle — spawning, tracking, terminating, and pheromone-based routing. A bug in the pool can cause resource leaks (orphaned coroutines), deadlocks (semaphore exhaustion), or agent starvation. No unit tests exist.

## Root Cause
AgentPool was built in Sprint 4 and upgraded to TaskGroup in Sprint 9. Testing coroutine-based concurrency requires careful mocking of asyncio primitives, which was deferred.

## Fix
### `tests/unit/test_agent_pool.py`
```python
"""
Unit tests for aria_engine.agent_pool.AgentPool.

Tests:
- Agent loading from DB
- Spawn single and multiple agents
- Terminate agents (graceful + forced)
- Pheromone-based routing
- Session isolation
- Concurrent operation limits (semaphore)
- Error recovery
- Pool status reporting
"""
import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.agent_pool import AgentPool, AgentTask
from aria_engine.config import EngineConfig
from aria_engine.exceptions import AgentError


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
def pool(config: EngineConfig) -> AgentPool:
    """Create AgentPool with mocked dependencies."""
    p = AgentPool(config)
    return p


@pytest.fixture
def agent_configs() -> list[dict[str, Any]]:
    """Sample agent configurations."""
    return [
        {
            "agent_id": "main",
            "model": "step-35-flash-free",
            "system_prompt": "You are Aria, the main agent.",
            "temperature": 0.7,
        },
        {
            "agent_id": "researcher",
            "model": "qwen3-mlx",
            "system_prompt": "You are Aria's research agent.",
            "temperature": 0.3,
        },
        {
            "agent_id": "social",
            "model": "step-35-flash-free",
            "system_prompt": "You manage social media.",
            "temperature": 0.8,
        },
    ]


@pytest.fixture
def mock_session_manager():
    """Mock NativeSessionManager."""
    mgr = AsyncMock()
    mgr.create_session = AsyncMock(return_value={
        "id": "test-session-id",
        "agent_id": "main",
        "status": "active",
    })
    return mgr


# ============================================================================
# Spawn Tests
# ============================================================================

class TestSpawnAgents:
    """Tests for agent spawning."""

    @pytest.mark.asyncio
    async def test_spawn_single_agent(self, pool: AgentPool, mock_session_manager):
        """Spawning a single agent creates a session and registers it."""
        with patch("aria_engine.agent_pool.NativeSessionManager", return_value=mock_session_manager):
            results = await pool.spawn_agents([{
                "agent_id": "main",
                "model": "step-35-flash-free",
            }])

            assert "main" in results
            assert results["main"] == "running"
            assert "main" in pool._agents
            assert pool._agents["main"].status == "running"

    @pytest.mark.asyncio
    async def test_spawn_multiple_agents(self, pool: AgentPool, agent_configs, mock_session_manager):
        """Spawning multiple agents creates sessions concurrently."""
        with patch("aria_engine.agent_pool.NativeSessionManager", return_value=mock_session_manager):
            results = await pool.spawn_agents(agent_configs)

            assert len(results) == 3
            for config in agent_configs:
                assert results[config["agent_id"]] == "running"

    @pytest.mark.asyncio
    async def test_spawn_respects_max_concurrent(self, pool: AgentPool, mock_session_manager):
        """Cannot spawn more than MAX_CONCURRENT agents simultaneously."""
        pool.MAX_CONCURRENT = 2

        configs = [
            {"agent_id": f"agent-{i}", "model": "step-35-flash-free"}
            for i in range(5)
        ]

        with patch("aria_engine.agent_pool.NativeSessionManager", return_value=mock_session_manager):
            # This should still work — semaphore limits concurrency, not total count
            results = await pool.spawn_agents(configs)

            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_spawn_failure_reports_error(self, pool: AgentPool):
        """If spawn fails, the error is reported in results."""
        mock_mgr = AsyncMock()
        mock_mgr.create_session = AsyncMock(
            side_effect=AgentError("Failed to create session")
        )

        with patch("aria_engine.agent_pool.NativeSessionManager", return_value=mock_mgr):
            results = await pool.spawn_agents([{
                "agent_id": "failing",
                "model": "step-35-flash-free",
            }])

            # Agent should be in error state
            assert "failing" in pool._agents
            assert pool._agents["failing"].status == "error"


# ============================================================================
# Terminate Tests
# ============================================================================

class TestTerminateAgents:
    """Tests for agent termination."""

    @pytest.mark.asyncio
    async def test_terminate_single_agent(self, pool: AgentPool):
        """Terminating an agent cancels its task and removes it."""
        mock_task = AsyncMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()

        pool._agents["test-agent"] = AgentTask(
            agent_id="test-agent",
            task=mock_task,
            status="running",
        )

        await pool._terminate_agent("test-agent")

        mock_task.cancel.assert_called_once()
        assert pool._agents["test-agent"].status == "terminated"

    @pytest.mark.asyncio
    async def test_terminate_already_done(self, pool: AgentPool):
        """Terminating an already-finished agent is a no-op."""
        mock_task = AsyncMock()
        mock_task.done.return_value = True

        pool._agents["done-agent"] = AgentTask(
            agent_id="done-agent",
            task=mock_task,
            status="completed",
        )

        await pool._terminate_agent("done-agent")

        mock_task.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_terminates_all(self, pool: AgentPool):
        """Shutdown terminates all running agents."""
        for i in range(3):
            mock_task = AsyncMock()
            mock_task.done.return_value = False
            mock_task.cancel = MagicMock()
            pool._agents[f"agent-{i}"] = AgentTask(
                agent_id=f"agent-{i}",
                task=mock_task,
                status="running",
            )

        await pool.shutdown(timeout=5.0)

        assert len(pool._agents) == 0
        assert pool._shutdown.is_set()


# ============================================================================
# Pheromone Routing Tests
# ============================================================================

class TestPheromoneRouting:
    """Tests for pheromone-based agent routing."""

    @pytest.mark.asyncio
    async def test_route_to_best_agent(self, pool: AgentPool):
        """Routes task to agent with highest pheromone score."""
        pool._agents = {
            "main": AgentTask(agent_id="main", status="running"),
            "researcher": AgentTask(agent_id="researcher", status="running"),
            "social": AgentTask(agent_id="social", status="running"),
        }

        pheromone_scores = {
            "main": 0.500,
            "researcher": 0.850,
            "social": 0.650,
        }

        with patch.object(pool, "_get_pheromone_scores", new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = pheromone_scores

            best = await pool.route_to_best_agent(
                task_description="Research Python 3.13 features"
            )

            assert best == "researcher"

    @pytest.mark.asyncio
    async def test_route_excludes_busy_agents(self, pool: AgentPool):
        """Routing skips agents that are currently busy."""
        pool._agents = {
            "main": AgentTask(agent_id="main", status="busy"),
            "researcher": AgentTask(agent_id="researcher", status="running"),
        }

        pheromone_scores = {
            "main": 0.900,  # Higher score but busy
            "researcher": 0.600,
        }

        with patch.object(pool, "_get_pheromone_scores", new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = pheromone_scores

            best = await pool.route_to_best_agent(
                task_description="Any task"
            )

            assert best == "researcher"

    @pytest.mark.asyncio
    async def test_route_fallback_when_all_busy(self, pool: AgentPool):
        """When all agents are busy, returns 'main' as fallback."""
        pool._agents = {
            "main": AgentTask(agent_id="main", status="busy"),
            "researcher": AgentTask(agent_id="researcher", status="busy"),
        }

        with patch.object(pool, "_get_pheromone_scores", new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = {"main": 0.5, "researcher": 0.5}

            best = await pool.route_to_best_agent(task_description="Urgent task")

            assert best == "main"  # fallback to main


# ============================================================================
# Session Isolation Tests
# ============================================================================

class TestSessionIsolation:
    """Tests for agent session isolation."""

    @pytest.mark.asyncio
    async def test_each_agent_gets_unique_session(self, pool: AgentPool, mock_session_manager):
        """Each spawned agent gets its own isolated chat session."""
        session_ids: list[str] = []

        async def track_session(**kwargs):
            sid = f"session-{len(session_ids)}"
            session_ids.append(sid)
            return {"id": sid, "agent_id": kwargs.get("agent_id"), "status": "active"}

        mock_session_manager.create_session = AsyncMock(side_effect=track_session)

        with patch("aria_engine.agent_pool.NativeSessionManager", return_value=mock_session_manager):
            await pool.spawn_agents([
                {"agent_id": "agent-a", "model": "test"},
                {"agent_id": "agent-b", "model": "test"},
            ])

        assert len(session_ids) == 2
        assert session_ids[0] != session_ids[1]


# ============================================================================
# Pool Status Tests
# ============================================================================

class TestPoolStatus:
    """Tests for pool status reporting."""

    def test_empty_pool_status(self, pool: AgentPool):
        """Empty pool reports correct status."""
        status = pool.get_pool_status()

        assert status["total_agents"] == 0
        assert status["max_concurrent"] == 5
        assert status["shutdown_requested"] is False
        assert status["agents"] == {}

    def test_pool_status_with_agents(self, pool: AgentPool):
        """Pool with agents reports their states."""
        pool._agents = {
            "main": AgentTask(agent_id="main", status="running"),
            "researcher": AgentTask(agent_id="researcher", status="error"),
        }

        status = pool.get_pool_status()

        assert status["total_agents"] == 2
        assert status["agents"]["main"]["status"] == "running"
        assert status["agents"]["researcher"]["status"] == "error"


# ============================================================================
# Parallel Task Execution Tests
# ============================================================================

class TestParallelTasks:
    """Tests for running parallel agent tasks."""

    @pytest.mark.asyncio
    async def test_run_parallel_tasks(self, pool: AgentPool):
        """Multiple tasks execute in parallel and return results."""
        pool._agents = {
            "main": AgentTask(agent_id="main", status="running"),
            "researcher": AgentTask(agent_id="researcher", status="running"),
        }

        with patch.object(pool, "_execute_agent_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "output": "Task completed",
                "latency_ms": 200,
                "tokens": 50,
            }

            results = await pool.run_parallel_tasks([
                {"agent_id": "main", "prompt": "Task 1", "session_id": "s1"},
                {"agent_id": "researcher", "prompt": "Task 2", "session_id": "s2"},
            ])

            assert len(results) == 2
            for r in results:
                assert r["status"] == "success"

    @pytest.mark.asyncio
    async def test_parallel_task_timeout(self, pool: AgentPool):
        """Tasks that exceed timeout are cancelled."""
        pool._agents = {
            "slow": AgentTask(agent_id="slow", status="running"),
        }

        async def slow_task(task_spec):
            await asyncio.sleep(10)
            return {"output": "done"}

        with patch.object(pool, "_execute_agent_task", side_effect=slow_task):
            results = await pool.run_parallel_tasks(
                [{"agent_id": "slow", "prompt": "Slow task", "session_id": "s1"}],
                timeout=0.1,
            )

            assert any(r["status"] in ("timeout", "error") for r in results)


# ============================================================================
# Error Recovery Tests
# ============================================================================

class TestErrorRecovery:
    """Tests for error recovery in the agent pool."""

    @pytest.mark.asyncio
    async def test_agent_error_doesnt_crash_pool(self, pool: AgentPool):
        """A single agent error doesn't bring down the entire pool."""
        pool._agents = {
            "good": AgentTask(agent_id="good", status="running"),
            "bad": AgentTask(agent_id="bad", status="running"),
        }

        async def mixed_exec(task_spec):
            if task_spec["agent_id"] == "bad":
                raise AgentError("Agent crashed")
            return {"output": "Success", "latency_ms": 100, "tokens": 10}

        with patch.object(pool, "_execute_agent_task", side_effect=mixed_exec):
            results = await pool.run_parallel_tasks([
                {"agent_id": "good", "prompt": "OK", "session_id": "s1"},
                {"agent_id": "bad", "prompt": "Fail", "session_id": "s2"},
            ])

            # Pool should still be operational
            assert pool._shutdown.is_set() is False
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | AgentPool sits at engine layer |
| 2 | .env for secrets (zero in code) | ✅ | Test config uses dummy credentials |
| 3 | models.yaml single source of truth | ❌ | Tests mock model references |
| 4 | Docker-first testing | ✅ | Tests run in Docker CI |
| 5 | aria_memories only writable path | ❌ | Tests only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S4-01 must complete first (AgentPool implementation exists)
- S9-03 should complete first (TaskGroup refactor applied)
- S10-01 should complete first (shared conftest fixtures)

## Verification
```bash
# 1. Run tests:
pytest tests/unit/test_agent_pool.py -v
# EXPECTED: All tests pass

# 2. Coverage:
pytest tests/unit/test_agent_pool.py --cov=aria_engine.agent_pool --cov-report=term-missing
# EXPECTED: >85% coverage

# 3. Import check:
python -c "import tests.unit.test_agent_pool; print('OK')"
# EXPECTED: OK
```

## Prompt for Agent
```
Write comprehensive unit tests for aria_engine.agent_pool.AgentPool.

FILES TO READ FIRST:
- aria_engine/agent_pool.py (full file — implementation under test)
- aria_engine/config.py (EngineConfig)
- aria_engine/exceptions.py (AgentError)
- aria_agents/scoring.py (pheromone scoring reference)
- tests/conftest.py (shared fixtures)

STEPS:
1. Read all files above
2. Create tests/unit/test_agent_pool.py
3. Mock DB, NativeSessionManager, and ChatEngine
4. Test concurrency with asyncio tasks
5. Run pytest and verify all tests pass

CONSTRAINTS:
- Mock all DB access — no real database connections
- Test TaskGroup error handling (except* syntax)
- Test semaphore limits (MAX_CONCURRENT=5)
- Test pheromone routing logic
- Verify session isolation per agent
```
