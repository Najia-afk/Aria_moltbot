# aria_skills/health/patterns.py
"""
Failure pattern tracking and learning.

Records recurring failures so Aria can learn from past incidents
and suggest preventive measures.

Part of Aria's self-healing system (TICKET-36).
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aria.health.patterns")


@dataclass
class FailureRecord:
    """A single recorded failure occurrence."""
    component: str
    error_type: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class FailurePatternStore:
    """
    Track recurring failure patterns for learning.

    Groups failures by (component, error_type) and surfaces
    patterns that recur beyond a threshold.
    """

    def __init__(self, max_records: int = 5000):
        self._records: list[FailureRecord] = []
        self._max_records = max_records
        # (component, error_type) → count for fast lookup
        self._counts: dict[tuple[str, str], int] = defaultdict(int)

    def record_failure(
        self,
        component: str,
        error_type: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record a failure occurrence."""
        record = FailureRecord(
            component=component,
            error_type=error_type,
            context=context or {},
        )
        self._records.append(record)
        self._counts[(component, error_type)] += 1

        # Evict oldest if at capacity
        if len(self._records) > self._max_records:
            evicted = self._records[0]
            self._records = self._records[1:]
            key = (evicted.component, evicted.error_type)
            self._counts[key] = max(0, self._counts[key] - 1)

        logger.debug(
            f"Recorded failure: {component}/{error_type} "
            f"(total: {self._counts[(component, error_type)]})"
        )

    def get_recurring_patterns(self, min_occurrences: int = 3) -> list[dict]:
        """
        Return failure patterns that recur at least min_occurrences times.

        Returns list of dicts with component, error_type, count, and
        sample contexts.
        """
        patterns = []
        for (component, error_type), count in self._counts.items():
            if count >= min_occurrences:
                # Gather recent contexts for this pattern
                matching = [
                    r for r in self._records
                    if r.component == component and r.error_type == error_type
                ]
                recent_contexts = [r.context for r in matching[-5:]]
                patterns.append({
                    "component": component,
                    "error_type": error_type,
                    "count": count,
                    "recent_contexts": recent_contexts,
                    "first_seen": matching[0].timestamp if matching else None,
                    "last_seen": matching[-1].timestamp if matching else None,
                })
        # Sort by count descending
        patterns.sort(key=lambda p: p["count"], reverse=True)
        return patterns

    def suggest_prevention(self, pattern: dict) -> str:
        """
        Suggest a preventive measure for a recurring failure pattern.

        Uses heuristics based on component type and error type
        to generate actionable advice.
        """
        component = pattern.get("component", "unknown")
        error_type = pattern.get("error_type", "unknown")
        count = pattern.get("count", 0)

        # Heuristic-based suggestions
        suggestions = {
            "database": {
                "connection_error": (
                    f"Database connection errors occurred {count} times. "
                    "Consider: increase connection pool size, add connection "
                    "health checks, or review network stability."
                ),
                "timeout": (
                    f"Database timeouts occurred {count} times. "
                    "Consider: optimize slow queries, increase timeout "
                    "limits, or add query caching."
                ),
                "default": (
                    f"Database component '{error_type}' failed {count} times. "
                    "Review database logs and consider adding monitoring alerts."
                ),
            },
            "llm": {
                "model_error": (
                    f"LLM model errors occurred {count} times. "
                    "Consider: configure model fallback chain, add request "
                    "queuing, or switch to a more stable model."
                ),
                "rate_limit": (
                    f"LLM rate limiting hit {count} times. "
                    "Consider: implement request batching, add backoff "
                    "delays, or increase rate limit quota."
                ),
                "default": (
                    f"LLM component '{error_type}' failed {count} times. "
                    "Review model configuration and provider status."
                ),
            },
            "service": {
                "unresponsive": (
                    f"Service unresponsive {count} times. "
                    "Consider: add health check endpoints, configure "
                    "auto-restart policies, or scale horizontally."
                ),
                "default": (
                    f"Service '{error_type}' failed {count} times. "
                    "Review service logs and resource utilization."
                ),
            },
        }

        comp_suggestions = suggestions.get(component, {})
        suggestion = comp_suggestions.get(
            error_type,
            comp_suggestions.get(
                "default",
                f"Component '{component}' experienced '{error_type}' "
                f"{count} times. Add monitoring and review logs."
            ),
        )
        return suggestion

    @property
    def total_failures(self) -> int:
        """Total number of recorded failures."""
        return len(self._records)

    def get_component_failures(self, component: str) -> list[FailureRecord]:
        """Get all failure records for a specific component."""
        return [r for r in self._records if r.component == component]
