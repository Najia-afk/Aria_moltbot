# aria_agents/__init__.py
"""
Aria Agents Package

Multi-agent orchestration system for Aria Blue.
Agents are defined in aria_mind/AGENTS.md and loaded dynamically
by AgentLoader — never hardcoded.
"""

from aria_agents.base import BaseAgent, AgentConfig, AgentMessage, AgentRole
from aria_agents.context import AgentContext, AgentResult
from aria_agents.coordinator import AgentCoordinator, MAX_CONCURRENT_AGENTS
from aria_agents.loader import AgentLoader

__all__ = [
    # Base
    "BaseAgent",
    "AgentConfig",
    "AgentMessage",
    "AgentRole",
    # Context
    "AgentContext",
    "AgentResult",
    # Coordinator
    "AgentCoordinator",
    "AgentLoader",
    "MAX_CONCURRENT_AGENTS",
]
