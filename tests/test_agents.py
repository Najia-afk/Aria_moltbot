# tests/test_agents.py
"""
Tests for aria_agents package.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from aria_agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from aria_agents.loader import AgentLoader
from aria_agents.coordinator import AgentCoordinator, LLMAgent


class TestAgentConfig:
    """Tests for AgentConfig."""
    
    def test_config_defaults(self):
        """Test config with default values."""
        config = AgentConfig(
            id="test",
            name="Test Agent",
            role=AgentRole.COORDINATOR,
            model="gemini-pro",
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
            model="gemini-pro",
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
- model: gemini-pro
- role: coordinator
- skills: [gemini, database]

## Researcher
- model: gemini-pro
- parent: aria
- role: researcher
- capabilities: [search, summarize]
"""
        
        agents = AgentLoader.parse_agents_md(content)
        
        assert "aria" in agents
        assert "researcher" in agents
        assert agents["researcher"].parent == "aria"
        assert agents["aria"].model == "gemini-pro"
    
    def test_get_agent_hierarchy(self):
        """Test building agent hierarchy."""
        agents = {
            "aria": AgentConfig(
                id="aria",
                name="Aria",
                role=AgentRole.COORDINATOR,
                model="gemini-pro",
            ),
            "researcher": AgentConfig(
                id="researcher",
                name="Researcher",
                role=AgentRole.RESEARCHER,
                model="gemini-pro",
                parent="aria",
            ),
            "coder": AgentConfig(
                id="coder",
                name="Coder",
                role=AgentRole.CODER,
                model="gemini-pro",
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
        skill_registry._skills["gemini"] = mock_llm_skill
        
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
        skill_registry._skills["gemini"] = mock_llm_skill
        
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
            model="gemini-pro",
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
            model="gemini-pro",
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
