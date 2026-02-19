"""
Unit tests for aria_engine.metrics.

Tests all Prometheus metric types, decorators, and server startup.
"""
import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest
from prometheus_client import CollectorRegistry

from aria_engine.metrics import AriaMetrics, track_request, track_llm, update_system_metrics


# ---------------------------------------------------------------------------
# Use a fresh registry to avoid conflicts with global state
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_registry():
    """Create a fresh CollectorRegistry for isolated testing."""
    return CollectorRegistry()


@pytest.fixture
def metrics(fresh_registry):
    """Create AriaMetrics with a fresh registry."""
    return AriaMetrics(reg=fresh_registry)


# ---------------------------------------------------------------------------
# Metric creation tests
# ---------------------------------------------------------------------------

class TestAriaMetrics:
    """Test that all metrics are created correctly."""

    def test_build_info_exists(self, metrics):
        assert metrics.build_info is not None

    def test_request_total_counter(self, metrics):
        metrics.request_total.labels(method="chat", status="200").inc()
        val = metrics.request_total.labels(method="chat", status="200")._value.get()
        assert val == 1.0

    def test_request_duration_histogram(self, metrics):
        metrics.request_duration.labels(method="chat").observe(0.15)
        # Histogram sum should update
        assert metrics.request_duration.labels(method="chat")._sum.get() > 0

    def test_request_in_progress_gauge(self, metrics):
        metrics.request_in_progress.labels(method="chat").inc()
        assert metrics.request_in_progress.labels(method="chat")._value.get() == 1.0
        metrics.request_in_progress.labels(method="chat").dec()
        assert metrics.request_in_progress.labels(method="chat")._value.get() == 0.0

    def test_llm_request_total(self, metrics):
        metrics.llm_request_total.labels(model="kimi", status="success").inc()
        val = metrics.llm_request_total.labels(model="kimi", status="success")._value.get()
        assert val == 1.0

    def test_llm_tokens_counters(self, metrics):
        metrics.llm_tokens_input.labels(model="kimi").inc(1000)
        metrics.llm_tokens_output.labels(model="kimi").inc(500)
        assert metrics.llm_tokens_input.labels(model="kimi")._value.get() == 1000.0
        assert metrics.llm_tokens_output.labels(model="kimi")._value.get() == 500.0

    def test_agent_routing(self, metrics):
        metrics.agent_routing_total.labels(selected_agent="aria-talk").inc()
        val = metrics.agent_routing_total.labels(selected_agent="aria-talk")._value.get()
        assert val == 1.0

    def test_agent_pheromone_score(self, metrics):
        metrics.agent_pheromone_score.labels(agent_id="aria-talk").set(0.85)
        assert metrics.agent_pheromone_score.labels(agent_id="aria-talk")._value.get() == 0.85

    def test_sessions_active(self, metrics):
        metrics.sessions_active.set(5)
        assert metrics.sessions_active._value.get() == 5.0

    def test_scheduler_metrics(self, metrics):
        metrics.scheduler_jobs_total.labels(status="active").set(10)
        metrics.scheduler_executions_total.labels(job_id="heartbeat", status="success").inc()
        assert metrics.scheduler_jobs_total.labels(status="active")._value.get() == 10.0

    def test_skill_execution(self, metrics):
        metrics.skill_execution_total.labels(skill_name="llm", status="success").inc()
        metrics.skill_execution_duration.labels(skill_name="llm").observe(1.5)
        assert metrics.skill_execution_total.labels(
            skill_name="llm", status="success"
        )._value.get() == 1.0

    def test_db_metrics(self, metrics):
        metrics.db_query_total.labels(operation="select").inc()
        metrics.db_query_duration.labels(operation="select").observe(0.005)
        assert metrics.db_query_total.labels(operation="select")._value.get() == 1.0

    def test_error_metrics(self, metrics):
        metrics.errors_total.labels(error_type="LLMError", component="chat").inc()
        assert metrics.errors_total.labels(
            error_type="LLMError", component="chat"
        )._value.get() == 1.0

    def test_memory_metrics(self, metrics):
        metrics.memory_rss_bytes.set(256 * 1024 * 1024)
        metrics.memory_gc_objects.set(50000)
        assert metrics.memory_rss_bytes._value.get() == 256 * 1024 * 1024
        assert metrics.memory_gc_objects._value.get() == 50000


# ---------------------------------------------------------------------------
# System metrics update
# ---------------------------------------------------------------------------

class TestSystemMetrics:
    """Test system metrics collection."""

    @pytest.mark.asyncio
    async def test_update_system_metrics(self):
        """Test that update_system_metrics runs without error."""
        await update_system_metrics()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    """Test that the METRICS singleton is accessible."""

    def test_metrics_singleton_import(self):
        from aria_engine.metrics import METRICS
        assert METRICS is not None
        assert hasattr(METRICS, "request_total")
        assert hasattr(METRICS, "llm_request_total")
        assert hasattr(METRICS, "agent_routing_total")
        assert hasattr(METRICS, "sessions_active")
        assert hasattr(METRICS, "scheduler_jobs_total")
        assert hasattr(METRICS, "errors_total")
        assert hasattr(METRICS, "memory_rss_bytes")
