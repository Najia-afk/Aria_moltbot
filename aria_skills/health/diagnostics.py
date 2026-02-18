# aria_skills/health/diagnostics.py
"""
Self-diagnostic health signals and anomaly detection ledger.

Part of Aria's self-healing system (TICKET-36).
Architecture: DB ↔ SQLAlchemy ↔ FastAPI ↔ api_client ↔ Skills ↔ ARIA
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum


class Severity(Enum):
    """Severity levels for health signals."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthSignal:
    """A single health observation from a monitored component."""
    component: str
    metric: str
    value: float
    threshold: float
    severity: Severity
    timestamp: str = ""
    message: str = ""
    resolved: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.message:
            self.message = (
                f"{self.component}.{self.metric}: {self.value} "
                f"(threshold {self.threshold}, {self.severity.value})"
            )

    @property
    def is_anomaly(self) -> bool:
        """A signal is anomalous if value exceeds threshold."""
        return self.value > self.threshold

    @property
    def parsed_timestamp(self) -> datetime:
        """Parse the ISO timestamp string back to datetime."""
        return datetime.fromisoformat(self.timestamp)


class HealthLedger:
    """Rolling window of health signals with anomaly detection."""

    def __init__(self, max_signals: int = 1000):
        self.signals: list[HealthSignal] = []
        self.max_signals = max_signals

    def record(self, signal: HealthSignal) -> None:
        """Record a health signal, evicting oldest if at capacity."""
        self.signals.append(signal)
        if len(self.signals) > self.max_signals:
            self.signals = self.signals[-self.max_signals:]

    def get_anomalies(self, window_minutes: int = 60) -> list[HealthSignal]:
        """Return anomalous signals within the given time window."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        return [
            s for s in self.signals
            if s.is_anomaly
            and not s.resolved
            and s.parsed_timestamp >= cutoff
        ]

    def get_component_health(self, component: str) -> dict:
        """Get health summary for a specific component."""
        comp_signals = [s for s in self.signals if s.component == component]
        if not comp_signals:
            return {"component": component, "status": "unknown", "signal_count": 0}

        active = [s for s in comp_signals if not s.resolved]
        worst = Severity.INFO
        severity_order = {
            Severity.INFO: 0,
            Severity.WARNING: 1,
            Severity.ERROR: 2,
            Severity.CRITICAL: 3,
        }
        for s in active:
            if severity_order.get(s.severity, 0) > severity_order.get(worst, 0):
                worst = s.severity

        return {
            "component": component,
            "status": "healthy" if worst == Severity.INFO else worst.value,
            "signal_count": len(comp_signals),
            "active_count": len(active),
            "worst_severity": worst.value,
            "latest_timestamp": comp_signals[-1].timestamp,
        }

    def get_summary(self) -> dict:
        """Get overall system health summary."""
        components = set(s.component for s in self.signals)
        component_summaries = {c: self.get_component_health(c) for c in components}

        active_signals = [s for s in self.signals if not s.resolved]
        severity_counts = {}
        for s in active_signals:
            severity_counts[s.severity.value] = severity_counts.get(s.severity.value, 0) + 1

        # Determine overall status
        if severity_counts.get("critical", 0) > 0:
            overall = "critical"
        elif severity_counts.get("error", 0) > 0:
            overall = "error"
        elif severity_counts.get("warning", 0) > 0:
            overall = "warning"
        else:
            overall = "healthy"

        return {
            "overall_status": overall,
            "total_signals": len(self.signals),
            "active_signals": len(active_signals),
            "severity_counts": severity_counts,
            "components": component_summaries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def clear_resolved(self, component: str) -> int:
        """Remove resolved signals for a component. Returns count removed."""
        before = len(self.signals)
        self.signals = [
            s for s in self.signals
            if not (s.component == component and s.resolved)
        ]
        return before - len(self.signals)
