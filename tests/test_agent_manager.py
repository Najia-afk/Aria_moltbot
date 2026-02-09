# tests/test_agent_manager.py
"""Tests for agent_manager skill."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus

pytestmark = pytest.mark.unit


@pytest.fixture
def skill_config():
    return SkillConfig(
        name="agent_manager",
        enabled=True,
        config={"api_url": "http://test-api:8000/api"},
    )


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    client = AsyncMock()
    return client


@pytest.fixture
def make_response():
    """Factory for mock httpx responses."""
    def _make(status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return resp
    return _make


@pytest.fixture
async def agent_manager(skill_config, mock_httpx_client):
    """Create an initialized AgentManagerSkill with mocked client."""
    from aria_skills.agent_manager import AgentManagerSkill
    skill = AgentManagerSkill(skill_config)
    await skill.initialize()
    skill._client = mock_httpx_client  # Replace real client with mock
    return skill


class TestAgentManagerInit:
    """Tests for initialization."""

    def test_skill_name(self, skill_config):
        from aria_skills.agent_manager import AgentManagerSkill
        skill = AgentManagerSkill(skill_config)
        assert skill.name == "agent_manager"

    def test_canonical_name(self, skill_config):
        from aria_skills.agent_manager import AgentManagerSkill
        skill = AgentManagerSkill(skill_config)
        assert skill.canonical_name == "aria-agent-manager"

    async def test_initialize(self, skill_config):
        from aria_skills.agent_manager import AgentManagerSkill
        skill = AgentManagerSkill(skill_config)
        result = await skill.initialize()
        assert result is True
        assert skill._status == SkillStatus.AVAILABLE


class TestListAgents:
    """Tests for list_agents."""

    async def test_list_agents_success(self, agent_manager, mock_httpx_client, make_response):
        sessions_data = {
            "sessions": [
                {"id": "abc-123", "agent_id": "analyst", "status": "active"},
                {"id": "def-456", "agent_id": "creator", "status": "active"},
            ],
            "count": 2,
        }
        mock_httpx_client.get = AsyncMock(return_value=make_response(200, sessions_data))

        result = await agent_manager.list_agents()
        assert result.success is True
        assert result.data["count"] == 2

    async def test_list_agents_with_filter(self, agent_manager, mock_httpx_client, make_response):
        mock_httpx_client.get = AsyncMock(return_value=make_response(200, {"sessions": [], "count": 0}))

        result = await agent_manager.list_agents(status="active", agent_id="analyst")
        assert result.success is True
        mock_httpx_client.get.assert_called_once()

    async def test_list_agents_api_error(self, agent_manager, mock_httpx_client, make_response):
        mock_httpx_client.get = AsyncMock(return_value=make_response(500))

        result = await agent_manager.list_agents()
        assert result.success is False


class TestSpawnAgent:
    """Tests for spawn_agent."""

    async def test_spawn_agent_success(self, agent_manager, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {"id": "new-123", "created": True})
        )

        context = {"task": "Analyze market data", "priority": 3}
        result = await agent_manager.spawn_agent("analyst", context)
        assert result.success is True
        assert result.data["created"] is True

    async def test_spawn_agent_no_context(self, agent_manager, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {"id": "new-456", "created": True})
        )

        result = await agent_manager.spawn_agent("devops")
        assert result.success is True

    async def test_spawn_agent_invalid_context(self, agent_manager):
        """Context with empty task should fail validation."""
        result = await agent_manager.spawn_agent("analyst", {"task": ""})
        assert result.success is False
        assert "task" in result.error.lower()


class TestTerminateAgent:
    """Tests for terminate_agent."""

    async def test_terminate_success(self, agent_manager, mock_httpx_client, make_response):
        mock_httpx_client.patch = AsyncMock(
            return_value=make_response(200, {"updated": True})
        )

        result = await agent_manager.terminate_agent("abc-123")
        assert result.success is True
        assert result.data["status"] == "terminated"

    async def test_terminate_not_initialized(self, skill_config):
        from aria_skills.agent_manager import AgentManagerSkill
        skill = AgentManagerSkill(skill_config)
        # Don't initialize — _client is None
        result = await skill.terminate_agent("abc-123")
        assert result.success is False


class TestPruneStale:
    """Tests for prune_stale_sessions."""

    async def test_prune_stale_sessions(self, agent_manager, mock_httpx_client, make_response):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
        new_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        sessions_data = {
            "sessions": [
                {"id": "old-1", "started_at": old_time, "status": "active"},
                {"id": "new-1", "started_at": new_time, "status": "active"},
            ],
            "count": 2,
        }

        mock_httpx_client.get = AsyncMock(return_value=make_response(200, sessions_data))
        mock_httpx_client.patch = AsyncMock(return_value=make_response(200, {"updated": True}))

        result = await agent_manager.prune_stale_sessions(max_age_hours=6)
        assert result.success is True
        assert result.data["pruned"] == 1
        assert "old-1" in result.data["session_ids"]

    async def test_prune_nothing_to_prune(self, agent_manager, mock_httpx_client, make_response):
        new_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

        mock_httpx_client.get = AsyncMock(
            return_value=make_response(200, {"sessions": [{"id": "x", "started_at": new_time}], "count": 1})
        )

        result = await agent_manager.prune_stale_sessions()
        assert result.success is True
        assert result.data["pruned"] == 0


class TestGetStats:
    """Tests for get_agent_stats."""

    async def test_get_aggregate_stats(self, agent_manager, mock_httpx_client, make_response):
        stats_data = {
            "total_sessions": 50,
            "active_sessions": 3,
            "total_tokens": 150000,
            "total_cost": 1.25,
        }
        mock_httpx_client.get = AsyncMock(return_value=make_response(200, stats_data))

        result = await agent_manager.get_agent_stats()
        assert result.success is True
        assert result.data["total_sessions"] == 50


class TestPerformanceReport:
    """Tests for get_performance_report."""

    async def test_performance_report(self, agent_manager, mock_httpx_client, make_response):
        stats_data = {
            "total_sessions": 100,
            "active_sessions": 5,
            "total_tokens": 500000,
            "total_cost": 3.50,
            "by_agent": [{"agent_id": "main", "sessions": 80}],
            "by_status": [{"status": "active", "count": 5}],
        }
        mock_httpx_client.get = AsyncMock(return_value=make_response(200, stats_data))

        result = await agent_manager.get_performance_report()
        assert result.success is True
        assert result.data["total_sessions"] == 100
        assert "generated_at" in result.data
        assert len(result.data["by_agent"]) == 1


class TestSkillRegistration:
    """Test that the skill is properly registered."""

    def test_registered_in_registry(self):
        from aria_skills.registry import SkillRegistry
        assert "agent_manager" in SkillRegistry._skill_classes

    def test_registered_canonical(self):
        from aria_skills.registry import SkillRegistry
        assert "aria-agent-manager" in SkillRegistry._skill_classes
