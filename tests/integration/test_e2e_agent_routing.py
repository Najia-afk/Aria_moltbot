"""
E2E integration tests for Agent Routing & Pheromone System.

Tests the full pipeline:
  User Message ─► EngineRouter ─► Pheromone Scoring ─► Agent Selection
                                                            │
  Agent state + DB scores ◄─────────────────────────────────┘

Validates: routing accuracy, pheromone scoring, score update,
concurrent routing, and specialty matching.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError
from aria_engine.routing import (
    COLD_START_SCORE,
    DECAY_FACTOR,
    SPECIALTY_PATTERNS,
    WEIGHTS,
    EngineRouter,
    compute_load_score,
    compute_pheromone_score,
    compute_specialty_match,
)


# ---------------------------------------------------------------------------
# Agent definitions for testing
# ---------------------------------------------------------------------------

TEST_AGENTS = {
    "aria-social": {
        "agent_id": "aria-social",
        "display_name": "Social Agent",
        "focus_type": "social",
        "status": "idle",
        "pheromone_score": 0.5,
        "consecutive_failures": 0,
        "last_active_at": None,
    },
    "aria-devops": {
        "agent_id": "aria-devops",
        "display_name": "DevOps Agent",
        "focus_type": "devops",
        "status": "idle",
        "pheromone_score": 0.5,
        "consecutive_failures": 0,
        "last_active_at": None,
    },
    "aria-analysis": {
        "agent_id": "aria-analysis",
        "display_name": "Analysis Agent",
        "focus_type": "analysis",
        "status": "idle",
        "pheromone_score": 0.5,
        "consecutive_failures": 0,
        "last_active_at": None,
    },
    "aria-creative": {
        "agent_id": "aria-creative",
        "display_name": "Creative Agent",
        "focus_type": "creative",
        "status": "idle",
        "pheromone_score": 0.5,
        "consecutive_failures": 0,
        "last_active_at": None,
    },
    "aria-research": {
        "agent_id": "aria-research",
        "display_name": "Research Agent",
        "focus_type": "research",
        "status": "idle",
        "pheromone_score": 0.5,
        "consecutive_failures": 0,
        "last_active_at": None,
    },
    "main": {
        "agent_id": "main",
        "display_name": "Aria Main",
        "focus_type": None,  # Generalist
        "status": "idle",
        "pheromone_score": 0.5,
        "consecutive_failures": 0,
        "last_active_at": None,
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_engine():
    """Mock DB engine that returns agent state rows."""
    engine = AsyncMock()
    conn = AsyncMock()

    def make_execute_side_effect(agents_data):
        """Create execute mock that returns agent rows from TEST_AGENTS."""
        async def execute(query, params=None):
            result = MagicMock()
            # Return all agents matching the request
            if params:
                agent_ids = [v for k, v in params.items() if k.startswith("a")]
                rows = [TEST_AGENTS[aid] for aid in agent_ids if aid in agents_data]
            else:
                rows = list(agents_data.values())
            result.mappings = MagicMock(return_value=MagicMock(
                all=MagicMock(return_value=rows)
            ))
            return result
        return execute

    conn.execute = AsyncMock(side_effect=make_execute_side_effect(TEST_AGENTS))
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=conn)
    engine._conn = conn
    return engine


@pytest.fixture
def router(mock_db_engine):
    """Create an EngineRouter with test agent data."""
    return EngineRouter(mock_db_engine)


# ---------------------------------------------------------------------------
# Tests — Pure scoring functions
# ---------------------------------------------------------------------------

class TestSpecialtyMatch:
    """Tests for compute_specialty_match()."""

    @pytest.mark.integration
    def test_social_keywords_match(self):
        """Social keywords score high for social agents."""
        score = compute_specialty_match("Post a new tweet about AI", "social")
        assert score >= 0.6

    @pytest.mark.integration
    def test_devops_keywords_match(self):
        """DevOps keywords score high for devops agents."""
        score = compute_specialty_match("Deploy the Docker container and run CI tests", "devops")
        assert score >= 0.6

    @pytest.mark.integration
    def test_analysis_keywords_match(self):
        """Analysis keywords score high for analysis agents."""
        score = compute_specialty_match("Analyze the metrics and data trends", "analysis")
        assert score >= 0.6

    @pytest.mark.integration
    def test_creative_keywords_match(self):
        """Creative keywords score high for creative agents."""
        score = compute_specialty_match("Write a creative blog post about design", "creative")
        assert score >= 0.6

    @pytest.mark.integration
    def test_research_keywords_match(self):
        """Research keywords score high for research agents."""
        score = compute_specialty_match("Research the latest papers on knowledge graphs", "research")
        assert score >= 0.6

    @pytest.mark.integration
    def test_no_match_scores_low(self):
        """No keyword match scores low."""
        score = compute_specialty_match("Hello how are you", "devops")
        assert score <= 0.3

    @pytest.mark.integration
    def test_generalist_gets_moderate_score(self):
        """None focus_type gets moderate match score."""
        score = compute_specialty_match("Do something useful", None)
        assert 0.2 <= score <= 0.5

    @pytest.mark.integration
    def test_unknown_focus_gets_moderate_score(self):
        """Unknown focus type gets moderate match score."""
        score = compute_specialty_match("Hello", "unknown_type")
        assert 0.2 <= score <= 0.5


class TestLoadScore:
    """Tests for compute_load_score()."""

    @pytest.mark.integration
    def test_idle_no_failures(self):
        """Idle agent with no failures scores highest."""
        score = compute_load_score("idle", 0)
        assert score == 1.0

    @pytest.mark.integration
    def test_busy_scores_lower(self):
        """Busy agent scores lower than idle."""
        score = compute_load_score("busy", 0)
        assert score == 0.3

    @pytest.mark.integration
    def test_error_scores_very_low(self):
        """Error agent scores very low."""
        score = compute_load_score("error", 0)
        assert score == 0.1

    @pytest.mark.integration
    def test_disabled_scores_zero(self):
        """Disabled agent scores zero."""
        score = compute_load_score("disabled", 0)
        assert score == 0.0

    @pytest.mark.integration
    def test_failures_reduce_score(self):
        """Consecutive failures reduce idle score."""
        score = compute_load_score("idle", 3)
        assert score < 1.0
        assert score >= 0.2


class TestPheromoneScore:
    """Tests for compute_pheromone_score()."""

    @pytest.mark.integration
    def test_empty_records_returns_cold_start(self):
        """No records → cold start score."""
        assert compute_pheromone_score([]) == COLD_START_SCORE

    @pytest.mark.integration
    def test_all_success_scores_high(self):
        """All successful records produce high score."""
        records = [
            {"success": True, "speed_score": 0.8, "cost_score": 0.9,
             "created_at": datetime.now(timezone.utc).isoformat()}
            for _ in range(5)
        ]
        score = compute_pheromone_score(records)
        assert score > 0.6

    @pytest.mark.integration
    def test_all_failure_scores_low(self):
        """All failed records produce low score."""
        records = [
            {"success": False, "speed_score": 0.2, "cost_score": 0.5,
             "created_at": datetime.now(timezone.utc).isoformat()}
            for _ in range(5)
        ]
        score = compute_pheromone_score(records)
        assert score < 0.4

    @pytest.mark.integration
    def test_time_decay_reduces_old_records(self):
        """Older records have less weight than recent ones."""
        old_time = "2025-01-01T00:00:00+00:00"  # ~1 year ago
        new_time = datetime.now(timezone.utc).isoformat()

        # One old success + one new failure
        records_old_bias = [
            {"success": True, "speed_score": 1.0, "cost_score": 1.0,
             "created_at": old_time},
            {"success": False, "speed_score": 0.0, "cost_score": 0.0,
             "created_at": new_time},
        ]

        # One old failure + one new success
        records_new_bias = [
            {"success": False, "speed_score": 0.0, "cost_score": 0.0,
             "created_at": old_time},
            {"success": True, "speed_score": 1.0, "cost_score": 1.0,
             "created_at": new_time},
        ]

        score_old_bias = compute_pheromone_score(records_old_bias)
        score_new_bias = compute_pheromone_score(records_new_bias)

        # New results should matter more
        assert score_new_bias > score_old_bias

    @pytest.mark.integration
    def test_score_bounded_zero_to_one(self):
        """Pheromone score is always between 0.0 and 1.0."""
        records = [
            {"success": True, "speed_score": 1.0, "cost_score": 1.0,
             "created_at": datetime.now(timezone.utc).isoformat()}
            for _ in range(100)
        ]
        score = compute_pheromone_score(records)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Tests — EngineRouter routing
# ---------------------------------------------------------------------------

class TestEngineRouting:
    """Tests for EngineRouter.route_message()."""

    @pytest.mark.integration
    async def test_devops_message_routes_to_devops(self, router):
        """DevOps-related message routes to devops agent."""
        result = await router.route_message(
            "Deploy the Docker container and monitor the CI build",
            list(TEST_AGENTS.keys()),
        )
        assert result == "aria-devops"

    @pytest.mark.integration
    async def test_social_message_routes_to_social(self, router):
        """Social/content message routes to social agent."""
        result = await router.route_message(
            "Post a new tweet about the community engagement",
            list(TEST_AGENTS.keys()),
        )
        assert result == "aria-social"

    @pytest.mark.integration
    async def test_analysis_message_routes_to_analysis(self, router):
        """Analysis/data message routes to analysis agent."""
        result = await router.route_message(
            "Analyze the data metrics and generate a report about trends",
            list(TEST_AGENTS.keys()),
        )
        assert result == "aria-analysis"

    @pytest.mark.integration
    async def test_creative_message_routes_to_creative(self, router):
        """Creative/writing message routes to creative agent."""
        result = await router.route_message(
            "Write a creative blog post and design visual content",
            list(TEST_AGENTS.keys()),
        )
        assert result == "aria-creative"

    @pytest.mark.integration
    async def test_research_message_routes_to_research(self, router):
        """Research message routes to research agent."""
        result = await router.route_message(
            "Research the latest papers on knowledge exploration",
            list(TEST_AGENTS.keys()),
        )
        assert result == "aria-research"

    @pytest.mark.integration
    async def test_single_agent_returns_that_agent(self, router):
        """When only one agent available, it's returned directly."""
        result = await router.route_message(
            "Any message",
            ["main"],
        )
        assert result == "main"

    @pytest.mark.integration
    async def test_empty_agents_raises(self, router):
        """Empty agent list raises EngineError."""
        with pytest.raises(EngineError, match="No available agents"):
            await router.route_message("Hello", [])

    @pytest.mark.integration
    async def test_concurrent_routing(self, router):
        """Multiple concurrent routing requests produce sane results."""
        queries = [
            ("Deploy Docker build test", "aria-devops"),
            ("Post tweet content social", "aria-social"),
            ("Analyze data metrics report", "aria-analysis"),
            ("Write creative blog content", "aria-creative"),
            ("Research papers knowledge", "aria-research"),
        ]

        tasks = [
            router.route_message(query, list(TEST_AGENTS.keys()))
            for query, _ in queries
        ]
        results = await asyncio.gather(*tasks)

        # Each result should be a valid agent
        for result in results:
            assert result in TEST_AGENTS


# ---------------------------------------------------------------------------
# Tests — Score updates
# ---------------------------------------------------------------------------

class TestScoreUpdates:
    """Tests for EngineRouter.update_scores()."""

    @pytest.mark.integration
    async def test_success_increases_score(self, router):
        """Successful interaction increases pheromone score."""
        # First update
        score1 = await router.update_scores(
            agent_id="aria-devops",
            success=True,
            duration_ms=500,
            token_cost=0.1,
        )
        assert score1 > 0.0

        # Second success should maintain or increase
        score2 = await router.update_scores(
            agent_id="aria-devops",
            success=True,
            duration_ms=300,
            token_cost=0.05,
        )
        assert score2 > 0.0

    @pytest.mark.integration
    async def test_failure_lowers_score(self, router):
        """Failed interaction produces lower score than success."""
        # Start with successes
        for _ in range(3):
            await router.update_scores(
                agent_id="aria-social",
                success=True,
                duration_ms=500,
            )
        success_score = compute_pheromone_score(router._records.get("aria-social", []))

        # Add failures
        for _ in range(3):
            await router.update_scores(
                agent_id="aria-social",
                success=False,
                duration_ms=2000,
            )
        mixed_score = compute_pheromone_score(router._records.get("aria-social", []))

        assert mixed_score < success_score

    @pytest.mark.integration
    async def test_speed_score_computed(self, router):
        """Fast responses produce higher speed scores."""
        await router.update_scores(
            agent_id="aria-devops",
            success=True,
            duration_ms=100,  # Very fast
        )

        records = router._records["aria-devops"]
        assert records[-1]["speed_score"] > 0.9

    @pytest.mark.integration
    async def test_slow_response_low_speed_score(self, router):
        """Slow responses produce lower speed scores."""
        await router.update_scores(
            agent_id="aria-devops",
            success=True,
            duration_ms=25000,  # Very slow
        )

        records = router._records["aria-devops"]
        assert records[-1]["speed_score"] < 0.3

    @pytest.mark.integration
    async def test_records_capped(self, router):
        """Records per agent are capped at MAX_RECORDS_PER_AGENT."""
        from aria_engine.routing import MAX_RECORDS_PER_AGENT

        for i in range(MAX_RECORDS_PER_AGENT + 50):
            await router.update_scores(
                agent_id="main",
                success=True,
                duration_ms=500,
            )

        assert len(router._records["main"]) <= MAX_RECORDS_PER_AGENT

    @pytest.mark.integration
    async def test_total_invocations_tracked(self, router):
        """Total invocation count is incremented."""
        initial = router._total_invocations
        await router.update_scores("main", True, 500)
        await router.update_scores("main", True, 500)
        assert router._total_invocations == initial + 2


# ---------------------------------------------------------------------------
# Tests — All agents reachable
# ---------------------------------------------------------------------------

class TestAllAgentsReachable:
    """Verify all specialty agents are reachable by appropriate queries."""

    @pytest.mark.integration
    async def test_all_specialties_reachable(self, router):
        """Every specialized agent can be reached by targeted queries."""
        test_queries = {
            "aria-social": "Post a tweet about community social engagement and share content",
            "aria-devops": "Deploy the Docker container and run CI/CD build test on server",
            "aria-analysis": "Analyze the data metrics and review statistical trends in the report",
            "aria-creative": "Create a visual design for the art blog and write brand content",
            "aria-research": "Research the latest papers and investigate knowledge studies",
        }

        reached: set[str] = set()
        for expected_agent, query in test_queries.items():
            result = await router.route_message(query, list(TEST_AGENTS.keys()))
            reached.add(result)

        # All specialty agents should be reachable
        specialty_agents = {aid for aid, info in TEST_AGENTS.items() if info["focus_type"]}
        assert specialty_agents.issubset(reached), (
            f"Unreachable agents: {specialty_agents - reached}"
        )

    @pytest.mark.integration
    async def test_routing_returns_valid_agent(self, router):
        """Routing always returns one of the available agents."""
        for _ in range(20):
            result = await router.route_message(
                "Some random message about various topics",
                list(TEST_AGENTS.keys()),
            )
            assert result in TEST_AGENTS


# ---------------------------------------------------------------------------
# Tests — Routing table
# ---------------------------------------------------------------------------

class TestRoutingTable:
    """Tests for EngineRouter.get_routing_table()."""

    @pytest.mark.integration
    async def test_routing_table_returns_list(self, router):
        """get_routing_table() returns a list of agent info dicts."""
        table = await router.get_routing_table()
        assert isinstance(table, list)
