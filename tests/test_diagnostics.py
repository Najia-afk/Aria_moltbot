# tests/test_diagnostics.py
"""
Tests for Aria self-diagnostic & auto-recovery system (TICKET-36).

Covers: HealthSignal, Severity, HealthLedger, Playbooks,
        RecoveryExecutor (circuit breaker), FailurePatternStore.
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio

pytestmark = pytest.mark.unit

from aria_skills.health.diagnostics import HealthSignal, HealthLedger, Severity
from aria_skills.health.playbooks import (
    Playbook,
    RESTART_SERVICE,
    CLEAR_CACHE,
    REDUCE_LOAD,
    MODEL_FALLBACK,
    DATABASE_RECOVERY,
    ALL_PLAYBOOKS,
)
from aria_skills.health.recovery import RecoveryExecutor, RecoveryAction
from aria_skills.health.patterns import FailurePatternStore


# ── HealthSignal tests ──────────────────────────────────────────────────


class TestHealthSignal:
    def test_health_signal_creation(self):
        """Test basic HealthSignal construction and defaults."""
        signal = HealthSignal(
            component="database",
            metric="latency_ms",
            value=500.0,
            threshold=200.0,
            severity=Severity.WARNING,
        )
        assert signal.component == "database"
        assert signal.metric == "latency_ms"
        assert signal.value == 500.0
        assert signal.threshold == 200.0
        assert signal.severity == Severity.WARNING
        assert signal.timestamp  # auto-filled
        assert "database.latency_ms" in signal.message
        assert signal.resolved is False

    def test_severity_enum(self):
        """All severity levels exist and have correct values."""
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"
        assert len(Severity) == 4

    def test_health_signal_custom_timestamp(self):
        """Custom timestamp is preserved."""
        ts = "2026-01-01T00:00:00+00:00"
        signal = HealthSignal(
            component="cpu",
            metric="usage",
            value=90.0,
            threshold=80.0,
            severity=Severity.ERROR,
            timestamp=ts,
        )
        assert signal.timestamp == ts

    def test_health_signal_is_anomaly(self):
        """is_anomaly is True iff value > threshold."""
        normal = HealthSignal("a", "b", 50.0, 100.0, Severity.INFO)
        assert normal.is_anomaly is False

        anomalous = HealthSignal("a", "b", 150.0, 100.0, Severity.ERROR)
        assert anomalous.is_anomaly is True


# ── HealthLedger tests ──────────────────────────────────────────────────


class TestHealthLedger:
    def test_ledger_record(self):
        """Signals are recorded and retrievable."""
        ledger = HealthLedger()
        sig = HealthSignal("db", "conn", 5.0, 3.0, Severity.WARNING)
        ledger.record(sig)
        assert len(ledger.signals) == 1
        assert ledger.signals[0] is sig

    def test_ledger_max_signals(self):
        """Ledger evicts oldest signals when max_signals exceeded."""
        ledger = HealthLedger(max_signals=5)
        for i in range(10):
            ledger.record(
                HealthSignal("c", "m", float(i), 0.0, Severity.INFO)
            )
        assert len(ledger.signals) == 5
        # Oldest surviving should be signal 5
        assert ledger.signals[0].value == 5.0

    def test_ledger_anomalies(self):
        """get_anomalies returns only unresolved anomalous signals in window."""
        ledger = HealthLedger()
        # Normal signal (value <= threshold)
        ledger.record(HealthSignal("a", "b", 1.0, 10.0, Severity.INFO))
        # Anomalous signal
        ledger.record(HealthSignal("a", "b", 20.0, 10.0, Severity.ERROR))
        # Resolved anomalous signal
        resolved = HealthSignal("a", "b", 20.0, 10.0, Severity.ERROR)
        resolved.resolved = True
        ledger.record(resolved)

        anomalies = ledger.get_anomalies(window_minutes=60)
        assert len(anomalies) == 1
        assert anomalies[0].value == 20.0
        assert anomalies[0].resolved is False

    def test_ledger_anomalies_window(self):
        """Signals outside the time window are excluded."""
        ledger = HealthLedger()
        # Old signal (2 hours ago)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        old = HealthSignal("a", "b", 99.0, 10.0, Severity.ERROR, timestamp=old_ts)
        ledger.record(old)
        # Recent signal
        ledger.record(HealthSignal("a", "b", 99.0, 10.0, Severity.ERROR))

        anomalies = ledger.get_anomalies(window_minutes=60)
        assert len(anomalies) == 1  # only the recent one

    def test_ledger_component_health(self):
        """get_component_health returns correct summary for a component."""
        ledger = HealthLedger()
        ledger.record(HealthSignal("db", "conn", 1.0, 10.0, Severity.INFO))
        ledger.record(HealthSignal("db", "latency", 500.0, 200.0, Severity.ERROR))

        health = ledger.get_component_health("db")
        assert health["component"] == "db"
        assert health["signal_count"] == 2
        assert health["active_count"] == 2
        assert health["worst_severity"] == "error"

    def test_ledger_component_health_unknown(self):
        """Unknown component returns status=unknown."""
        ledger = HealthLedger()
        health = ledger.get_component_health("nonexistent")
        assert health["status"] == "unknown"
        assert health["signal_count"] == 0

    def test_ledger_summary(self):
        """get_summary aggregates across all components."""
        ledger = HealthLedger()
        ledger.record(HealthSignal("db", "conn", 1.0, 10.0, Severity.INFO))
        ledger.record(HealthSignal("llm", "error", 5.0, 1.0, Severity.CRITICAL))

        summary = ledger.get_summary()
        assert summary["overall_status"] == "critical"
        assert summary["total_signals"] == 2
        assert "db" in summary["components"]
        assert "llm" in summary["components"]
        assert "timestamp" in summary

    def test_ledger_summary_healthy(self):
        """Summary reports healthy when only INFO signals exist."""
        ledger = HealthLedger()
        ledger.record(HealthSignal("a", "b", 1.0, 10.0, Severity.INFO))
        summary = ledger.get_summary()
        assert summary["overall_status"] == "healthy"

    def test_ledger_clear_resolved(self):
        """clear_resolved removes resolved signals for a component."""
        ledger = HealthLedger()
        s1 = HealthSignal("db", "conn", 5.0, 3.0, Severity.WARNING)
        s1.resolved = True
        s2 = HealthSignal("db", "lat", 1.0, 10.0, Severity.INFO)
        s3 = HealthSignal("llm", "err", 5.0, 1.0, Severity.ERROR)
        s3.resolved = True
        ledger.record(s1)
        ledger.record(s2)
        ledger.record(s3)

        removed = ledger.clear_resolved("db")
        assert removed == 1
        assert len(ledger.signals) == 2  # s2 and s3 remain
        # llm resolved signal still present
        assert any(s.component == "llm" for s in ledger.signals)


# ── Playbook tests ──────────────────────────────────────────────────────


class TestPlaybooks:
    def test_playbook_definitions(self):
        """All 5 built-in playbooks are defined with required fields."""
        assert len(ALL_PLAYBOOKS) == 5
        for pb in ALL_PLAYBOOKS:
            assert isinstance(pb, Playbook)
            assert pb.name
            assert pb.description
            assert pb.trigger_condition
            assert len(pb.steps) > 0
            assert pb.cooldown_seconds > 0
            assert pb.max_retries > 0

    def test_playbook_matches(self):
        """Playbook.matches works with component.metric and severity filter."""
        pb = Playbook(
            name="test",
            description="test",
            trigger_condition="database.connection_error",
            severity_filter=["error", "critical"],
        )
        assert pb.matches("database", "connection_error", "error") is True
        assert pb.matches("database", "connection_error", "info") is False
        assert pb.matches("llm", "model_error", "error") is False

    def test_playbook_matches_no_filter(self):
        """Match without severity_filter accepts any severity."""
        pb = Playbook(
            name="test",
            description="test",
            trigger_condition="system.cpu_high",
        )
        assert pb.matches("system", "cpu_high", "info") is True


# ── RecoveryExecutor tests ──────────────────────────────────────────────


class TestRecoveryExecutor:
    @pytest.mark.asyncio
    async def test_recovery_executor_no_signals(self):
        """No anomalies → no recovery actions."""
        ledger = HealthLedger()
        executor = RecoveryExecutor(ledger)
        actions = await executor.evaluate_and_recover()
        assert actions == []

    @pytest.mark.asyncio
    @patch("aria_skills.health.recovery.asyncio.sleep", new_callable=AsyncMock)
    async def test_recovery_executor_with_matching_signal(self, mock_sleep):
        """Anomaly matching a playbook triggers recovery."""
        ledger = HealthLedger()
        ledger.record(
            HealthSignal("service", "unresponsive", 10.0, 1.0, Severity.ERROR)
        )
        executor = RecoveryExecutor(ledger)
        actions = await executor.evaluate_and_recover()
        assert len(actions) == 1
        assert actions[0].playbook_name == "restart_service"
        assert actions[0].success is True

    @pytest.mark.asyncio
    @patch("aria_skills.health.recovery.asyncio.sleep", new_callable=AsyncMock)
    async def test_recovery_executor_playbook_execution(self, mock_sleep):
        """Playbook steps are executed and signal is marked resolved."""
        ledger = HealthLedger()
        signal = HealthSignal(
            "database", "connection_error", 10.0, 1.0, Severity.ERROR
        )
        ledger.record(signal)
        executor = RecoveryExecutor(ledger)
        actions = await executor.evaluate_and_recover()
        assert len(actions) == 1
        assert actions[0].success is True
        assert actions[0].steps_executed > 0
        assert signal.resolved is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_cooldown(self):
        """Second execution within cooldown is skipped (circuit open)."""
        ledger = HealthLedger()
        short_cooldown_pb = Playbook(
            name="fast_pb",
            description="test",
            trigger_condition="test.metric",
            steps=[{"action": "log", "message": "test"}],
            cooldown_seconds=9999,
            max_retries=3,
            severity_filter=["error"],
        )
        ledger.record(
            HealthSignal("test", "metric", 10.0, 1.0, Severity.ERROR)
        )
        executor = RecoveryExecutor(ledger, playbooks=[short_cooldown_pb])

        # First run should execute
        actions1 = await executor.evaluate_and_recover()
        assert len(actions1) == 1

        # Reset signal to unresolved and add a new one
        ledger.record(
            HealthSignal("test", "metric", 10.0, 1.0, Severity.ERROR)
        )

        # Second run within cooldown should skip
        actions2 = await executor.evaluate_and_recover()
        assert len(actions2) == 0

    @pytest.mark.asyncio
    async def test_recovery_action_dataclass(self):
        """RecoveryAction has all required fields."""
        action = RecoveryAction(
            playbook_name="test",
            signal_component="db",
            signal_metric="latency",
            steps_executed=3,
            success=True,
        )
        assert action.playbook_name == "test"
        assert action.timestamp  # auto-filled
        assert action.error is None

    @pytest.mark.asyncio
    async def test_recovery_executor_no_matching_playbook(self):
        """An anomaly with no matching playbook produces no action."""
        ledger = HealthLedger()
        ledger.record(
            HealthSignal("unknown_comp", "unknown_metric", 10.0, 1.0, Severity.ERROR)
        )
        executor = RecoveryExecutor(ledger)
        actions = await executor.evaluate_and_recover()
        assert len(actions) == 0


# ── FailurePatternStore tests ──────────────────────────────────────────


class TestFailurePatternStore:
    def test_failure_pattern_record(self):
        """Records are stored and counted."""
        store = FailurePatternStore()
        store.record_failure("db", "timeout", {"query": "SELECT 1"})
        assert store.total_failures == 1

    def test_failure_pattern_recurring(self):
        """Patterns above threshold are returned by get_recurring_patterns."""
        store = FailurePatternStore()
        for _ in range(5):
            store.record_failure("db", "timeout")
        for _ in range(2):
            store.record_failure("llm", "rate_limit")

        patterns = store.get_recurring_patterns(min_occurrences=3)
        assert len(patterns) == 1
        assert patterns[0]["component"] == "db"
        assert patterns[0]["error_type"] == "timeout"
        assert patterns[0]["count"] == 5

    def test_failure_pattern_suggest(self):
        """suggest_prevention returns a non-empty suggestion string."""
        store = FailurePatternStore()
        pattern = {"component": "database", "error_type": "connection_error", "count": 5}
        suggestion = store.suggest_prevention(pattern)
        assert isinstance(suggestion, str)
        assert len(suggestion) > 20
        assert "5" in suggestion  # should reference the count

    def test_failure_pattern_suggest_default(self):
        """suggest_prevention falls back for unknown component/error combos."""
        store = FailurePatternStore()
        pattern = {"component": "exotic", "error_type": "weird_error", "count": 7}
        suggestion = store.suggest_prevention(pattern)
        assert "exotic" in suggestion
        assert "weird_error" in suggestion

    def test_failure_pattern_eviction(self):
        """Records are evicted when max_records is exceeded."""
        store = FailurePatternStore(max_records=5)
        for i in range(10):
            store.record_failure("comp", "err", {"i": i})
        assert store.total_failures == 5

    def test_failure_pattern_component_failures(self):
        """get_component_failures filters correctly."""
        store = FailurePatternStore()
        store.record_failure("db", "timeout")
        store.record_failure("llm", "error")
        store.record_failure("db", "connection_error")
        db_failures = store.get_component_failures("db")
        assert len(db_failures) == 2
        assert all(f.component == "db" for f in db_failures)
