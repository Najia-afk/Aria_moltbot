# tests/test_self_diagnostic.py
"""
Tests for TICKET-36: Self-Diagnostic & Auto-Recovery.

Covers:
- HealthSignal creation and properties
- HealthLedger recording, anomaly detection, and summaries
- Playbook matching and built-in definitions
- RecoveryExecutor with circuit breaker
- FailurePatternStore recurring pattern detection
- Integration: ledger → executor pipeline
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

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
from aria_skills.health.patterns import FailurePatternStore, FailureRecord


# ============================================================================
# HealthSignal tests
# ============================================================================


class TestHealthSignal:
    """Tests for HealthSignal dataclass."""

    def test_signal_creation_basic(self):
        sig = HealthSignal(
            component="service",
            metric="latency",
            value=5.0,
            threshold=3.0,
            severity=Severity.WARNING,
        )
        assert sig.component == "service"
        assert sig.metric == "latency"
        assert sig.value == 5.0
        assert sig.threshold == 3.0
        assert sig.severity == Severity.WARNING

    def test_signal_auto_timestamp(self):
        sig = HealthSignal(
            component="llm", metric="error_rate", value=0.5,
            threshold=0.1, severity=Severity.ERROR,
        )
        assert sig.timestamp != ""
        parsed = datetime.fromisoformat(sig.timestamp)
        assert parsed.tzinfo is not None  # UTC aware

    def test_signal_auto_message(self):
        sig = HealthSignal(
            component="database", metric="connections", value=100.0,
            threshold=80.0, severity=Severity.WARNING,
        )
        assert "database" in sig.message
        assert "connections" in sig.message
        assert "100.0" in sig.message

    def test_signal_custom_message(self):
        sig = HealthSignal(
            component="llm", metric="tokens", value=1.0,
            threshold=0.5, severity=Severity.INFO,
            message="Custom message",
        )
        assert sig.message == "Custom message"

    def test_signal_is_anomaly_true(self):
        sig = HealthSignal(
            component="cpu", metric="usage", value=95.0,
            threshold=80.0, severity=Severity.ERROR,
        )
        assert sig.is_anomaly is True

    def test_signal_is_anomaly_false(self):
        sig = HealthSignal(
            component="cpu", metric="usage", value=50.0,
            threshold=80.0, severity=Severity.INFO,
        )
        assert sig.is_anomaly is False

    def test_signal_is_anomaly_equal_threshold(self):
        sig = HealthSignal(
            component="mem", metric="pct", value=80.0,
            threshold=80.0, severity=Severity.WARNING,
        )
        # Equal to threshold → not anomalous (strictly >)
        assert sig.is_anomaly is False

    def test_signal_parsed_timestamp(self):
        ts = "2026-01-15T10:30:00+00:00"
        sig = HealthSignal(
            component="x", metric="y", value=1.0,
            threshold=0.5, severity=Severity.INFO, timestamp=ts,
        )
        parsed = sig.parsed_timestamp
        assert isinstance(parsed, datetime)
        assert parsed.year == 2026
        assert parsed.month == 1

    def test_severity_enum_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"


# ============================================================================
# HealthLedger tests
# ============================================================================


class TestHealthLedger:
    """Tests for HealthLedger rolling window and anomaly detection."""

    def _make_signal(self, component="svc", metric="err", value=10.0,
                     threshold=5.0, severity=Severity.ERROR,
                     resolved=False, timestamp=None):
        sig = HealthSignal(
            component=component, metric=metric, value=value,
            threshold=threshold, severity=severity,
        )
        if timestamp:
            sig.timestamp = timestamp
        sig.resolved = resolved
        return sig

    def test_record_stores_signal(self):
        ledger = HealthLedger()
        sig = self._make_signal()
        ledger.record(sig)
        assert len(ledger.signals) == 1
        assert ledger.signals[0] is sig

    def test_record_evicts_oldest_when_full(self):
        ledger = HealthLedger(max_signals=3)
        sigs = [self._make_signal(component=f"c{i}") for i in range(5)]
        for s in sigs:
            ledger.record(s)
        assert len(ledger.signals) == 3
        # Oldest 2 evicted
        assert ledger.signals[0].component == "c2"
        assert ledger.signals[-1].component == "c4"

    def test_get_anomalies_returns_unresolved_above_threshold(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(value=10.0, threshold=5.0))     # anomaly
        ledger.record(self._make_signal(value=2.0, threshold=5.0))      # healthy
        ledger.record(self._make_signal(value=8.0, threshold=5.0, resolved=True))  # resolved
        anomalies = ledger.get_anomalies(window_minutes=60)
        assert len(anomalies) == 1

    def test_get_anomalies_respects_time_window(self):
        ledger = HealthLedger()
        # Old signal
        old = self._make_signal()
        old.timestamp = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        ledger.record(old)
        # Recent signal
        ledger.record(self._make_signal())
        anomalies = ledger.get_anomalies(window_minutes=30)
        assert len(anomalies) == 1  # only the recent one

    def test_get_component_health_unknown_component(self):
        ledger = HealthLedger()
        result = ledger.get_component_health("nonexistent")
        assert result["status"] == "unknown"
        assert result["signal_count"] == 0

    def test_get_component_health_healthy(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(
            component="db", severity=Severity.INFO, value=1.0, threshold=5.0,
        ))
        result = ledger.get_component_health("db")
        assert result["status"] == "healthy"
        assert result["signal_count"] == 1

    def test_get_component_health_worst_severity(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(component="api", severity=Severity.INFO, value=1.0, threshold=5.0))
        ledger.record(self._make_signal(component="api", severity=Severity.ERROR))
        result = ledger.get_component_health("api")
        assert result["worst_severity"] == "error"

    def test_get_summary_structure(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(component="a", severity=Severity.WARNING))
        ledger.record(self._make_signal(component="b", severity=Severity.ERROR))
        summary = ledger.get_summary()
        assert "overall_status" in summary
        assert "total_signals" in summary
        assert "components" in summary
        assert "severity_counts" in summary
        assert summary["total_signals"] == 2

    def test_get_summary_overall_critical(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(severity=Severity.CRITICAL))
        summary = ledger.get_summary()
        assert summary["overall_status"] == "critical"

    def test_get_summary_overall_healthy_when_all_resolved(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(severity=Severity.ERROR, resolved=True))
        summary = ledger.get_summary()
        assert summary["overall_status"] == "healthy"

    def test_clear_resolved(self):
        ledger = HealthLedger()
        ledger.record(self._make_signal(component="x", resolved=True))
        ledger.record(self._make_signal(component="x", resolved=False))
        ledger.record(self._make_signal(component="y", resolved=True))
        removed = ledger.clear_resolved("x")
        assert removed == 1
        assert len(ledger.signals) == 2  # one x (unresolved) + one y


# ============================================================================
# Playbook tests
# ============================================================================


class TestPlaybooks:
    """Tests for recovery playbooks and matching."""

    def test_playbook_matches_exact(self):
        pb = Playbook(
            name="test", description="t",
            trigger_condition="service.unresponsive",
            severity_filter=["error"],
        )
        assert pb.matches("service", "unresponsive", "error") is True

    def test_playbook_no_match_wrong_metric(self):
        pb = Playbook(
            name="test", description="t",
            trigger_condition="service.unresponsive",
            severity_filter=["error"],
        )
        assert pb.matches("service", "latency", "error") is False

    def test_playbook_no_match_wrong_severity(self):
        pb = Playbook(
            name="test", description="t",
            trigger_condition="service.unresponsive",
            severity_filter=["critical"],
        )
        assert pb.matches("service", "unresponsive", "error") is False

    def test_playbook_matches_without_severity_filter(self):
        pb = Playbook(
            name="test", description="t",
            trigger_condition="service.unresponsive",
        )
        assert pb.matches("service", "unresponsive", "info") is True

    def test_builtin_restart_service(self):
        assert RESTART_SERVICE.name == "restart_service"
        assert RESTART_SERVICE.trigger_condition == "service.unresponsive"
        assert len(RESTART_SERVICE.steps) > 0

    def test_builtin_clear_cache(self):
        assert CLEAR_CACHE.name == "clear_cache"
        assert "cache" in CLEAR_CACHE.trigger_condition

    def test_builtin_model_fallback(self):
        assert MODEL_FALLBACK.name == "model_fallback"
        assert MODEL_FALLBACK.matches("llm", "model_error", "error") is True

    def test_builtin_database_recovery(self):
        assert DATABASE_RECOVERY.name == "database_recovery"
        assert DATABASE_RECOVERY.matches("database", "connection_error", "error") is True

    def test_all_playbooks_contains_all(self):
        names = {pb.name for pb in ALL_PLAYBOOKS}
        assert "restart_service" in names
        assert "clear_cache" in names
        assert "reduce_load" in names
        assert "model_fallback" in names
        assert "database_recovery" in names

    def test_playbook_default_cooldown(self):
        pb = Playbook(name="t", description="t", trigger_condition="x")
        assert pb.cooldown_seconds == 300

    def test_playbook_default_max_retries(self):
        pb = Playbook(name="t", description="t", trigger_condition="x")
        assert pb.max_retries == 3


# ============================================================================
# RecoveryExecutor tests
# ============================================================================


class TestRecoveryExecutor:
    """Tests for the recovery executor with circuit breaker."""

    def _make_signal(self, component="service", metric="unresponsive",
                     value=10.0, threshold=5.0, severity=Severity.ERROR):
        return HealthSignal(
            component=component, metric=metric, value=value,
            threshold=threshold, severity=severity,
        )

    @pytest.mark.asyncio
    async def test_evaluate_no_anomalies(self):
        ledger = HealthLedger()
        executor = RecoveryExecutor(ledger)
        actions = await executor.evaluate_and_recover()
        assert actions == []

    @pytest.mark.asyncio
    async def test_evaluate_matches_playbook_and_executes(self):
        ledger = HealthLedger()
        sig = self._make_signal()
        ledger.record(sig)
        executor = RecoveryExecutor(ledger, playbooks=[RESTART_SERVICE])
        actions = await executor.evaluate_and_recover()
        assert len(actions) == 1
        assert actions[0].playbook_name == "restart_service"
        assert actions[0].success is True
        # Signal should be marked resolved
        assert sig.resolved is True

    @pytest.mark.asyncio
    async def test_evaluate_no_matching_playbook(self):
        ledger = HealthLedger()
        sig = self._make_signal(component="unknown_comp", metric="unknown_metric")
        ledger.record(sig)
        executor = RecoveryExecutor(ledger, playbooks=[RESTART_SERVICE])
        actions = await executor.evaluate_and_recover()
        assert actions == []  # no playbook matches

    @pytest.mark.asyncio
    async def test_history_tracks_executions(self):
        ledger = HealthLedger()
        sig = self._make_signal()
        ledger.record(sig)
        executor = RecoveryExecutor(ledger, playbooks=[RESTART_SERVICE])
        await executor.evaluate_and_recover()
        assert len(executor.history) == 1
        assert executor.history[0].playbook_name == "restart_service"

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_repeated_execution(self):
        ledger = HealthLedger()
        # First execution
        sig1 = self._make_signal()
        ledger.record(sig1)
        executor = RecoveryExecutor(ledger, playbooks=[
            Playbook(
                name="fast_pb", description="t",
                trigger_condition="service.unresponsive",
                steps=[{"action": "log", "message": "recovering"}],
                cooldown_seconds=600,
                severity_filter=["error"],
            ),
        ])
        actions1 = await executor.evaluate_and_recover()
        assert len(actions1) == 1

        # Second execution within cooldown → blocked
        sig2 = self._make_signal()
        ledger.record(sig2)
        actions2 = await executor.evaluate_and_recover()
        assert len(actions2) == 0  # circuit open

    @pytest.mark.asyncio
    async def test_max_retries_blocks_after_failures(self):
        ledger = HealthLedger()
        failing_pb = Playbook(
            name="fail_pb", description="t",
            trigger_condition="service.unresponsive",
            steps=[
                {"action": "log", "message": "trying"},
                {"action": "INVALID_ACTION_THAT_WONT_CAUSE_EXCEPTION", "message": "x"},
            ],
            max_retries=1,
            cooldown_seconds=0,
            severity_filter=["error"],
        )
        executor = RecoveryExecutor(ledger, playbooks=[failing_pb])
        # Simulate a failure count exceeding max_retries
        executor._failure_counts["fail_pb"] = 2
        sig = self._make_signal()
        ledger.record(sig)
        actions = await executor.evaluate_and_recover()
        assert len(actions) == 0  # max retries exceeded

    @pytest.mark.asyncio
    async def test_execute_step_wait(self):
        """Wait step should call asyncio.sleep."""
        ledger = HealthLedger()
        executor = RecoveryExecutor(ledger)
        sig = self._make_signal()
        with patch("aria_skills.health.recovery.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await executor._execute_step({"action": "wait", "seconds": 5}, sig)
            mock_sleep.assert_awaited_once_with(5)


# ============================================================================
# RecoveryAction tests
# ============================================================================


class TestRecoveryAction:
    """Tests for RecoveryAction dataclass."""

    def test_action_creation(self):
        action = RecoveryAction(
            playbook_name="restart_service",
            signal_component="service",
            signal_metric="unresponsive",
            steps_executed=3,
            success=True,
        )
        assert action.playbook_name == "restart_service"
        assert action.success is True
        assert action.error is None

    def test_action_auto_timestamp(self):
        action = RecoveryAction(
            playbook_name="t", signal_component="c",
            signal_metric="m", steps_executed=0, success=False,
        )
        assert action.timestamp != ""
        parsed = datetime.fromisoformat(action.timestamp)
        assert parsed.tzinfo is not None

    def test_action_with_error(self):
        action = RecoveryAction(
            playbook_name="t", signal_component="c",
            signal_metric="m", steps_executed=1, success=False,
            error="connection refused",
        )
        assert action.error == "connection refused"


# ============================================================================
# FailurePatternStore tests
# ============================================================================


class TestFailurePatternStore:
    """Tests for failure pattern tracking and learning."""

    def test_record_failure(self):
        store = FailurePatternStore()
        store.record_failure("db", "timeout", {"query": "SELECT 1"})
        assert store.total_failures == 1

    def test_recurring_patterns_below_threshold(self):
        store = FailurePatternStore()
        store.record_failure("db", "timeout")
        store.record_failure("db", "timeout")
        patterns = store.get_recurring_patterns(min_occurrences=3)
        assert len(patterns) == 0

    def test_recurring_patterns_at_threshold(self):
        store = FailurePatternStore()
        for _ in range(3):
            store.record_failure("db", "timeout")
        patterns = store.get_recurring_patterns(min_occurrences=3)
        assert len(patterns) == 1
        assert patterns[0]["component"] == "db"
        assert patterns[0]["error_type"] == "timeout"
        assert patterns[0]["count"] == 3

    def test_recurring_patterns_sorted_by_count(self):
        store = FailurePatternStore()
        for _ in range(5):
            store.record_failure("llm", "model_error")
        for _ in range(3):
            store.record_failure("db", "timeout")
        patterns = store.get_recurring_patterns(min_occurrences=3)
        assert len(patterns) == 2
        assert patterns[0]["count"] >= patterns[1]["count"]

    def test_eviction_at_capacity(self):
        store = FailurePatternStore(max_records=5)
        for i in range(10):
            store.record_failure(f"comp{i}", "err")
        assert store.total_failures == 5

    def test_get_component_failures(self):
        store = FailurePatternStore()
        store.record_failure("db", "timeout")
        store.record_failure("llm", "error")
        store.record_failure("db", "connection")
        db_failures = store.get_component_failures("db")
        assert len(db_failures) == 2
        assert all(f.component == "db" for f in db_failures)

    def test_suggest_prevention_database(self):
        store = FailurePatternStore()
        suggestion = store.suggest_prevention({
            "component": "database",
            "error_type": "connection_error",
            "count": 5,
        })
        assert "connection" in suggestion.lower() or "database" in suggestion.lower()

    def test_suggest_prevention_llm(self):
        store = FailurePatternStore()
        suggestion = store.suggest_prevention({
            "component": "llm",
            "error_type": "model_error",
            "count": 3,
        })
        assert "model" in suggestion.lower() or "llm" in suggestion.lower()

    def test_suggest_prevention_unknown(self):
        store = FailurePatternStore()
        suggestion = store.suggest_prevention({
            "component": "mystery",
            "error_type": "bizarre",
            "count": 7,
        })
        assert isinstance(suggestion, str)
        assert len(suggestion) > 0


# ============================================================================
# FailureRecord tests
# ============================================================================


class TestFailureRecord:
    """Tests for FailureRecord dataclass."""

    def test_record_auto_timestamp(self):
        rec = FailureRecord(component="db", error_type="timeout")
        assert rec.timestamp != ""
        parsed = datetime.fromisoformat(rec.timestamp)
        assert parsed.tzinfo is not None

    def test_record_with_context(self):
        rec = FailureRecord(
            component="llm", error_type="rate_limit",
            context={"model": "qwen3", "tokens": 500},
        )
        assert rec.context["model"] == "qwen3"


# ============================================================================
# Integration tests
# ============================================================================


class TestIntegration:
    """End-to-end tests: ledger detects anomaly → executor runs playbook."""

    @pytest.mark.asyncio
    async def test_ledger_anomaly_triggers_recovery(self):
        """Full pipeline: record anomalous signal → detect → recover."""
        ledger = HealthLedger()
        executor = RecoveryExecutor(ledger, playbooks=[MODEL_FALLBACK])

        # Record an LLM anomaly matching MODEL_FALLBACK
        sig = HealthSignal(
            component="llm", metric="model_error", value=10.0,
            threshold=1.0, severity=Severity.ERROR,
        )
        ledger.record(sig)

        # Verify anomaly exists
        anomalies = ledger.get_anomalies()
        assert len(anomalies) == 1

        # Execute recovery
        actions = await executor.evaluate_and_recover()
        assert len(actions) == 1
        assert actions[0].playbook_name == "model_fallback"
        assert actions[0].success is True

        # Signal should now be resolved
        assert sig.resolved is True
        # Anomaly list should be empty
        assert len(ledger.get_anomalies()) == 0

    @pytest.mark.asyncio
    async def test_pattern_store_integrates_with_signals(self):
        """Record failures from signals into pattern store."""
        ledger = HealthLedger()
        store = FailurePatternStore()

        # Simulate repeated database errors
        for _ in range(4):
            sig = HealthSignal(
                component="database", metric="connection_error",
                value=10.0, threshold=1.0, severity=Severity.ERROR,
            )
            ledger.record(sig)
            store.record_failure(sig.component, sig.metric)

        patterns = store.get_recurring_patterns(min_occurrences=3)
        assert len(patterns) == 1
        assert patterns[0]["component"] == "database"

        suggestion = store.suggest_prevention(patterns[0])
        assert isinstance(suggestion, str)

    @pytest.mark.asyncio
    async def test_full_cycle_record_detect_recover_learn(self):
        """Record → detect anomaly → recover → store pattern for learning."""
        ledger = HealthLedger()
        store = FailurePatternStore()
        executor = RecoveryExecutor(ledger, playbooks=[DATABASE_RECOVERY])

        # Inject 3 database failures
        for _ in range(3):
            sig = HealthSignal(
                component="database", metric="connection_error",
                value=5.0, threshold=1.0, severity=Severity.ERROR,
            )
            ledger.record(sig)
            store.record_failure(sig.component, sig.metric)

        # Run recovery
        actions = await executor.evaluate_and_recover()
        # At least some signals matched and were recovered
        assert len(actions) >= 1

        # Pattern store should show recurring issue
        patterns = store.get_recurring_patterns(min_occurrences=3)
        assert len(patterns) >= 1

        # Summary should reflect state
        summary = ledger.get_summary()
        assert summary["total_signals"] == 3
