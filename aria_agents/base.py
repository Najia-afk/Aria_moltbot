# aria_agents/base.py
"""
Base agent classes.

Defines the interface for all agents in the system.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_skills import SkillRegistry
    from aria_agents.coordinator import AgentCoordinator


class AgentRole(str, Enum):
    """Agent role types — aligned with FocusType."""
    COORDINATOR = "coordinator"  # Main orchestrator
    DEVSECOPS = "devsecops"      # Security + CI/CD
    DATA = "data"                # Data analysis + MLOps
    TRADER = "trader"            # Market analysis + portfolio
    CREATIVE = "creative"        # Content creation
    SOCIAL = "social"            # Social media + community
    JOURNALIST = "journalist"    # Research + investigation
    MEMORY = "memory"            # Memory management (support role)
    RESEARCHER = "researcher"    # Research + analysis
    CODER = "coder"              # Code generation + review


ROLE_TO_FOCUS_MAP = {
    "coordinator": "orchestrator",
    "devsecops": "devsecops",
    "data": "data",
    "trader": "trader",
    "creative": "creative",
    "social": "social",
    "journalist": "journalist",
    "memory": "orchestrator",
}


# Default mind files loaded for each agent role.
# Orchestrator/main agents load everything; sub-agents load a lighter set.
DEFAULT_MIND_FILES_FULL = [
    "IDENTITY.md", "SOUL.md", "SKILLS.md", "TOOLS.md", "MEMORY.md",
    "GOALS.md", "AGENTS.md", "SECURITY.md",
]
DEFAULT_MIND_FILES_LIGHT = [
    "IDENTITY.md", "SOUL.md", "TOOLS.md",
]

ROLE_DEFAULT_MIND_FILES: dict[str, list[str]] = {
    "coordinator": DEFAULT_MIND_FILES_FULL,
    "devsecops": ["IDENTITY.md", "SOUL.md", "TOOLS.md", "SECURITY.md"],
    "data": ["IDENTITY.md", "SOUL.md", "TOOLS.md", "MEMORY.md"],
    "trader": DEFAULT_MIND_FILES_LIGHT,
    "creative": ["IDENTITY.md", "SOUL.md", "TOOLS.md", "SKILLS.md"],
    "social": ["IDENTITY.md", "SOUL.md", "TOOLS.md", "SKILLS.md"],
    "journalist": ["IDENTITY.md", "SOUL.md", "TOOLS.md", "SECURITY.md"],
    "memory": ["IDENTITY.md", "SOUL.md", "MEMORY.md"],
    "researcher": DEFAULT_MIND_FILES_LIGHT,
    "coder": ["IDENTITY.md", "SOUL.md", "TOOLS.md", "SECURITY.md"],
}


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    id: str
    name: str
    role: AgentRole
    model: str
    parent: str | None = None
    capabilities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    mind_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_mind_files(self) -> list[str]:
        """Return mind files for this agent — explicit list or role-based default."""
        if self.mind_files:
            return self.mind_files
        return ROLE_DEFAULT_MIND_FILES.get(self.role.value, DEFAULT_MIND_FILES_LIGHT)


# Mandatory browser policy for all agents
BROWSER_POLICY = """
MANDATORY WEB ACCESS POLICY:
- Use ONLY the docker aria-browser (browserless/chrome) for all web access
- Browser endpoint: http://aria-browser:3000 (or localhost:3000 from host)
- Use browser(action="open|snapshot|navigate|act") exclusively
- NEVER use web_search (Brave API) - it is FORBIDDEN
- NEVER use web_fetch for browsing - use browser tool instead
- This policy is MANDATORY with NO EXCEPTIONS
"""


@dataclass
class AgentMessage:
    """A message in the agent system."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    agent_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
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
    - Consult peers via coordinator
    - Maintain sliding-window conversation context
    """
    
    # Context window limits — prevents token overflow
    _MAX_CONTEXT_MESSAGES = 50
    _SUMMARIZE_THRESHOLD = 40  # Summarize when context exceeds this
    
    def __init__(
        self, 
        config: AgentConfig, 
        skill_registry: "SkillRegistry" | None = None,
        coordinator: "AgentCoordinator" | None = None
    ):
        self.config = config
        self._skill_registry = skill_registry
        self._coordinator = coordinator  # For peer consultation
        self._context: list[AgentMessage] = []
        self._sub_agents: dict[str, "BaseAgent"] = {}
        self._total_messages_processed = 0
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
    
    def get_sub_agent(self, agent_id: str) -> "BaseAgent" | None:
        """Get a sub-agent by ID."""
        return self._sub_agents.get(agent_id)
    
    def clear_context(self) -> None:
        """Clear conversation context."""
        self._context = []
    
    def add_to_context(self, message: AgentMessage) -> None:
        """Add a message to context with sliding window management."""
        self._context.append(message)
        self._total_messages_processed += 1
        
        # Sliding window: when context gets too large, trim older messages
        # Keep system messages + most recent messages
        if len(self._context) > self._MAX_CONTEXT_MESSAGES:
            # Preserve any system messages at the start
            system_msgs = [m for m in self._context[:5] if m.role == "system"]
            # Keep last N messages
            recent = self._context[-(self._MAX_CONTEXT_MESSAGES - len(system_msgs)):]
            self._context = system_msgs + recent
            self.logger.debug(
                f"Context trimmed to {len(self._context)} messages "
                f"(total processed: {self._total_messages_processed})"
            )
    
    def get_context(self, limit: int | None = None) -> list[AgentMessage]:
        """Get recent context messages."""
        if limit:
            return self._context[-limit:]
        return self._context.copy()
    
    def get_context_summary(self) -> dict[str, Any]:
        """Get a summary of the current context state."""
        role_counts = {}
        for msg in self._context:
            role_counts[msg.role] = role_counts.get(msg.role, 0) + 1
        return {
            "messages": len(self._context),
            "max_capacity": self._MAX_CONTEXT_MESSAGES,
            "total_processed": self._total_messages_processed,
            "roles": role_counts,
        }
    
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
            AgentRole.DEVSECOPS: (
                f"You are {self.name}, a DevSecOps specialist. "
                "Handle security, CI/CD, code review, testing, and infrastructure."
            ),
            AgentRole.DATA: (
                f"You are {self.name}, a data analysis specialist. "
                "Perform data analysis, MLOps, experiment tracking, and metrics."
            ),
            AgentRole.TRADER: (
                f"You are {self.name}, a market analysis specialist. "
                "Analyze markets, manage portfolios, and track financial metrics."
            ),
            AgentRole.CREATIVE: (
                f"You are {self.name}, a creative content specialist. "
                "Generate compelling content, stories, and creative assets."
            ),
            AgentRole.SOCIAL: (
                f"You are {self.name}, a social media specialist. "
                "Create engaging content, manage interactions, and maintain brand voice."
            ),
            AgentRole.JOURNALIST: (
                f"You are {self.name}, a research and investigation specialist. "
                "Investigate topics, fact-check claims, and produce well-sourced reports."
            ),
            AgentRole.MEMORY: (
                f"You are {self.name}, a memory specialist. "
                "Store important information, recall relevant context, and manage knowledge."
            ),
        }
        return prompts.get(self.role, f"You are {self.name}.")
