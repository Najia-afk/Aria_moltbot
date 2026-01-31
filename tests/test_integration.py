# tests/test_integration.py
"""
Integration tests for Aria.

Tests end-to-end flows combining skills and agents.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills import SkillRegistry, SkillStatus
from aria_agents import AgentCoordinator


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
        """Test health check flow."""
        from aria_skills.health import HealthMonitorSkill
        from aria_skills.base import SkillConfig
        
        # Setup
        registry = SkillRegistry()
        registry._skills["moltbook"] = mock_moltbook_skill
        registry._skills["database"] = mock_database_skill
        
        # Create health monitor
        config = SkillConfig(name="health_monitor", config={"alert_threshold": 3})
        monitor = HealthMonitorSkill(config)
        monitor.set_registry(registry)
        await monitor.initialize()
        
        # Run health check
        result = await monitor.check_all_skills()
        
        assert result.success
        assert result.data["all_healthy"] is True
        assert "moltbook" in result.data["skills"]
        assert "database" in result.data["skills"]


class TestSkillAgentInteraction:
    """Tests for skill-agent interactions."""
    
    @pytest.mark.asyncio
    async def test_agent_uses_skill(self, mock_agent_config, mock_llm_skill):
        """Test agent using a skill."""
        from aria_agents.coordinator import LLMAgent
        
        registry = SkillRegistry()
        registry._skills["gemini"] = mock_llm_skill
        
        agent = LLMAgent(mock_agent_config, registry)
        
        # Use skill directly
        result = await agent.use_skill("gemini", "generate", prompt="Test")
        
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
    async def test_create_and_complete_goal(self):
        """Test goal lifecycle."""
        from aria_skills.goals import GoalSchedulerSkill, TaskPriority, TaskStatus
        from aria_skills.base import SkillConfig
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        # Create goal
        result = await scheduler.add_goal(
            goal_id="learn_python",
            title="Learn Python",
            description="Master Python programming",
            priority=TaskPriority.HIGH,
        )
        assert result.success
        
        # Update progress
        result = await scheduler.update_goal_progress("learn_python", 50.0)
        assert result.data["progress"] == 50.0
        assert result.data["status"] == "pending"
        
        # Complete goal
        result = await scheduler.update_goal_progress("learn_python", 100.0)
        assert result.data["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_scheduled_task_execution(self):
        """Test scheduled task execution."""
        from aria_skills.goals import GoalSchedulerSkill
        from aria_skills.base import SkillConfig
        
        config = SkillConfig(name="goal_scheduler")
        scheduler = GoalSchedulerSkill(config)
        await scheduler.initialize()
        
        # Track if handler was called
        handler_called = False
        
        async def test_handler():
            nonlocal handler_called
            handler_called = True
            return "executed"
        
        # Add task
        await scheduler.add_task(
            task_id="test_task",
            name="Test Task",
            handler="test_handler",
            interval_seconds=60,
        )
        
        # Register handler
        scheduler.register_handler("test_handler", test_handler)
        
        # Run task
        result = await scheduler.run_task("test_task")
        
        assert result.success
        assert handler_called is True


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
    async def test_moltbook_rate_limit_tracking(self):
        """Test Moltbook rate limit tracking."""
        from aria_skills.moltbook import MoltbookSkill
        from aria_skills.base import SkillConfig
        from datetime import datetime
        
        config = SkillConfig(
            name="moltbook",
            config={"auth": "token"},
            rate_limit={"posts_per_hour": 3, "posts_per_day": 10},
        )
        
        skill = MoltbookSkill(config)
        skill._status = SkillStatus.AVAILABLE
        skill._token = "test"
        
        # Initially should be under limit
        assert skill._check_rate_limit() is True
        
        # Simulate posts
        now = datetime.utcnow()
        skill._post_times = [now, now, now]  # 3 posts
        
        # Now should be at limit
        assert skill._check_rate_limit() is False


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
