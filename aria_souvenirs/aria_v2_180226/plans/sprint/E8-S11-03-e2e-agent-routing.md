# S11-03: E2E Agent Routing & Pheromone System
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 11

## Problem
Aria's 6-agent system uses a pheromone-based routing algorithm to select which agent handles each request. This is the most complex subsystem in the engine — incorrect routing means users talk to the wrong agent, agents fight over tasks, or requests get dropped. We need E2E tests that verify the full routing pipeline with real database state.

## Root Cause
The pheromone routing system involves multiple interacting components: agent spawning, score computation, task matching, session binding, and score decay. Unit tests validate each in isolation, but integration tests must verify the emergent behavior when all components interact with real database state and concurrent requests.

## Fix
### `tests/integration/test_e2e_agent_routing.py`
```python
"""
E2E integration tests for Agent Routing & Pheromone System.

Tests the full pipeline:
  User Message ─► Router ─► Pheromone Scoring ─► Agent Selection
                                                       │
  Agent Pool state + DB scores ◄───────────────────────┘

Validates: routing accuracy, pheromone decay, session binding,
concurrent routing, agent specialization, and fallback behavior.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Agent definitions for testing
# ---------------------------------------------------------------------------

TEST_AGENTS = {
    "researcher": {
        "id": "researcher",
        "name": "Researcher Agent",
        "skills": ["research", "fact_check", "unified_search"],
        "keywords": ["search", "find", "look up", "research", "investigate"],
        "base_score": 0.5,
    },
    "coder": {
        "id": "coder",
        "name": "Coder Agent",
        "skills": ["sandbox", "pytest_runner", "ci_cd"],
        "keywords": ["code", "implement", "debug", "fix", "test", "python", "function"],
        "base_score": 0.5,
    },
    "analyst": {
        "id": "analyst",
        "name": "Analyst Agent",
        "skills": ["market_data", "portfolio", "sentiment_analysis"],
        "keywords": ["analyze", "data", "market", "price", "trend", "chart"],
        "base_score": 0.5,
    },
    "writer": {
        "id": "writer",
        "name": "Writer Agent",
        "skills": ["brainstorm", "moltbook", "conversation_summary"],
        "keywords": ["write", "draft", "blog", "article", "story", "summarize"],
        "base_score": 0.5,
    },
    "ops": {
        "id": "ops",
        "name": "Ops Agent",
        "skills": ["health", "performance", "security_scan"],
        "keywords": ["deploy", "monitor", "health", "status", "server", "cpu"],
        "base_score": 0.5,
    },
    "coordinator": {
        "id": "coordinator",
        "name": "Coordinator Agent",
        "skills": ["goals", "schedule", "sprint_manager"],
        "keywords": ["plan", "schedule", "goal", "sprint", "prioritize"],
        "base_score": 0.6,  # slight bias as fallback
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def agent_pool():
    """Create an AgentPool with test agents."""
    from aria_engine.agent_pool import AgentPool

    pool = AgentPool()
    for agent_id, agent_def in TEST_AGENTS.items():
        await pool.register(agent_def)
    yield pool
    await pool.shutdown()


@pytest.fixture
async def router(agent_pool):
    """Create a Router connected to the test agent pool."""
    from aria_engine.router import PheromoneRouter

    router = PheromoneRouter(agent_pool=agent_pool)
    yield router


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestE2EAgentRouting:
    """End-to-end agent routing integration tests."""

    @pytest.mark.integration
    async def test_research_query_routes_to_researcher(self, router):
        """Research-related queries route to the researcher agent."""
        result = await router.route("Can you research the latest AI papers on arxiv?")
        assert result.agent_id == "researcher"
        assert result.confidence > 0.5

    @pytest.mark.integration
    async def test_code_query_routes_to_coder(self, router):
        """Code-related queries route to the coder agent."""
        result = await router.route("Write a Python function to sort a list")
        assert result.agent_id == "coder"
        assert result.confidence > 0.5

    @pytest.mark.integration
    async def test_market_query_routes_to_analyst(self, router):
        """Market/data queries route to the analyst."""
        result = await router.route("Analyze the Bitcoin price trend this week")
        assert result.agent_id == "analyst"
        assert result.confidence > 0.5

    @pytest.mark.integration
    async def test_writing_query_routes_to_writer(self, router):
        """Writing tasks route to the writer agent."""
        result = await router.route("Draft a blog post about autonomous AI agents")
        assert result.agent_id == "writer"
        assert result.confidence > 0.5

    @pytest.mark.integration
    async def test_ops_query_routes_to_ops(self, router):
        """Operations queries route to the ops agent."""
        result = await router.route("Check the server health and CPU usage")
        assert result.agent_id == "ops"
        assert result.confidence > 0.5

    @pytest.mark.integration
    async def test_ambiguous_query_routes_to_coordinator(self, router):
        """Ambiguous queries fall through to the coordinator."""
        result = await router.route("Hello, how are you?")
        assert result.agent_id == "coordinator"

    @pytest.mark.integration
    async def test_pheromone_score_increases_on_success(self, router, agent_pool):
        """Successful task completion increases agent's pheromone score."""
        # Route and record success
        result = await router.route("Research quantum computing")
        initial_score = await agent_pool.get_pheromone_score("researcher")

        await router.record_outcome(
            agent_id="researcher",
            task_id=result.task_id,
            success=True,
            quality_score=0.9,
        )

        new_score = await agent_pool.get_pheromone_score("researcher")
        assert new_score > initial_score

    @pytest.mark.integration
    async def test_pheromone_score_decreases_on_failure(self, router, agent_pool):
        """Failed task completion decreases agent's pheromone score."""
        result = await router.route("Debug this code")
        initial_score = await agent_pool.get_pheromone_score("coder")

        await router.record_outcome(
            agent_id="coder",
            task_id=result.task_id,
            success=False,
            quality_score=0.1,
        )

        new_score = await agent_pool.get_pheromone_score("coder")
        assert new_score < initial_score

    @pytest.mark.integration
    async def test_pheromone_decay_over_time(self, router, agent_pool):
        """Pheromone scores decay towards baseline over time."""
        # Boost researcher score
        for _ in range(5):
            result = await router.route("Research something interesting")
            await router.record_outcome(
                agent_id="researcher",
                task_id=result.task_id,
                success=True,
                quality_score=0.95,
            )

        boosted_score = await agent_pool.get_pheromone_score("researcher")

        # Apply decay
        await agent_pool.apply_pheromone_decay(decay_factor=0.8)

        decayed_score = await agent_pool.get_pheromone_score("researcher")
        assert decayed_score < boosted_score
        assert decayed_score > TEST_AGENTS["researcher"]["base_score"]

    @pytest.mark.integration
    async def test_session_binding_preserves_agent(self, router):
        """Once an agent is bound to a session, it handles all messages."""
        session_id = "sticky-session-001"

        # First message routes to researcher
        r1 = await router.route("Research AI safety papers", session_id=session_id)
        assert r1.agent_id == "researcher"

        # Second message should stick to researcher even though it looks like code
        r2 = await router.route("Now write code to scrape those papers", session_id=session_id)
        assert r2.agent_id == "researcher"  # session binding overrides

    @pytest.mark.integration
    async def test_session_rebinding_on_explicit_switch(self, router):
        """Agent can be switched explicitly mid-session."""
        session_id = "switch-session-001"

        r1 = await router.route("Research quantum computing", session_id=session_id)
        assert r1.agent_id == "researcher"

        # Explicit switch
        r2 = await router.route(
            "Switch to coder agent and implement a quantum circuit simulator",
            session_id=session_id,
            force_agent="coder",
        )
        assert r2.agent_id == "coder"

    @pytest.mark.integration
    async def test_concurrent_routing_requests(self, router):
        """Multiple concurrent routing requests produce correct results."""
        queries = [
            ("Research AI papers", "researcher"),
            ("Write a Python quicksort", "coder"),
            ("Analyze market trends", "analyst"),
            ("Draft a blog post", "writer"),
            ("Check server health", "ops"),
        ]

        tasks = [router.route(query) for query, _ in queries]
        results = await asyncio.gather(*tasks)

        for (query, expected_agent), result in zip(queries, results):
            assert result.agent_id == expected_agent, (
                f"Query '{query}' routed to '{result.agent_id}' instead of '{expected_agent}'"
            )

    @pytest.mark.integration
    async def test_routing_with_context(self, router):
        """Router considers conversation context for better routing."""
        session_id = "context-session-001"

        # Establish context with a code question
        await router.route(
            "I'm building a Python web scraper",
            session_id=session_id,
        )

        # Follow-up should stay with coder despite ambiguous phrasing
        r2 = await router.route(
            "Can you help me with the next step?",
            session_id=session_id,
        )
        assert r2.agent_id == "coder"

    @pytest.mark.integration
    async def test_all_agents_reachable(self, router):
        """Every registered agent can be reached by appropriate queries."""
        reached_agents: set[str] = set()

        test_queries = {
            "researcher": "Search for recent papers on transformers",
            "coder": "Implement a binary search algorithm in Python",
            "analyst": "What's the current Bitcoin price trend",
            "writer": "Write me a short story about AI",
            "ops": "Monitor the server CPU usage",
            "coordinator": "Help me plan my quarterly goals",
        }

        for agent_id, query in test_queries.items():
            result = await router.route(query)
            reached_agents.add(result.agent_id)

        assert reached_agents == set(TEST_AGENTS.keys()), (
            f"Unreachable agents: {set(TEST_AGENTS.keys()) - reached_agents}"
        )

    @pytest.mark.integration
    async def test_routing_metadata(self, router):
        """Routing result includes useful metadata."""
        result = await router.route("Research machine learning papers")

        assert hasattr(result, "agent_id")
        assert hasattr(result, "confidence")
        assert hasattr(result, "task_id")
        assert hasattr(result, "scores")  # all agent scores

        # Scores should be a dict of agent_id → score
        assert isinstance(result.scores, dict)
        assert len(result.scores) == len(TEST_AGENTS)
        assert all(0.0 <= s <= 1.0 for s in result.scores.values())

    @pytest.mark.integration
    async def test_agent_unavailable_reroutes(self, router, agent_pool):
        """If best agent is unavailable, request goes to next best."""
        # Disable the researcher
        await agent_pool.set_status("researcher", "unavailable")

        result = await router.route("Research quantum computing papers")
        assert result.agent_id != "researcher"
        # Should route to coordinator as fallback
        assert result.agent_id in {"coordinator", "writer"}

        # Re-enable
        await agent_pool.set_status("researcher", "active")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Tests agent routing layer |
| 2 | .env for secrets | ✅ | TEST_DATABASE_URL |
| 3 | models.yaml single source | ❌ | No LLM calls |
| 4 | Docker-first testing | ✅ | PostgreSQL for pheromone state |
| 5 | aria_memories only writable path | ❌ | DB writes only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S10-04 (unit tests for AgentPool) must pass
- aria_engine.router module exists
- aria_engine.agent_pool module exists

## Verification
```bash
# 1. Run agent routing E2E tests:
TEST_DATABASE_URL=postgresql://aria:aria_test@localhost:5432/aria_test pytest tests/integration/test_e2e_agent_routing.py -v --timeout=30

# 2. Check pheromone tests specifically:
pytest tests/integration/test_e2e_agent_routing.py -k "pheromone" -v

# 3. Check concurrent routing:
pytest tests/integration/test_e2e_agent_routing.py::TestE2EAgentRouting::test_concurrent_routing_requests -v -s
```

## Prompt for Agent
```
Create end-to-end integration tests for agent routing and pheromone system.

FILES TO READ FIRST:
- aria_engine/agent_pool.py (AgentPool class)
- aria_engine/router.py (PheromoneRouter class)
- aria_agents/scoring.py (pheromone scoring)
- aria_agents/coordinator.py (fallback coordinator)
- tests/unit/test_agent_pool.py (complement these)

STEPS:
1. Create tests/integration/test_e2e_agent_routing.py
2. Define 6 test agents matching the real agent definitions
3. Test: keyword routing, pheromone boost/decay, session binding, concurrent, fallback
4. Use real database for pheromone state persistence

CONSTRAINTS:
- Do NOT mock the router or agent pool — use real instances
- Mock the LLM for keyword extraction if needed
- Test all 6 agents are reachable
- Test pheromone scores change correctly
- Test session binding stickiness
```
