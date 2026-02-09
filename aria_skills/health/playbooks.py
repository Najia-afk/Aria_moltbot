# aria_skills/health/playbooks.py
"""
Recovery playbooks for Aria's self-healing system.

Each playbook defines a named recovery procedure with trigger conditions,
ordered steps, cooldown, and retry limits.

Part of Aria's self-healing system (TICKET-36).
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Playbook:
    """A recovery playbook that maps a failure pattern to corrective actions."""
    name: str
    description: str
    trigger_condition: str  # pattern string matched against signal component+metric
    steps: list[dict[str, Any]] = field(default_factory=list)
    cooldown_seconds: int = 300  # 5 minutes default
    max_retries: int = 3
    severity_filter: Optional[list[str]] = None  # e.g. ["error", "critical"]

    def matches(self, component: str, metric: str, severity: str) -> bool:
        """Check if this playbook's trigger matches the given signal."""
        signal_key = f"{component}.{metric}"
        pattern_match = self.trigger_condition in signal_key or signal_key in self.trigger_condition
        if self.severity_filter:
            return pattern_match and severity in self.severity_filter
        return pattern_match


# ── Built-in Recovery Playbooks ──────────────────────────────────────────

RESTART_SERVICE = Playbook(
    name="restart_service",
    description="Restart a failing Docker service via docker compose.",
    trigger_condition="service.unresponsive",
    steps=[
        {"action": "log", "message": "Service unresponsive — initiating restart"},
        {"action": "shell", "command": "docker compose restart {component}"},
        {"action": "wait", "seconds": 10},
        {"action": "health_check", "target": "{component}"},
        {"action": "log", "message": "Service restart complete for {component}"},
    ],
    cooldown_seconds=300,
    max_retries=3,
    severity_filter=["error", "critical"],
)

CLEAR_CACHE = Playbook(
    name="clear_cache",
    description="Clear stale cache and working memory entries.",
    trigger_condition="memory.cache_stale",
    steps=[
        {"action": "log", "message": "Cache staleness detected — clearing"},
        {"action": "api_call", "endpoint": "/cache/clear", "method": "POST"},
        {"action": "log", "message": "Cache cleared successfully"},
    ],
    cooldown_seconds=120,
    max_retries=5,
    severity_filter=["warning", "error"],
)

REDUCE_LOAD = Playbook(
    name="reduce_load",
    description="Scale back scheduled tasks when system is overloaded.",
    trigger_condition="system.cpu_high",
    steps=[
        {"action": "log", "message": "High CPU load detected — reducing scheduled tasks"},
        {"action": "config_update", "key": "scheduler.max_concurrent", "value": 1},
        {"action": "api_call", "endpoint": "/scheduler/pause-non-critical", "method": "POST"},
        {"action": "wait", "seconds": 60},
        {"action": "health_check", "target": "system"},
        {"action": "log", "message": "Load reduction applied"},
    ],
    cooldown_seconds=600,
    max_retries=2,
    severity_filter=["warning", "error", "critical"],
)

MODEL_FALLBACK = Playbook(
    name="model_fallback",
    description="Switch to backup LLM model when primary is unavailable.",
    trigger_condition="llm.model_error",
    steps=[
        {"action": "log", "message": "Primary model failing — switching to fallback"},
        {"action": "api_call", "endpoint": "/models/fallback", "method": "POST"},
        {"action": "wait", "seconds": 5},
        {"action": "health_check", "target": "llm"},
        {"action": "log", "message": "Model fallback activated"},
    ],
    cooldown_seconds=180,
    max_retries=2,
    severity_filter=["error", "critical"],
)

DATABASE_RECOVERY = Playbook(
    name="database_recovery",
    description="Reconnect and vacuum the database when connection issues arise.",
    trigger_condition="database.connection_error",
    steps=[
        {"action": "log", "message": "Database connection issue — attempting recovery"},
        {"action": "api_call", "endpoint": "/database/reconnect", "method": "POST"},
        {"action": "wait", "seconds": 5},
        {"action": "health_check", "target": "database"},
        {"action": "shell", "command": "docker exec aria-db psql -U aria -c 'VACUUM ANALYZE;'"},
        {"action": "log", "message": "Database recovery complete"},
    ],
    cooldown_seconds=300,
    max_retries=3,
    severity_filter=["error", "critical"],
)

# All built-in playbooks
ALL_PLAYBOOKS: list[Playbook] = [
    RESTART_SERVICE,
    CLEAR_CACHE,
    REDUCE_LOAD,
    MODEL_FALLBACK,
    DATABASE_RECOVERY,
]
