# aria_agents/context.py
"""
Agent context protocol — structured input/output for all agent invocations.

Every agent call should use AgentContext for structured input and
AgentResult for structured output. This enables performance tracking,
pheromone scoring, and reproducible agent behavior.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentContext:
    """Structured context for agent invocations (8-element protocol)."""
    task: str
    context: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    format: str = "text"
    agent_id: str = ""
    parent_id: str | None = None
    deadline: datetime | None = None

    def validate(self) -> bool:
        """Validate that required fields are present."""
        return bool(self.task.strip())


@dataclass
class AgentResult:
    """Structured result from an agent invocation."""
    agent_id: str
    success: bool
    output: str
    duration_ms: int = 0
    token_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
