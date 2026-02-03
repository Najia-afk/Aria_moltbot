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

__version__ = "1.1.0"

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

# Import skill implementations to register them
from aria_skills.moltbook import MoltbookSkill
from aria_skills.database import DatabaseSkill
from aria_skills.llm import MoonshotSkill, OllamaSkill
from aria_skills.health import HealthMonitorSkill
from aria_skills.goals import GoalSchedulerSkill, Goal, ScheduledTask, TaskPriority, TaskStatus
from aria_skills.knowledge_graph import KnowledgeGraphSkill
from aria_skills.pytest_runner import PytestSkill

# New skill implementations (v1.1.0)
from aria_skills.performance import PerformanceSkill
from aria_skills.social import SocialSkill
from aria_skills.hourly_goals import HourlyGoalsSkill
from aria_skills.litellm_skill import LiteLLMSkill
from aria_skills.schedule import ScheduleSkill

# Focus-specific skills (v1.2.0)
from aria_skills.security_scan import SecurityScanSkill
from aria_skills.ci_cd import CICDSkill
from aria_skills.data_pipeline import DataPipelineSkill
from aria_skills.experiment import ExperimentSkill
from aria_skills.market_data import MarketDataSkill
from aria_skills.portfolio import PortfolioSkill
from aria_skills.brainstorm import BrainstormSkill
from aria_skills.research import ResearchSkill
from aria_skills.fact_check import FactCheckSkill
from aria_skills.community import CommunitySkill

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillConfig",
    "SkillResult",
    "SkillStatus",
    "SkillRegistry",
    # Core Skills
    "MoltbookSkill",
    "DatabaseSkill",
    "OllamaSkill",  # Default LLM (local)
    "MoonshotSkill",
    "KnowledgeGraphSkill",
    "HealthMonitorSkill",
    "GoalSchedulerSkill",
    "PytestSkill",
    # New Skills (v1.1.0)
    "PerformanceSkill",
    "SocialSkill",
    "HourlyGoalsSkill",
    "LiteLLMSkill",
    "ScheduleSkill",
    # Focus-Specific Skills (v1.2.0)
    "SecurityScanSkill",      # DevSecOps
    "CICDSkill",              # DevSecOps
    "DataPipelineSkill",      # Data Architect
    "ExperimentSkill",        # Data Architect
    "MarketDataSkill",        # Crypto Trader
    "PortfolioSkill",         # Crypto Trader
    "BrainstormSkill",        # Creative
    "ResearchSkill",          # Journalist
    "FactCheckSkill",         # Journalist
    "CommunitySkill",         # Social Architect
    # Goal types
    "Goal",
    "ScheduledTask",
    "TaskPriority",
    "TaskStatus",
]
