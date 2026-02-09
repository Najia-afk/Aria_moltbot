# aria_agents/base.py
"""
Base agent classes.

Defines the interface for all agents in the system.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_skills import SkillRegistry
    from aria_agents.coordinator import AgentCoordinator


class AgentRole(Enum):
    """Agent role types."""
    COORDINATOR = "coordinator"  # Main orchestrator
    RESEARCHER = "researcher"    # Information gathering
    SOCIAL = "social"            # Social media interaction
    CODER = "coder"              # Code generation/review
    MEMORY = "memory"            # Memory management


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    id: str
    name: str
    role: AgentRole
    model: str
    parent: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """A message in the agent system."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    agent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """
    Base class for all agents.
    
    Agents can:
    - Process messages and generate responses
    - Use skills from the skill registry
    - Delegate to sub-agents
    - Maintain conversation context
    """
    
    def __init__(
        self, 
        config: AgentConfig, 
        skill_registry: Optional["SkillRegistry"] = None,
        coordinator: Optional["AgentCoordinator"] = None
    ):
        self.config = config
        self._skill_registry = skill_registry
        self._coordinator = coordinator  # For peer consultation
        self._context: List[AgentMessage] = []
        self._sub_agents: Dict[str, "BaseAgent"] = {}
        self.logger = logging.getLogger(f"aria.agent.{config.id}")
    
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def role(self) -> AgentRole:
        return self.config.role
    
    def set_skill_registry(self, registry: "SkillRegistry") -> None:
        """Inject skill registry."""
        self._skill_registry = registry
    
    def add_sub_agent(self, agent: "BaseAgent") -> None:
        """Add a sub-agent."""
        self._sub_agents[agent.id] = agent
    
    def get_sub_agent(self, agent_id: str) -> Optional["BaseAgent"]:
        """Get a sub-agent by ID."""
        return self._sub_agents.get(agent_id)
    
    def clear_context(self) -> None:
        """Clear conversation context."""
        self._context = []
    
    def add_to_context(self, message: AgentMessage) -> None:
        """Add a message to context."""
        self._context.append(message)
    
    def get_context(self, limit: Optional[int] = None) -> List[AgentMessage]:
        """Get recent context messages."""
        if limit:
            return self._context[-limit:]
        return self._context.copy()
    
    @abstractmethod
    async def process(self, message: str, **kwargs) -> AgentMessage:
        """
        Process an incoming message and generate a response.
        
        Args:
            message: The input message
            **kwargs: Additional parameters
            
        Returns:
            AgentMessage with the response
        """
        pass
    
    async def use_skill(self, skill_name: str, method: str, **kwargs) -> Any:
        """
        Use a skill from the registry.
        
        Args:
            skill_name: Name of the skill
            method: Method to call on the skill
            **kwargs: Arguments to pass to the method
            
        Returns:
            Result from the skill method
        """
        if not self._skill_registry:
            raise RuntimeError("No skill registry available")
        
        skill = self._skill_registry.get(skill_name)
        if not skill:
            raise ValueError(f"Skill {skill_name} not found")
        
        if skill_name not in self.config.skills:
            self.logger.warning(f"Agent {self.id} using skill {skill_name} not in its allowed skills")
        
        method_fn = getattr(skill, method, None)
        if not method_fn:
            raise ValueError(f"Method {method} not found on skill {skill_name}")
        
        return await method_fn(**kwargs)
    
    async def delegate(self, agent_id: str, message: str, **kwargs) -> AgentMessage:
        """
        Delegate to a sub-agent.
        
        Args:
            agent_id: ID of the sub-agent
            message: Message to send
            **kwargs: Additional parameters
            
        Returns:
            Response from the sub-agent
        """
        sub_agent = self._sub_agents.get(agent_id)
        if not sub_agent:
            raise ValueError(f"Sub-agent {agent_id} not found")
        
        self.logger.debug(f"Delegating to {agent_id}: {message[:50]}...")
        return await sub_agent.process(message, **kwargs)
    
    async def consult(self, agent_id: str, question: str, **kwargs) -> AgentMessage:
        """
        Consult another agent (peer or any agent in system).
        
        Routes through coordinator for proper access - enables cross-focus
        collaboration without strict parent-child hierarchy.
        
        Args:
            agent_id: ID of the agent to consult
            question: The question/topic to get their perspective on
            **kwargs: Additional parameters
            
        Returns:
            Response from the consulted agent
        """
        if not self._coordinator:
            raise RuntimeError("No coordinator available for peer consultation")
        
        # Add context about who's asking for proper attribution
        context_question = f"[Consultation from {self.name} ({self.config.role.value})]: {question}"
        self.logger.debug(f"Consulting {agent_id}: {question[:50]}...")
        return await self._coordinator.process(context_question, agent_id=agent_id, **kwargs)
    
    def get_system_prompt(self) -> str:
        """Build the system prompt for this agent."""
        if self.config.system_prompt:
            return self.config.system_prompt
        
        # Default system prompt based on role
        prompts = {
            AgentRole.COORDINATOR: (
                f"You are {self.name}, the main coordinator. "
                "Analyze requests and delegate to appropriate sub-agents. "
                "Synthesize responses from sub-agents into coherent answers."
            ),
            AgentRole.RESEARCHER: (
                f"You are {self.name}, a research specialist. "
                "Find accurate information, cite sources, and verify facts."
            ),
            AgentRole.SOCIAL: (
                f"You are {self.name}, a social media specialist. "
                "Create engaging content, manage interactions, and maintain brand voice."
            ),
            AgentRole.CODER: (
                f"You are {self.name}, a coding specialist. "
                "Write clean code, review for issues, and explain technical concepts."
            ),
            AgentRole.MEMORY: (
                f"You are {self.name}, a memory specialist. "
                "Store important information, recall relevant context, and manage knowledge."
            ),
        }
        return prompts.get(self.role, f"You are {self.name}.")
