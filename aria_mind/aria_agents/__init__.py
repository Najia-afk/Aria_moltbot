"""Aria Agents — Agent-Managing-Agent System.

Autonomous agent swarm that delegates, monitors, and optimizes itself.
"""
from .base import AgentConfig, AgentResult, AgentRole, BaseAgent
from .coordinator import AgentCoordinator, coordinator
from .scoring import (
    COLD_START_SCORE,
    PerformanceRecord,
    PerformanceTracker,
    compute_pheromone,
    default_tracker,
    select_best_agent,
)
from .agents import (
    AnalystAgent,
    AriaTalkAgent,
    CreatorAgent,
    DevOpsAgent,
    MemoryAgent,
    OpenClawAgent,
    create_all_agents,
)

__all__ = [
    # Base
    "AgentConfig",
    "AgentResult", 
    "AgentRole",
    "BaseAgent",
    # Coordinator
    "AgentCoordinator",
    "coordinator",
    # Scoring
    "COLD_START_SCORE",
    "PerformanceRecord",
    "PerformanceTracker",
    "compute_pheromone",
    "default_tracker",
    "select_best_agent",
    # Agents
    "AnalystAgent",
    "AriaTalkAgent",
    "CreatorAgent",
    "DevOpsAgent",
    "MemoryAgent",
    "OpenClawAgent",
    "create_all_agents",
]

__version__ = "0.2.0"
