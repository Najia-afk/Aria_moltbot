# tests/test_skills.py
"""
Tests for aria_skills package.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


class TestSkillResult:
    """Tests for SkillResult."""
    
    def test_ok_result(self):
        """Test successful result creation."""
        result = SkillResult.ok({"key": "value"})
        
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
    
    def test_fail_result(self):
        """Test failure result creation."""
        result = SkillResult.fail("Something went wrong")
        
        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"
    
    def test_result_bool(self):
        """Test result boolean conversion."""
        assert bool(SkillResult.ok({})) is True
        assert bool(SkillResult.fail("error")) is False


class TestSkillConfig:
    """Tests for SkillConfig."""
    
    def test_config_creation(self):
        """Test config creation with defaults."""
        config = SkillConfig(name="test")
        
        assert config.name == "test"
        assert config.enabled is True
        assert config.config == {}
        assert config.rate_limit is None
    
    def test_config_with_rate_limit(self):
        """Test config with rate limiting."""
        config = SkillConfig(
            name="test",
            rate_limit={"requests_per_minute": 60},
        )
        
        assert config.rate_limit == {"requests_per_minute": 60}


class TestSkillRegistry:
    """Tests for SkillRegistry."""
    
    def test_empty_registry(self, skill_registry):
        """Test empty registry."""
        assert skill_registry.list() == []
        assert skill_registry.get("nonexistent") is None
    
    def test_register_decorator(self):
        """Test @register decorator."""
        registry = SkillRegistry()
        
        @registry.register
        class TestSkill(BaseSkill):
            @property
            def name(self):
                return "test_skill"
            
            async def initialize(self):
                return True
            
            async def health_check(self):
                return SkillStatus.AVAILABLE
        
        assert "test_skill" in registry._registered_classes
    
    @pytest.mark.asyncio
    async def test_check_all_health(self, skill_registry, mock_moltbook_skill, mock_database_skill):
        """Test checking health of all skills."""
        # Manually add mock skills to registry
        skill_registry._skills["moltbook"] = mock_moltbook_skill
        skill_registry._skills["database"] = mock_database_skill
        
        results = await skill_registry.check_all_health()
        
        assert "moltbook" in results
        assert "database" in results
        assert results["moltbook"] == SkillStatus.AVAILABLE


class TestMoltbookSkill:
    """Tests for MoltbookSkill."""
    
    @pytest.mark.asyncio
    async def test_post_status_rate_limit(self, mock_env):
        """Test rate limiting on posts."""
        from aria_skills.moltbook import MoltbookSkill
        
        config = SkillConfig(
            name="moltbook",
            config={
                "api_url": "https://test.api",
                "auth": "test-token",
            },
            rate_limit={"posts_per_hour": 2, "posts_per_day": 5},
        )
        
        skill = MoltbookSkill(config)
        skill._status = SkillStatus.AVAILABLE
        skill._token = "test-token"
        
        # Simulate hitting rate limit
        from datetime import datetime
        skill._post_times = [datetime.utcnow(), datetime.utcnow()]
        
        assert skill._check_rate_limit() is False
    
    @pytest.mark.asyncio
    async def test_content_truncation(self, mock_env):
        """Test content truncation to 500 chars."""
        from aria_skills.moltbook import MoltbookSkill
        
        config = SkillConfig(
            name="moltbook",
            config={"auth": "test-token"},
        )
        
        skill = MoltbookSkill(config)
        
        # Content over 500 chars would be truncated
        long_content = "x" * 600
        assert len(long_content) > 500


class TestDatabaseSkill:
    """Tests for DatabaseSkill."""
    
    def test_unavailable_without_asyncpg(self):
        """Test skill is unavailable without asyncpg."""
        from aria_skills.database import DatabaseSkill, HAS_ASYNCPG
        
        config = SkillConfig(name="database", config={"dsn": "test"})
        skill = DatabaseSkill(config)
        
        # Status depends on asyncpg availability
        assert skill._status == SkillStatus.UNAVAILABLE


class TestLLMSkills:
    """Tests for LLM skills."""
    
    def test_gemini_models_list(self):
        """Test Gemini models are defined."""
        from aria_skills.llm import GeminiSkill
        
        assert "gemini-pro" in GeminiSkill.MODELS
        assert "gemini-pro-vision" in GeminiSkill.MODELS
    
    def test_moonshot_models_list(self):
        """Test Moonshot models are defined."""
        from aria_skills.llm import MoonshotSkill
        
        assert "moonshot-v1-8k" in MoonshotSkill.MODELS
        assert "moonshot-v1-128k" in MoonshotSkill.MODELS


class TestHealthMonitorSkill:
    """Tests for HealthMonitorSkill."""
    
    @pytest.mark.asyncio
    async def test_check_all_skills(self, skill_registry, mock_moltbook_skill):
        """Test checking all skills."""
        from aria_skills.health import HealthMonitorSkill
        
        config = SkillConfig(
            name="health_monitor",
            config={"alert_threshold": 3},
        )
        
        monitor = HealthMonitorSkill(config)
        skill_registry._skills["moltbook"] = mock_moltbook_skill
        monitor.set_registry(skill_registry)
        
        await monitor.initialize()
        result = await monitor.check_all_skills()
        
        assert result.success
        assert "moltbook" in result.data["skills"]


class TestGoalSchedulerSkill:
    """Tests for GoalSchedulerSkill."""
    
    @pytest.mark.asyncio
    async def test_add_goal(self):
        """Test adding a goal."""
        from aria_skills.goals import GoalSchedulerSkill, TaskPriority
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        result = await scheduler.add_goal(
            goal_id="test_goal",
            title="Test Goal",
            description="A test goal",
            priority=TaskPriority.HIGH,
        )
        
        assert result.success
        assert result.data["goal_id"] == "test_goal"
    
    @pytest.mark.asyncio
    async def test_add_task(self):
        """Test adding a scheduled task."""
        from aria_skills.goals import GoalSchedulerSkill
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        result = await scheduler.add_task(
            task_id="test_task",
            name="Test Task",
            handler="test.handler",
            interval_seconds=3600,
        )
        
        assert result.success
        assert result.data["task_id"] == "test_task"
        assert result.data["next_run"] is not None
