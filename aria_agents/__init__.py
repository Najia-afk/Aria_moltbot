# aria_agents/__init__.py
"""
Aria Agents Package

Multi-agent orchestration system for Aria Blue.
Agents can delegate to sub-agents and use skills.
"""

from aria_agents.base import BaseAgent, AgentConfig, AgentMessage
from aria_agents.context import AgentContext, AgentResult
from aria_agents.coordinator import AgentCoordinator, MAX_CONCURRENT_AGENTS
from aria_agents.loader import AgentLoader

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentMessage",
    "AgentContext",
    "AgentResult",
    "AgentCoordinator",
    "AgentLoader",
    "MAX_CONCURRENT_AGENTS",
]
