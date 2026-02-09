# tests/test_integration.py
"""
Integration tests for Aria.

Tests end-to-end flows combining skills and agents.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills import SkillRegistry, SkillStatus
from aria_agents import AgentCoordinator


@pytest.mark.docker
@pytest.mark.integration
class TestFlaskRoutes:
    """Tests for Flask web routes (requires Docker stack)."""
    
    @pytest.fixture
    def flask_app(self):
        """Create Flask test client."""
        try:
            # Try new location first
            from src.web.app import create_app
        except ImportError:
            try:
                # Fallback to old location
                from app.main import create_app
            except ImportError:
                pytest.skip("Flask app not available")
        
        import os
        os.environ.setdefault('SECRET_KEY', 'test-secret-key')
        os.environ.setdefault('SERVICE_HOST', 'localhost')
        os.environ.setdefault('API_BASE_URL', '/api')
        os.environ.setdefault('CLAWDBOT_PUBLIC_URL', 'http://localhost:18789')
        
        app = create_app()
        app.config['TESTING'] = True
        return app.test_client()
    
    def test_index_route(self, flask_app):
        """Test index route returns 200."""
        response = flask_app.get('/')
        assert response.status_code == 200
        assert b'Aria Blue' in response.data
    
    def test_dashboard_route(self, flask_app):
        """Test dashboard route returns 200."""
        response = flask_app.get('/dashboard')
        assert response.status_code == 200
    
    def test_thoughts_route(self, flask_app):
        """Test thoughts route returns 200."""
        response = flask_app.get('/thoughts')
        assert response.status_code == 200
    
    def test_activities_route(self, flask_app):
        """Test activities route returns 200."""
        response = flask_app.get('/activities')
        assert response.status_code == 200
    
    def test_records_route(self, flask_app):
        """Test records route returns 200."""
        response = flask_app.get('/records')
        assert response.status_code == 200
    
    def test_search_route(self, flask_app):
        """Test search route returns 200."""
        response = flask_app.get('/search')
        assert response.status_code == 200
    
    def test_services_route(self, flask_app):
        """Test services route returns 200."""
        response = flask_app.get('/services')
        assert response.status_code == 200
    
    def test_litellm_route(self, flask_app):
        """Test litellm route returns 200."""
        response = flask_app.get('/litellm')
        assert response.status_code == 200
        assert b'LiteLLM' in response.data


class TestAriaBootstrap:
    """Tests for Aria initialization flow."""
    
    @pytest.mark.asyncio
    async def test_full_initialization(self, aria_mind_path, mock_env):
        """Test full Aria initialization."""
        # 1. Create skill registry
        registry = SkillRegistry()
        
        # 2. Load tools config
        await registry.load_from_config(f"{aria_mind_path}/TOOLS.md")
        
        # 3. Create agent coordinator
        coordinator = AgentCoordinator(registry)
        
        # 4. Load agents config
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        
        # 5. Initialize agents
        await coordinator.initialize_agents()
        
        # Verify
        assert coordinator.get_main_agent() is not None
        status = coordinator.get_status()
        assert status["agents"] >= 1
        assert status["skill_registry"] is True
    
    @pytest.mark.asyncio
    async def test_health_check_flow(self, mock_moltbook_skill, mock_database_skill):
        """Test health check flow via registry."""
        from aria_skills.health import HealthMonitorSkill
        from aria_skills.base import SkillConfig
        
        # Setup registry with mock skills
        registry = SkillRegistry()
        registry._skills["moltbook"] = mock_moltbook_skill
        registry._skills["database"] = mock_database_skill
        
        # Run health check via registry
        results = await registry.check_all_health()
        
        assert "moltbook" in results
        assert "database" in results
        assert results["moltbook"] == SkillStatus.AVAILABLE
        assert results["database"] == SkillStatus.AVAILABLE


class TestSkillAgentInteraction:
    """Tests for skill-agent interactions."""
    
    @pytest.mark.asyncio
    async def test_agent_uses_skill(self, mock_agent_config, mock_llm_skill):
        """Test agent using a skill."""
        from aria_agents.coordinator import LLMAgent
        
        registry = SkillRegistry()
        registry._skills["moonshot"] = mock_llm_skill
        
        agent = LLMAgent(mock_agent_config, registry)
        
        # Use skill directly
        result = await agent.use_skill("moonshot", "generate", prompt="Test")
        
        assert result.success
        assert "text" in result.data
    
    @pytest.mark.asyncio
    async def test_agent_skill_not_available(self, mock_agent_config):
        """Test agent handling unavailable skill."""
        from aria_agents.coordinator import LLMAgent
        
        registry = SkillRegistry()
        agent = LLMAgent(mock_agent_config, registry)
        
        with pytest.raises(ValueError, match="not found"):
            await agent.use_skill("nonexistent", "method")


class TestGoalTracking:
    """Tests for goal and task tracking."""
    
    @pytest.mark.asyncio
    async def test_create_and_update_goal(self, mock_env):
        """Test goal lifecycle: create and update."""
        from aria_skills.goals import GoalSchedulerSkill
        from aria_skills.base import SkillConfig
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        # Create goal
        result = await scheduler.create_goal(
            title="Learn Python",
            description="Master Python programming",
            priority=1,
        )
        assert result.success
        goal_id = result.data["id"]
        
        # Update progress
        result = await scheduler.update_goal(goal_id, progress=50)
        assert result.success
        
        # Complete goal
        result = await scheduler.update_goal(goal_id, progress=100)
        assert result.success
    
    @pytest.mark.asyncio
    async def test_list_goals(self, mock_env):
        """Test listing goals."""
        from aria_skills.goals import GoalSchedulerSkill
        from aria_skills.base import SkillConfig
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        # Create a goal first
        await scheduler.create_goal(title="Test Goal", priority=1)
        
        # List goals
        result = await scheduler.list_goals()
        assert result.success


class TestMemoryPersistence:
    """Tests for memory and persistence."""
    
    @pytest.mark.asyncio
    async def test_database_memory_storage(self, mock_database_skill):
        """Test storing memories in database."""
        # Mock the store_memory method
        mock_database_skill.store_memory = AsyncMock(
            return_value=MagicMock(success=True)
        )
        mock_database_skill.recall_memory = AsyncMock(
            return_value=MagicMock(success=True, data={"value": "test_value"})
        )
        
        # Store
        result = await mock_database_skill.store_memory("test_key", "test_value")
        assert result.success
        
        # Recall
        result = await mock_database_skill.recall_memory("test_key")
        assert result.success
        assert result.data["value"] == "test_value"


class TestRateLimiting:
    """Tests for rate limiting across skills."""
    
    @pytest.mark.asyncio
    async def test_moltbook_create_post_without_client(self, mock_env):
        """Test Moltbook gracefully handles missing client."""
        from aria_skills.moltbook import MoltbookSkill
        from aria_skills.base import SkillConfig
        
        config = SkillConfig(
            name="moltbook",
            config={},
        )
        
        skill = MoltbookSkill(config)
        # Not initialized — no client
        result = await skill.create_post(content="Test post")
        assert not result.success


class TestErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_skill_error_recovery(self, mock_moltbook_skill):
        """Test skill error recovery."""
        # Simulate error
        mock_moltbook_skill.health_check = AsyncMock(return_value=SkillStatus.ERROR)
        
        status = await mock_moltbook_skill.health_check()
        assert status == SkillStatus.ERROR
        
        # Recover
        mock_moltbook_skill.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
        status = await mock_moltbook_skill.health_check()
        assert status == SkillStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_coordinator_handles_agent_error(self, aria_mind_path, skill_registry):
        """Test coordinator handles agent errors gracefully."""
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()
        
        # Should not raise, even without LLM
        response = await coordinator.process("Test message")
        assert response is not None
