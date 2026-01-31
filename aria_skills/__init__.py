# aria_skills/__init__.py
"""
Aria Skills - API-safe skill interfaces

Skills are modular capabilities that Aria can use to interact
with external systems (APIs, databases, services).

Each skill:
- Has a clear interface
- Handles its own authentication
- Implements rate limiting
- Provides health checks
- Logs all operations

Usage:
    from aria_skills import SkillRegistry
    
    registry = SkillRegistry()
    await registry.load_from_config("aria_mind/TOOLS.md")
    
    moltbook = registry.get("moltbook")
    await moltbook.post_status("Hello world!")
"""

__version__ = "1.0.0"

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

# Import skill implementations to register them
from aria_skills.moltbook import MoltbookSkill
from aria_skills.database import DatabaseSkill
from aria_skills.llm import GeminiSkill, MoonshotSkill, OllamaSkill
from aria_skills.health import HealthMonitorSkill
from aria_skills.goals import GoalSchedulerSkill, Goal, ScheduledTask, TaskPriority, TaskStatus
from aria_skills.knowledge_graph import KnowledgeGraphSkill

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillConfig",
    "SkillResult",
    "SkillStatus",
    "SkillRegistry",
    # Skills
    "MoltbookSkill",
    "DatabaseSkill",
    "OllamaSkill",  # Default LLM (local)
    "GeminiSkill",
    "MoonshotSkill",
    "KnowledgeGraphSkill",
    "HealthMonitorSkill",
    "GoalSchedulerSkill",
    # Goal types
    "Goal",
    "ScheduledTask",
    "TaskPriority",
    "TaskStatus",
]
