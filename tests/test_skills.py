# tests/test_skills.py
"""
Tests for aria_skills package.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

pytestmark = pytest.mark.unit


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
    async def test_create_post_no_client(self, mock_env):
        """Test that create_post fails gracefully without API client."""
        from aria_skills.moltbook import MoltbookSkill
        
        config = SkillConfig(
            name="moltbook",
            config={
                "api_url": "https://test.api",
            },
        )
        
        skill = MoltbookSkill(config)
        # Don't initialize (no httpx client)
        
        result = await skill.create_post(content="Hello world")
        assert not result.success
    
    @pytest.mark.asyncio
    async def test_create_post_empty_content(self, mock_env):
        """Test that empty content is rejected."""
        from aria_skills.moltbook import MoltbookSkill
        
        config = SkillConfig(
            name="moltbook",
            config={"api_key": "test-token"},
        )
        
        skill = MoltbookSkill(config)
        await skill.initialize()
        
        result = await skill.create_post(content="")
        assert not result.success
    
    def test_skill_name(self, mock_env):
        """Test MoltbookSkill has correct name."""
        from aria_skills.moltbook import MoltbookSkill
        
        config = SkillConfig(name="moltbook", config={})
        skill = MoltbookSkill(config)
        assert skill.name == "moltbook"


class TestLLMSkills:
    """Tests for LLM skills."""
    
    def test_moonshot_skill_has_name(self):
        """Test MoonshotSkill has correct name."""
        from aria_skills.llm import MoonshotSkill
        
        config = SkillConfig(name="llm", config={})
        skill = MoonshotSkill(config)
        assert skill.name == "llm"
    
    def test_moonshot_skill_has_chat_method(self):
        """Test MoonshotSkill has chat method."""
        from aria_skills.llm import MoonshotSkill
        
        assert hasattr(MoonshotSkill, "chat")
        assert hasattr(MoonshotSkill, "initialize")
        assert hasattr(MoonshotSkill, "health_check")


class TestHealthMonitorSkill:
    """Tests for HealthMonitorSkill."""
    
    @pytest.mark.asyncio
    async def test_check_system(self):
        """Test system health check."""
        from aria_skills.health import HealthMonitorSkill
        
        config = SkillConfig(
            name="health_monitor",
            config={"alert_threshold": 3},
        )
        
        monitor = HealthMonitorSkill(config)
        await monitor.initialize()
        
        result = await monitor.check_system()
        assert result.success
        assert "overall_status" in result.data
        assert "checks" in result.data
    
    @pytest.mark.asyncio
    async def test_health_monitor_name(self):
        """Test HealthMonitorSkill has correct name."""
        from aria_skills.health import HealthMonitorSkill
        
        config = SkillConfig(name="health_monitor", config={})
        monitor = HealthMonitorSkill(config)
        assert monitor.name == "health"


class TestGoalSchedulerSkill:
    """Tests for GoalSchedulerSkill."""
    
    @pytest.mark.asyncio
    async def test_create_goal(self, mock_env):
        """Test creating a goal (fallback mode)."""
        from aria_skills.goals import GoalSchedulerSkill
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        result = await scheduler.create_goal(
            title="Test Goal",
            description="A test goal",
            priority=1,
        )
        
        assert result.success
        assert result.data["title"] == "Test Goal"
    
    @pytest.mark.asyncio
    async def test_update_goal(self, mock_env):
        """Test updating a goal (fallback mode)."""
        from aria_skills.goals import GoalSchedulerSkill
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        # Create first
        create_result = await scheduler.create_goal(
            title="Update Test",
            description="Will be updated",
        )
        assert create_result.success
        goal_id = create_result.data["id"]
        
        # Update progress
        update_result = await scheduler.update_goal(goal_id, progress=50)
        assert update_result.success
    
    @pytest.mark.asyncio
    async def test_goal_scheduler_name(self, mock_env):
        """Test GoalSchedulerSkill has correct name."""
        from aria_skills.goals import GoalSchedulerSkill
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        assert scheduler.name == "goals"


class TestAriaAPIClient:
    """Tests for AriaAPIClient."""
    
    @pytest.mark.asyncio
    async def test_api_client_init(self):
        """Test API client initialization."""
        from aria_skills.api_client import AriaAPIClient
        
        config = SkillConfig(name="api_client", config={
            "api_url": "http://localhost:8000/api"
        })
        client = AriaAPIClient(config)
        
        assert client.name == "api_client"
    
    @pytest.mark.asyncio
    async def test_api_client_methods_exist(self):
        """Test API client has all required methods."""
        from aria_skills.api_client import AriaAPIClient
        
        # Check all expected methods exist
        assert hasattr(AriaAPIClient, 'get_memories')
        assert hasattr(AriaAPIClient, 'set_memory')
        assert hasattr(AriaAPIClient, 'get_thoughts')
        assert hasattr(AriaAPIClient, 'create_thought')
        assert hasattr(AriaAPIClient, 'get_activities')
        assert hasattr(AriaAPIClient, 'create_activity')
        assert hasattr(AriaAPIClient, 'get_goals')
        assert hasattr(AriaAPIClient, 'create_goal')
        assert hasattr(AriaAPIClient, 'get_heartbeats')
        assert hasattr(AriaAPIClient, 'create_heartbeat')
        assert hasattr(AriaAPIClient, 'get_knowledge_graph')
        assert hasattr(AriaAPIClient, 'get_social_posts')
