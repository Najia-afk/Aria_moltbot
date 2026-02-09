# tests/test_agents.py
"""
Tests for aria_agents package.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from aria_agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from aria_agents.context import AgentContext, AgentResult
from aria_agents.loader import AgentLoader
from aria_agents.coordinator import AgentCoordinator, LLMAgent, MAX_CONCURRENT_AGENTS


class TestAgentConfig:
    """Tests for AgentConfig."""
    
    def test_config_defaults(self):
        """Test config with default values."""
        config = AgentConfig(
            id="test",
            name="Test Agent",
            role=AgentRole.COORDINATOR,
            model="qwen3-mlx",
        )
        
        assert config.id == "test"
        assert config.parent is None
        assert config.capabilities == []
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
    
    def test_config_with_parent(self):
        """Test config with parent agent."""
        config = AgentConfig(
            id="child",
            name="Child Agent",
            role=AgentRole.RESEARCHER,
            model="qwen3-mlx",
            parent="parent_agent",
        )
        
        assert config.parent == "parent_agent"


class TestAgentMessage:
    """Tests for AgentMessage."""
    
    def test_message_creation(self):
        """Test message creation."""
        msg = AgentMessage(
            role="user",
            content="Hello",
            agent_id="test_agent",
        )
        
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
    
    def test_message_to_dict(self):
        """Test message serialization."""
        msg = AgentMessage(role="assistant", content="Response")
        data = msg.to_dict()
        
        assert data["role"] == "assistant"
        assert data["content"] == "Response"
        assert "timestamp" in data


class TestAgentLoader:
    """Tests for AgentLoader."""
    
    def test_parse_agents_md(self):
        """Test parsing AGENTS.md content."""
        content = """# Agents

## Aria
    - model: qwen3-mlx
- role: coordinator
    - skills: [ollama, database]

## Researcher
    - model: chimera-free
- parent: aria
- role: researcher
- capabilities: [search, summarize]
"""
        
        agents = AgentLoader.parse_agents_md(content)
        
        assert "aria" in agents
        assert "researcher" in agents
        assert agents["researcher"].parent == "aria"
        assert agents["aria"].model == "qwen3-mlx"
    
    def test_get_agent_hierarchy(self):
        """Test building agent hierarchy."""
        agents = {
            "aria": AgentConfig(
                id="aria",
                name="Aria",
                role=AgentRole.COORDINATOR,
                model="qwen3-mlx",
            ),
            "researcher": AgentConfig(
                id="researcher",
                name="Researcher",
                role=AgentRole.RESEARCHER,
                model="chimera-free",
                parent="aria",
            ),
            "coder": AgentConfig(
                id="coder",
                name="Coder",
                role=AgentRole.CODER,
                model="qwen3-coder-free",
                parent="aria",
            ),
        }
        
        hierarchy = AgentLoader.get_agent_hierarchy(agents)
        
        assert "aria" in hierarchy
        assert "researcher" in hierarchy["aria"]
        assert "coder" in hierarchy["aria"]


class TestLLMAgent:
    """Tests for LLMAgent."""
    
    @pytest.mark.asyncio
    async def test_process_without_llm(self, mock_agent_config):
        """Test processing without LLM skill."""
        agent = LLMAgent(mock_agent_config)
        
        response = await agent.process("Hello")
        
        assert response.role == "assistant"
        assert "[LLM not available]" in response.content
    
    @pytest.mark.asyncio
    async def test_process_with_llm(self, mock_agent_config, mock_llm_skill, skill_registry):
        """Test processing with LLM skill."""
        skill_registry._skills["moonshot"] = mock_llm_skill
        
        agent = LLMAgent(mock_agent_config, skill_registry)
        response = await agent.process("Hello")
        
        assert response.role == "assistant"
        assert "Test chat response" in response.content
        assert response.agent_id == "test_agent"
    
    def test_context_management(self, mock_agent_config):
        """Test agent context management."""
        agent = LLMAgent(mock_agent_config)
        
        msg1 = AgentMessage(role="user", content="First")
        msg2 = AgentMessage(role="assistant", content="Second")
        
        agent.add_to_context(msg1)
        agent.add_to_context(msg2)
        
        context = agent.get_context()
        assert len(context) == 2
        
        agent.clear_context()
        assert len(agent.get_context()) == 0
    
    def test_system_prompt_generation(self, mock_agent_config):
        """Test system prompt generation."""
        agent = LLMAgent(mock_agent_config)
        prompt = agent.get_system_prompt()
        
        assert "Test Agent" in prompt
        assert "coordinator" in prompt.lower()


class TestAgentCoordinator:
    """Tests for AgentCoordinator."""
    
    @pytest.mark.asyncio
    async def test_load_from_file(self, aria_mind_path):
        """Test loading agents from file."""
        coordinator = AgentCoordinator()
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        
        assert "aria" in coordinator._configs
        assert coordinator._main_agent_id == "aria"
    
    @pytest.mark.asyncio
    async def test_initialize_agents(self, aria_mind_path):
        """Test initializing agents."""
        coordinator = AgentCoordinator()
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()
        
        assert "aria" in coordinator.list_agents()
        assert coordinator.get_main_agent() is not None
    
    @pytest.mark.asyncio
    async def test_process_message(self, aria_mind_path, skill_registry, mock_llm_skill):
        """Test processing a message."""
        skill_registry._skills["moonshot"] = mock_llm_skill
        
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()
        
        response = await coordinator.process("Hello Aria")
        
        assert response.role == "assistant"
    
    def test_get_status(self):
        """Test coordinator status."""
        coordinator = AgentCoordinator()
        status = coordinator.get_status()
        
        assert "agents" in status
        assert "main_agent" in status
        assert "skill_registry" in status


class TestAgentDelegation:
    """Tests for agent delegation."""
    
    @pytest.mark.asyncio
    async def test_add_sub_agent(self, mock_agent_config):
        """Test adding sub-agents."""
        parent = LLMAgent(mock_agent_config)
        
        child_config = AgentConfig(
            id="child",
            name="Child",
            role=AgentRole.RESEARCHER,
            model="qwen3-mlx",
            parent="test_agent",
        )
        child = LLMAgent(child_config)
        
        parent.add_sub_agent(child)
        
        assert parent.get_sub_agent("child") is child
        assert parent.get_sub_agent("nonexistent") is None
    
    @pytest.mark.asyncio
    async def test_delegate_to_sub_agent(self, mock_agent_config):
        """Test delegating to sub-agent."""
        parent = LLMAgent(mock_agent_config)
        
        child_config = AgentConfig(
            id="child",
            name="Child",
            role=AgentRole.RESEARCHER,
            model="qwen3-mlx",
        )
        child = LLMAgent(child_config)
        parent.add_sub_agent(child)
        
        response = await parent.delegate("child", "Research this topic")
        
        assert response.role == "assistant"
    
    @pytest.mark.asyncio
    async def test_delegate_unknown_agent(self, mock_agent_config):
        """Test delegating to unknown agent raises error."""
        agent = LLMAgent(mock_agent_config)
        
        with pytest.raises(ValueError, match="not found"):
            await agent.delegate("unknown", "Message")


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_context_defaults(self):
        ctx = AgentContext(task="test task")
        assert ctx.format == "text"
        assert ctx.agent_id == ""
        assert ctx.parent_id is None
        assert ctx.deadline is None
        assert ctx.constraints == []
        assert ctx.examples == []

    def test_context_validate_valid(self):
        ctx = AgentContext(task="do something")
        assert ctx.validate() is True

    def test_context_validate_empty_task(self):
        ctx = AgentContext(task="")
        assert ctx.validate() is False

    def test_context_validate_whitespace_task(self):
        ctx = AgentContext(task="   ")
        assert ctx.validate() is False

    def test_context_full(self):
        from datetime import datetime, timezone
        ctx = AgentContext(
            task="analyze data",
            context={"source": "api"},
            constraints=["max 100 tokens"],
            examples=["example1"],
            format="json",
            agent_id="analyst",
            parent_id="aria",
            deadline=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        assert ctx.agent_id == "analyst"
        assert len(ctx.constraints) == 1


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_result_defaults(self):
        result = AgentResult(agent_id="test", success=True, output="done")
        assert result.duration_ms == 0
        assert result.token_cost == 0.0
        assert result.timestamp is not None

    def test_result_with_metadata(self):
        result = AgentResult(
            agent_id="analyst",
            success=False,
            output="failed",
            duration_ms=500,
            token_cost=0.001,
            metadata={"error": "timeout"},
        )
        assert result.metadata["error"] == "timeout"


class TestPheromoneScoring:
    """Tests for pheromone scoring."""

    def test_cold_start(self):
        from aria_agents.scoring import compute_pheromone
        assert compute_pheromone([]) == 0.5

    def test_perfect_score(self):
        from datetime import datetime, timezone
        from aria_agents.scoring import compute_pheromone
        records = [{
            "success": True,
            "speed_score": 1.0,
            "cost_score": 1.0,
            "created_at": datetime.now(timezone.utc),
        }]
        score = compute_pheromone(records)
        assert 0.9 < score <= 1.0

    def test_failure_score(self):
        from datetime import datetime, timezone
        from aria_agents.scoring import compute_pheromone
        records = [{
            "success": False,
            "speed_score": 0.5,
            "cost_score": 0.5,
            "created_at": datetime.now(timezone.utc),
        }]
        score = compute_pheromone(records)
        assert score < 0.5  # Worse than cold start

    def test_decay_reduces_old_records(self):
        from datetime import datetime, timezone, timedelta
        from aria_agents.scoring import compute_pheromone
        old_record = [{
            "success": True,
            "speed_score": 1.0,
            "cost_score": 1.0,
            "created_at": datetime.now(timezone.utc) - timedelta(days=30),
        }]
        new_record = [{
            "success": True,
            "speed_score": 1.0,
            "cost_score": 1.0,
            "created_at": datetime.now(timezone.utc),
        }]
        old_score = compute_pheromone(old_record)
        new_score = compute_pheromone(new_record)
        # Single records always normalize (decay cancels in weight)
        assert old_score == new_score

    def test_select_best_agent(self):
        from aria_agents.scoring import select_best_agent
        candidates = ["agent_a", "agent_b", "agent_c"]
        scores = {"agent_a": 0.3, "agent_b": 0.9, "agent_c": 0.5}
        assert select_best_agent(candidates, scores) == "agent_b"

    def test_select_best_agent_cold_start(self):
        from aria_agents.scoring import select_best_agent, COLD_START_SCORE
        candidates = ["new_agent", "tested"]
        scores = {"tested": 0.3}  # new_agent not in scores -> cold start 0.5
        assert select_best_agent(candidates, scores) == "new_agent"

    def test_select_no_candidates_raises(self):
        from aria_agents.scoring import select_best_agent
        with pytest.raises(ValueError):
            select_best_agent([], {})


class TestMaxConcurrent:
    """Tests for max concurrent agents constant."""

    def test_max_concurrent_value(self):
        assert MAX_CONCURRENT_AGENTS == 5


class TestExplorerWorkerValidator:
    """Tests for E/W/V cycle."""

    @pytest.mark.asyncio
    async def test_explore_returns_approaches(self, aria_mind_path, skill_registry, mock_llm_skill):
        skill_registry._skills["moonshot"] = mock_llm_skill
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()

        ctx = AgentContext(task="Build a dashboard", agent_id="aria")
        approaches = await coordinator.explore(ctx)
        assert isinstance(approaches, list)
        assert len(approaches) >= 1  # At least one approach

    @pytest.mark.asyncio
    async def test_work_returns_result(self, aria_mind_path, skill_registry, mock_llm_skill):
        skill_registry._skills["moonshot"] = mock_llm_skill
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()

        ctx = AgentContext(task="Implement dashboard", agent_id="aria")
        result = await coordinator.work(ctx, "Use React components")
        assert isinstance(result, AgentResult)
        assert result.agent_id != ""

    @pytest.mark.asyncio
    async def test_validate_returns_result(self, aria_mind_path, skill_registry, mock_llm_skill):
        skill_registry._skills["moonshot"] = mock_llm_skill
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()

        ctx = AgentContext(task="Validate output", constraints=["must be JSON"])
        work_result = AgentResult(agent_id="aria", success=True, output='{"key": "val"}')
        val_result = await coordinator.validate(ctx, work_result)
        assert isinstance(val_result, AgentResult)


class TestSpawnParallel:
    """Tests for parallel task spawning."""

    @pytest.mark.asyncio
    async def test_spawn_parallel_basic(self, aria_mind_path, skill_registry, mock_llm_skill):
        skill_registry._skills["moonshot"] = mock_llm_skill
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()

        tasks = [
            AgentContext(task="Task 1", agent_id="aria"),
            AgentContext(task="Task 2", agent_id="aria"),
        ]
        results = await coordinator.spawn_parallel(tasks)
        assert len(results) == 2
        assert all(isinstance(r, AgentResult) for r in results)

    @pytest.mark.asyncio
    async def test_spawn_parallel_empty(self, aria_mind_path, skill_registry, mock_llm_skill):
        skill_registry._skills["moonshot"] = mock_llm_skill
        coordinator = AgentCoordinator(skill_registry)
        await coordinator.load_from_file(f"{aria_mind_path}/AGENTS.md")
        await coordinator.initialize_agents()

        results = await coordinator.spawn_parallel([])
        assert results == []
