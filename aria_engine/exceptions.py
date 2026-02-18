"""Engine-specific exceptions."""


class EngineError(Exception):
    """Base exception for aria_engine."""
    pass


class LLMError(EngineError):
    """LLM gateway errors (model unavailable, timeout, etc.)."""
    pass


class SessionError(EngineError):
    """Session management errors."""
    pass


class SchedulerError(EngineError):
    """Scheduler errors (job execution, scheduling)."""
    pass


class AgentError(EngineError):
    """Agent pool errors (spawn, terminate, routing)."""
    pass


class ContextError(EngineError):
    """Context assembly errors."""
    pass


class ToolError(EngineError):
    """Tool calling errors."""
    pass
