"""Base agent classes and role definitions.

Defines AgentRole enum and BaseAgent class for all Aria sub-agents.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentRole(Enum):
    """Agent role types mapping to Focus personas."""
    COORDINATOR = "coordinator"
    DEVSECOPS = "devsecops"
    DATA = "data"
    TRADER = "trader"
    CREATIVE = "creative"
    SOCIAL = "social"
    JOURNALIST = "journalist"
    MEMORY = "memory"


class FocusType(Enum):
    """Focus type personas - aliases for AgentRole.
    
    These map 1:1 with AgentRole for semantic clarity in different contexts.
    """
    ORCHESTRATOR = "coordinator"
    DEVSECOPS = "devsecops"
    DATA = "data"
    TRADER = "trader"
    CREATIVE = "creative"
    SOCIAL = "social"
    JOURNALIST = "journalist"
    MEMORY = "memory"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    id: str
    focus: str
    model: str
    fallback: str | None = None
    skills: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    timeout: int = 600
    parent: str | None = None
    rate_limit: dict | None = None


@dataclass  
class AgentResult:
    """Result from an agent invocation."""
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: int = 0
    tokens_used: int = 0
    agent_id: str = ""


class BaseAgent(ABC):
    """Abstract base class for all Aria agents.
    
    All specialized agents must inherit from this class and implement
    the execute method.
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize agent with configuration.
        
        Args:
            config: AgentConfig with id, focus, model, etc.
        """
        self.config = config
        self.id = config.id
        self.focus = config.focus
        self.skills = set(config.skills)
        self.capabilities = set(config.capabilities)
    
    @abstractmethod
    def execute(self, task: dict) -> AgentResult:
        """Execute a task and return results.
        
        Args:
            task: Dict with task parameters including:
                - type: task type identifier
                - params: task-specific parameters
                - context: optional context data
                
        Returns:
            AgentResult with success status and data
        """
        pass
    
    def can_handle(self, task_type: str) -> bool:
        """Check if this agent can handle a task type.
        
        Args:
            task_type: Type of task to check
            
        Returns:
            True if agent has capability for this task
        """
        return task_type in self.capabilities
    
    def to_dict(self) -> dict:
        """Serialize agent config to dict."""
        return {
            "id": self.id,
            "focus": self.focus,
            "model": self.config.model,
            "skills": list(self.skills),
            "capabilities": list(self.capabilities),
            "timeout": self.config.timeout
        }
