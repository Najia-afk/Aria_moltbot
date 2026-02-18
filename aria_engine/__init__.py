"""
Aria Engine — Standalone Python runtime for Aria Blue.

Replaces OpenClaw with native:
- LLM gateway (direct litellm SDK)
- Chat engine (session lifecycle + streaming)
- Scheduler (APScheduler + PostgreSQL)
- Agent pool (async task management)
- Context manager (sliding window + importance)
"""

__version__ = "2.0.0"

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError, LLMError, SessionError, SchedulerError

__all__ = ["EngineConfig", "EngineError", "LLMError", "SessionError", "SchedulerError"]
