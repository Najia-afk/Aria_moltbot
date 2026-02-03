# aria_agents/coordinator.py
"""
Agent coordinator.

Manages agent lifecycle and message routing.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from aria_agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from aria_agents.loader import AgentLoader

if TYPE_CHECKING:
    from aria_skills import SkillRegistry


class LLMAgent(BaseAgent):
    """
    Agent that uses an LLM skill for processing.
    
    Uses the configured model to generate responses.
    All models route through LiteLLM for unified access.
    """
    
    async def process(self, message: str, **kwargs) -> AgentMessage:
        """Process message using LLM."""
        # Add user message to context
        user_msg = AgentMessage(role="user", content=message)
        self.add_to_context(user_msg)
        
        # Get the right LLM skill based on model config
        # Priority: Local MLX > OpenRouter FREE > Kimi (paid)
        llm_skill = None
        if self._skill_registry:
            model_lower = self.config.model.lower()
            
            # Paid Moonshot/Kimi models - use moonshot skill directly
            if "moonshot" in model_lower or "kimi" in model_lower:
                llm_skill = self._skill_registry.get("moonshot")
            
            # Local models (MLX or Ollama)
            elif any(x in model_lower for x in ["mlx", "ollama", "qwen", "glm-local"]):
                llm_skill = self._skill_registry.get("ollama")
            
            # OpenRouter FREE models - route through LiteLLM
            # Includes: trinity-free, qwen3-coder-free, chimera-free, 
            # qwen3-next-free, glm-free, deepseek-free, nemotron-free, gpt-oss-free
            elif any(x in model_lower for x in ["free", "trinity", "chimera", "coder", "deepseek", "nemotron", "gpt-oss"]):
                llm_skill = self._skill_registry.get("ollama") or self._skill_registry.get("moonshot")
            
            else:
                # Default: try local first, then cloud
                llm_skill = self._skill_registry.get("ollama") or self._skill_registry.get("moonshot")
        
        if not llm_skill:
            self.logger.warning("No LLM skill available, returning placeholder")
            response = AgentMessage(
                role="assistant",
                content="[LLM not available]",
                agent_id=self.id,
            )
            self.add_to_context(response)
            return response
        
        # Build messages for LLM
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        for ctx_msg in self.get_context(limit=10):
            messages.append({
                "role": ctx_msg.role,
                "content": ctx_msg.content,
            })
        
        # Call LLM with error handling
        try:
            result = await llm_skill.chat(
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            
            if result.success:
                content = result.data.get("text", "")
            else:
                content = f"[Error: {result.error}]"
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            content = f"[LLM Error: {e}]"
        
        response = AgentMessage(
            role="assistant",
            content=content,
            agent_id=self.id,
        )
        self.add_to_context(response)
        return response


class AgentCoordinator:
    """
    Coordinates multiple agents.
    
    Handles:
    - Agent lifecycle (creation, initialization)
    - Message routing between agents
    - Skill registry injection
    """
    
    def __init__(self, skill_registry: Optional["SkillRegistry"] = None):
        self._skill_registry = skill_registry
        self._agents: Dict[str, BaseAgent] = {}
        self._configs: Dict[str, AgentConfig] = {}
        self._hierarchy: Dict[str, List[str]] = {}
        self._main_agent_id: Optional[str] = None
        self.logger = logging.getLogger("aria.coordinator")
    
    def set_skill_registry(self, registry: "SkillRegistry") -> None:
        """Inject skill registry."""
        self._skill_registry = registry
        # Update all existing agents
        for agent in self._agents.values():
            agent.set_skill_registry(registry)
    
    async def load_from_file(self, filepath: str) -> None:
        """
        Load agent configurations from AGENTS.md.
        
        Args:
            filepath: Path to AGENTS.md file
        """
        self._configs = AgentLoader.load_from_file(filepath)
        self._hierarchy = AgentLoader.get_agent_hierarchy(self._configs)
        
        # Find main agent (no parent)
        for agent_id, config in self._configs.items():
            if config.parent is None:
                self._main_agent_id = agent_id
                break
        
        self.logger.info(f"Loaded {len(self._configs)} agent configs, main: {self._main_agent_id}")
    
    async def initialize_agents(self) -> None:
        """Create and initialize all agents."""
        for agent_id, config in self._configs.items():
            agent = LLMAgent(config, self._skill_registry)
            self._agents[agent_id] = agent
            self.logger.debug(f"Created agent: {agent_id}")
        
        # Set up sub-agent relationships
        for parent_id, child_ids in self._hierarchy.items():
            parent = self._agents.get(parent_id)
            if parent:
                for child_id in child_ids:
                    child = self._agents.get(child_id)
                    if child:
                        parent.add_sub_agent(child)
                        self.logger.debug(f"Linked {child_id} -> {parent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_main_agent(self) -> Optional[BaseAgent]:
        """Get the main (root) agent."""
        if self._main_agent_id:
            return self._agents.get(self._main_agent_id)
        return None
    
    def list_agents(self) -> List[str]:
        """List all agent IDs."""
        return list(self._agents.keys())
    
    async def process(self, message: str, agent_id: Optional[str] = None, **kwargs) -> AgentMessage:
        """
        Process a message through an agent.
        
        Args:
            message: Input message
            agent_id: Target agent (defaults to main agent)
            **kwargs: Additional parameters
            
        Returns:
            Response from the agent
        """
        target_id = agent_id or self._main_agent_id
        
        if not target_id:
            return AgentMessage(
                role="system",
                content="No agents configured",
            )
        
        agent = self._agents.get(target_id)
        if not agent:
            return AgentMessage(
                role="system",
                content=f"Agent {target_id} not found",
            )
        
        return await agent.process(message, **kwargs)
    
    async def broadcast(self, message: str, **kwargs) -> Dict[str, AgentMessage]:
        """
        Send a message to all agents in parallel.
        
        Args:
            message: Message to broadcast
            **kwargs: Additional parameters
            
        Returns:
            Dict of agent_id -> response
        """
        async def _process_single(agent_id: str, agent: BaseAgent) -> tuple:
            try:
                response = await agent.process(message, **kwargs)
                return agent_id, response
            except Exception as e:
                self.logger.error(f"Agent {agent_id} failed: {e}")
                return agent_id, AgentMessage(
                    role="system",
                    content=f"Error: {e}",
                    agent_id=agent_id,
                )
        
        # Process all agents in parallel
        results = await asyncio.gather(*[
            _process_single(aid, a) for aid, a in self._agents.items()
        ])
        
        return dict(results)
    
    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status."""
        return {
            "agents": len(self._agents),
            "main_agent": self._main_agent_id,
            "hierarchy": self._hierarchy,
            "skill_registry": self._skill_registry is not None,
        }
