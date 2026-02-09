# tests/test_skill_persistence.py
"""
TICKET-12: Tests for in-memory stub elimination.

Verifies that:
- Bucket A skills use httpx.AsyncClient as primary store (API-backed)
- Bucket A skills still keep fallback caches (safety net)
- Bucket C skills emit deprecation warnings
- API delegation pattern is correct (mock httpx)
"""
import asyncio
import os
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from aria_skills.base import SkillConfig, SkillResult, SkillStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(name: str = "test") -> SkillConfig:
    return SkillConfig(name=name, enabled=True, config={})


# ===========================================================================
# BUCKET A — httpx.AsyncClient is created in initialize()
# ===========================================================================

class TestGoalSkillPersistence:
    """GoalSchedulerSkill should delegate to REST API via httpx."""

    def test_has_api_url_and_client_attrs(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        assert hasattr(skill, "_api_url")
        assert hasattr(skill, "_client")
        assert skill._client is None  # before initialize

    @pytest.mark.asyncio
    async def test_initialize_creates_httpx_client(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_create_goal_calls_api(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "goal_1", "title": "test"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.create_goal(title="test goal")
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_list_goals_calls_api(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"id": "g1", "status": "active"}]

        with patch.object(skill._client, "get", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.list_goals()
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_update_goal_calls_api(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "goal_1", "status": "completed"}

        with patch.object(skill._client, "put", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.update_goal("goal_1", status="completed")
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_fallback_on_api_failure(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        await skill.initialize()

        # Make API call raise
        with patch.object(skill._client, "post", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")):
            result = await skill.create_goal(title="fallback test")
            assert result.success  # should succeed via fallback
            assert result.data.get("title") == "fallback test"  # data preserved

        await skill.close()

    def test_goals_dict_is_fallback_only(self):
        from aria_skills.goals import GoalSchedulerSkill
        skill = GoalSchedulerSkill(_cfg("goals"))
        # _goals dict should exist but be empty — it's the fallback cache
        assert isinstance(skill._goals, dict)
        assert len(skill._goals) == 0


class TestSocialSkillPersistence:
    """SocialSkill should delegate to REST API via httpx."""

    def test_has_api_attrs(self):
        from aria_skills.social import SocialSkill
        skill = SocialSkill(_cfg("social"))
        assert hasattr(skill, "_api_url")
        assert hasattr(skill, "_client")

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        from aria_skills.social import SocialSkill
        skill = SocialSkill(_cfg("social"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_create_post_calls_api(self):
        from aria_skills.social import SocialSkill
        skill = SocialSkill(_cfg("social"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "post_1"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.create_post(content="hello")
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_get_posts_calls_api(self):
        from aria_skills.social import SocialSkill
        skill = SocialSkill(_cfg("social"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"id": "post_1"}]

        with patch.object(skill._client, "get", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.get_posts()
            m.assert_called_once()
            assert result.success

        await skill.close()

    def test_posts_list_is_fallback(self):
        from aria_skills.social import SocialSkill
        skill = SocialSkill(_cfg("social"))
        assert isinstance(skill._posts, list)
        assert len(skill._posts) == 0


class TestHourlyGoalsSkillPersistence:
    """HourlyGoalsSkill should delegate to REST API via httpx."""

    def test_has_api_attrs(self):
        from aria_skills.hourly_goals import HourlyGoalsSkill
        skill = HourlyGoalsSkill(_cfg("hourly_goals"))
        assert hasattr(skill, "_api_url")
        assert hasattr(skill, "_client")

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        from aria_skills.hourly_goals import HourlyGoalsSkill
        skill = HourlyGoalsSkill(_cfg("hourly_goals"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_set_goal_calls_api(self):
        from aria_skills.hourly_goals import HourlyGoalsSkill
        skill = HourlyGoalsSkill(_cfg("hourly_goals"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "hg_10_0"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.set_goal(hour=10, goal="test")
            m.assert_called_once()
            assert result.success

        await skill.close()

    def test_hourly_goals_dict_is_fallback(self):
        from aria_skills.hourly_goals import HourlyGoalsSkill
        skill = HourlyGoalsSkill(_cfg("hourly_goals"))
        assert isinstance(skill._hourly_goals, dict)


class TestScheduleSkillPersistence:
    """ScheduleSkill should delegate to REST API via httpx."""

    def test_has_api_attrs(self):
        from aria_skills.schedule import ScheduleSkill
        skill = ScheduleSkill(_cfg("schedule"))
        assert hasattr(skill, "_api_url")
        assert hasattr(skill, "_client")

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        from aria_skills.schedule import ScheduleSkill
        skill = ScheduleSkill(_cfg("schedule"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_create_job_calls_api(self):
        from aria_skills.schedule import ScheduleSkill
        skill = ScheduleSkill(_cfg("schedule"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "job_1"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.create_job(name="test", schedule="every 1 hours", action="test")
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_list_jobs_calls_api(self):
        from aria_skills.schedule import ScheduleSkill
        skill = ScheduleSkill(_cfg("schedule"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"id": "job_1", "enabled": True}]

        with patch.object(skill._client, "get", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.list_jobs()
            m.assert_called_once()
            assert result.success

        await skill.close()

    def test_jobs_dict_is_fallback(self):
        from aria_skills.schedule import ScheduleSkill
        skill = ScheduleSkill(_cfg("schedule"))
        assert isinstance(skill._jobs, dict)


class TestPerformanceSkillPersistence:
    """PerformanceSkill should delegate to REST API via httpx."""

    def test_has_api_attrs(self):
        from aria_skills.performance import PerformanceSkill
        skill = PerformanceSkill(_cfg("performance"))
        assert hasattr(skill, "_api_url")
        assert hasattr(skill, "_client")

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        from aria_skills.performance import PerformanceSkill
        skill = PerformanceSkill(_cfg("performance"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_log_review_calls_api(self):
        from aria_skills.performance import PerformanceSkill
        skill = PerformanceSkill(_cfg("performance"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "perf_1"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.log_review(
                period="2026-02-09",
                successes=["ok"],
                failures=["nope"],
                improvements=["more"],
            )
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_get_reviews_calls_api(self):
        from aria_skills.performance import PerformanceSkill
        skill = PerformanceSkill(_cfg("performance"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"id": "perf_1"}]

        with patch.object(skill._client, "get", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.get_reviews()
            m.assert_called_once()
            assert result.success

        await skill.close()

    def test_logs_list_is_fallback(self):
        from aria_skills.performance import PerformanceSkill
        skill = PerformanceSkill(_cfg("performance"))
        assert isinstance(skill._logs, list)


class TestKnowledgeGraphSkillPersistence:
    """KnowledgeGraphSkill should delegate to REST API via httpx."""

    def test_has_api_attrs(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(_cfg("knowledge_graph"))
        assert hasattr(skill, "_api_url")
        assert hasattr(skill, "_client")

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(_cfg("knowledge_graph"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_add_entity_calls_api(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(_cfg("knowledge_graph"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "concept:test"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.add_entity(name="test", entity_type="concept")
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_add_relation_calls_api(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(_cfg("knowledge_graph"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"from": "a", "to": "b"}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.add_relation(from_entity="a", relation="related", to_entity="b")
            m.assert_called_once()
            assert result.success

        await skill.close()

    @pytest.mark.asyncio
    async def test_query_calls_api(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(_cfg("knowledge_graph"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"id": "concept:test"}]

        with patch.object(skill._client, "get", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.query(entity_type="concept")
            m.assert_called_once()
            assert result.success

        await skill.close()

    def test_entities_and_relations_are_fallbacks(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(_cfg("knowledge_graph"))
        assert isinstance(skill._entities, dict)
        assert isinstance(skill._relations, list)


class TestResearchSkillPersistence:
    """ResearchSkill should persist projects to /memories via httpx."""

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        from aria_skills.research import ResearchSkill
        skill = ResearchSkill(_cfg("research"))
        await skill.initialize()
        assert isinstance(skill._client, httpx.AsyncClient)
        await skill.close()

    @pytest.mark.asyncio
    async def test_start_project_persists_to_api(self):
        from aria_skills.research import ResearchSkill
        skill = ResearchSkill(_cfg("research"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": True}

        with patch.object(skill._client, "post", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.start_project(topic="AI Safety")
            assert result.success
            assert m.called  # post to /memories

        await skill.close()

    @pytest.mark.asyncio
    async def test_list_projects_tries_api(self):
        from aria_skills.research import ResearchSkill
        skill = ResearchSkill(_cfg("research"))
        await skill.initialize()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = []

        with patch.object(skill._client, "get", new_callable=AsyncMock, return_value=mock_resp) as m:
            result = await skill.list_projects()
            m.assert_called_once()
            assert result.success

        await skill.close()

    def test_has_serialize_and_save_methods(self):
        from aria_skills.research import ResearchSkill
        skill = ResearchSkill(_cfg("research"))
        assert hasattr(skill, "_save_project_to_api")
        assert hasattr(skill, "_serialize_project")


# ===========================================================================
# BUCKET C — Deprecation warnings
# ===========================================================================

class TestBucketCDeprecations:
    """Bucket C skills should emit DeprecationWarning on initialize()."""

    @pytest.mark.asyncio
    async def test_brainstorm_deprecation(self):
        from aria_skills.brainstorm import BrainstormSkill
        skill = BrainstormSkill(_cfg("brainstorm"))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await skill.initialize()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "research" in str(deprecation_warnings[0].message).lower()

    @pytest.mark.asyncio
    async def test_community_deprecation(self):
        from aria_skills.community import CommunitySkill
        skill = CommunitySkill(_cfg("community"))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await skill.initialize()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "social" in str(deprecation_warnings[0].message).lower()

    @pytest.mark.asyncio
    async def test_model_switcher_deprecation(self):
        from aria_skills.model_switcher import ModelSwitcherSkill
        skill = ModelSwitcherSkill(_cfg("model_switcher"))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await skill.initialize()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "litellm" in str(deprecation_warnings[0].message).lower()

    @pytest.mark.asyncio
    async def test_fact_check_deprecation(self):
        from aria_skills.fact_check import FactCheckSkill
        skill = FactCheckSkill(_cfg("fact_check"))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await skill.initialize()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "research" in str(deprecation_warnings[0].message).lower()


# ===========================================================================
# BUCKET B — TODO-only stubs (just verify they still import and init)
# ===========================================================================

class TestBucketBStubs:
    """Bucket B skills should still work but log warnings about missing endpoints."""

    @pytest.mark.asyncio
    async def test_portfolio_initializes(self):
        from aria_skills.portfolio import PortfolioSkill
        skill = PortfolioSkill(_cfg("portfolio"))
        result = await skill.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_experiment_initializes(self):
        from aria_skills.experiment import ExperimentSkill
        skill = ExperimentSkill(_cfg("experiment"))
        result = await skill.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_data_pipeline_initializes(self):
        from aria_skills.data_pipeline import DataPipelineSkill
        skill = DataPipelineSkill(_cfg("data_pipeline"))
        result = await skill.initialize()
        assert result is True


# ===========================================================================
# Cross-cutting: close() method exists on all Bucket A skills
# ===========================================================================

class TestCloseMethod:
    """All Bucket A skills should have a close() method."""

    def test_goals_has_close(self):
        from aria_skills.goals import GoalSchedulerSkill
        assert hasattr(GoalSchedulerSkill, "close")

    def test_social_has_close(self):
        from aria_skills.social import SocialSkill
        assert hasattr(SocialSkill, "close")

    def test_hourly_goals_has_close(self):
        from aria_skills.hourly_goals import HourlyGoalsSkill
        assert hasattr(HourlyGoalsSkill, "close")

    def test_schedule_has_close(self):
        from aria_skills.schedule import ScheduleSkill
        assert hasattr(ScheduleSkill, "close")

    def test_performance_has_close(self):
        from aria_skills.performance import PerformanceSkill
        assert hasattr(PerformanceSkill, "close")

    def test_knowledge_graph_has_close(self):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        assert hasattr(KnowledgeGraphSkill, "close")

    def test_research_has_close(self):
        from aria_skills.research import ResearchSkill
        assert hasattr(ResearchSkill, "close")
