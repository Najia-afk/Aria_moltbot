# S12-03: Prometheus Metrics on Port 8081
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 12

## Problem
Aria Blue needs production-grade observability. The Prometheus stack (already in docker-compose) needs actual metrics from `aria_engine`: request latencies, LLM token usage, agent routing decisions, scheduler job status, session counts, and error rates. These metrics must be exposed on a dedicated port (8081) and visualized in Grafana.

## Root Cause
OpenClaw exposed basic Node.js metrics. After migration, we have zero metrics from the Python engine. Without metrics, we're flying blind — we can't detect degradation, set alerts, or plan capacity. This ticket implements the full metrics layer.

## Fix
### `aria_engine/metrics.py`
```python
"""
Prometheus metrics for Aria Blue.

Exposes metrics on port 8081 via a dedicated HTTP server.
All counters, histograms, and gauges follow Prometheus naming conventions.

Usage:
    from aria_engine.metrics import METRICS, start_metrics_server
    
    # Start metrics server on port 8081
    await start_metrics_server(port=8081)
    
    # Record a request
    METRICS.request_duration.labels(method="chat", status="200").observe(0.15)
"""
import asyncio
import os
import time
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    Summary,
    generate_latest,
    start_http_server,
    REGISTRY,
)


# ---------------------------------------------------------------------------
# Custom registry (allows testing without global state pollution)
# ---------------------------------------------------------------------------

registry = REGISTRY


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

class AriaMetrics:
    """All Aria Blue metrics in one place."""

    def __init__(self, reg: CollectorRegistry = registry):
        # -- System info --
        self.build_info = Info(
            "aria_build",
            "Aria Blue build information",
            registry=reg,
        )

        # -- Request metrics --
        self.request_total = Counter(
            "aria_requests_total",
            "Total requests processed",
            ["method", "status"],
            registry=reg,
        )

        self.request_duration = Histogram(
            "aria_request_duration_seconds",
            "Request duration in seconds",
            ["method"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            registry=reg,
        )

        self.request_in_progress = Gauge(
            "aria_requests_in_progress",
            "Number of requests currently being processed",
            ["method"],
            registry=reg,
        )

        # -- LLM metrics --
        self.llm_request_total = Counter(
            "aria_llm_requests_total",
            "Total LLM API calls",
            ["model", "status"],
            registry=reg,
        )

        self.llm_request_duration = Histogram(
            "aria_llm_request_duration_seconds",
            "LLM request duration (time to first token for streaming)",
            ["model"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=reg,
        )

        self.llm_tokens_input = Counter(
            "aria_llm_tokens_input_total",
            "Total input tokens sent to LLM",
            ["model"],
            registry=reg,
        )

        self.llm_tokens_output = Counter(
            "aria_llm_tokens_output_total",
            "Total output tokens received from LLM",
            ["model"],
            registry=reg,
        )

        self.llm_token_cost_estimate = Counter(
            "aria_llm_token_cost_estimate_total",
            "Estimated token cost in USD",
            ["model"],
            registry=reg,
        )

        self.llm_circuit_breaker_state = Gauge(
            "aria_llm_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["model"],
            registry=reg,
        )

        self.llm_thinking_duration = Histogram(
            "aria_llm_thinking_duration_seconds",
            "Duration of thinking/reasoning phase",
            ["model"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
            registry=reg,
        )

        # -- Agent metrics --
        self.agent_routing_total = Counter(
            "aria_agent_routing_total",
            "Total agent routing decisions",
            ["selected_agent"],
            registry=reg,
        )

        self.agent_routing_duration = Histogram(
            "aria_agent_routing_duration_seconds",
            "Time to make routing decision",
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
            registry=reg,
        )

        self.agent_pheromone_score = Gauge(
            "aria_agent_pheromone_score",
            "Current pheromone score for each agent",
            ["agent_id"],
            registry=reg,
        )

        self.agent_task_total = Counter(
            "aria_agent_tasks_total",
            "Total tasks executed by each agent",
            ["agent_id", "status"],
            registry=reg,
        )

        self.agent_active = Gauge(
            "aria_agents_active",
            "Number of active agents",
            registry=reg,
        )

        # -- Session metrics --
        self.sessions_active = Gauge(
            "aria_sessions_active",
            "Number of active sessions",
            registry=reg,
        )

        self.sessions_created_total = Counter(
            "aria_sessions_created_total",
            "Total sessions created",
            registry=reg,
        )

        self.sessions_messages_total = Counter(
            "aria_sessions_messages_total",
            "Total messages across all sessions",
            ["role"],
            registry=reg,
        )

        self.session_duration = Histogram(
            "aria_session_duration_seconds",
            "Session duration from creation to last message",
            buckets=[60, 300, 600, 1800, 3600, 7200, 86400],
            registry=reg,
        )

        # -- Scheduler metrics --
        self.scheduler_jobs_total = Gauge(
            "aria_scheduler_jobs_total",
            "Total registered scheduler jobs",
            ["status"],
            registry=reg,
        )

        self.scheduler_executions_total = Counter(
            "aria_scheduler_executions_total",
            "Total scheduler job executions",
            ["job_id", "status"],
            registry=reg,
        )

        self.scheduler_execution_duration = Histogram(
            "aria_scheduler_execution_duration_seconds",
            "Scheduler job execution duration",
            ["job_id"],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
            registry=reg,
        )

        self.scheduler_last_run = Gauge(
            "aria_scheduler_last_run_timestamp",
            "Unix timestamp of last successful run for each job",
            ["job_id"],
            registry=reg,
        )

        # -- Skill metrics --
        self.skill_execution_total = Counter(
            "aria_skill_executions_total",
            "Total skill executions",
            ["skill_name", "status"],
            registry=reg,
        )

        self.skill_execution_duration = Histogram(
            "aria_skill_execution_duration_seconds",
            "Skill execution duration",
            ["skill_name"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
            registry=reg,
        )

        # -- Database metrics --
        self.db_query_total = Counter(
            "aria_db_queries_total",
            "Total database queries",
            ["operation"],
            registry=reg,
        )

        self.db_query_duration = Histogram(
            "aria_db_query_duration_seconds",
            "Database query duration",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=reg,
        )

        self.db_pool_size = Gauge(
            "aria_db_pool_size",
            "Current database connection pool size",
            registry=reg,
        )

        self.db_pool_available = Gauge(
            "aria_db_pool_available",
            "Available database connections",
            registry=reg,
        )

        # -- Error metrics --
        self.errors_total = Counter(
            "aria_errors_total",
            "Total errors by type",
            ["error_type", "component"],
            registry=reg,
        )

        # -- Memory metrics --
        self.memory_rss_bytes = Gauge(
            "aria_memory_rss_bytes",
            "Resident Set Size in bytes",
            registry=reg,
        )

        self.memory_gc_objects = Gauge(
            "aria_memory_gc_objects",
            "Number of objects tracked by GC",
            registry=reg,
        )


# Singleton
METRICS = AriaMetrics()


# ---------------------------------------------------------------------------
# Helper decorators
# ---------------------------------------------------------------------------

def track_request(method: str):
    """Decorator to track request metrics."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            METRICS.request_in_progress.labels(method=method).inc()
            start = time.monotonic()
            status = "200"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "500"
                METRICS.errors_total.labels(
                    error_type=type(e).__name__,
                    component=method,
                ).inc()
                raise
            finally:
                duration = time.monotonic() - start
                METRICS.request_total.labels(method=method, status=status).inc()
                METRICS.request_duration.labels(method=method).observe(duration)
                METRICS.request_in_progress.labels(method=method).dec()
        return wrapper
    return decorator


def track_llm(model: str):
    """Decorator to track LLM call metrics."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                METRICS.errors_total.labels(
                    error_type=type(e).__name__,
                    component="llm",
                ).inc()
                raise
            finally:
                duration = time.monotonic() - start
                METRICS.llm_request_total.labels(model=model, status=status).inc()
                METRICS.llm_request_duration.labels(model=model).observe(duration)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Metrics server
# ---------------------------------------------------------------------------

async def start_metrics_server(port: int = 8081) -> None:
    """Start the Prometheus metrics HTTP server on a dedicated port."""
    start_http_server(port, registry=registry)
    print(f"Prometheus metrics server started on port {port}")

    # Set build info
    METRICS.build_info.info({
        "version": os.getenv("ARIA_VERSION", "2.0.0"),
        "python": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        "engine": "aria_engine",
    })


async def update_system_metrics() -> None:
    """Periodically update system-level metrics. Call every 30s."""
    import gc
    try:
        import psutil
        proc = psutil.Process()
        METRICS.memory_rss_bytes.set(proc.memory_info().rss)
    except ImportError:
        pass

    METRICS.memory_gc_objects.set(len(gc.get_objects()))
```

### `deploy/grafana/dashboards/aria_engine.json`
```json
{
  "dashboard": {
    "title": "Aria Engine - Production Dashboard",
    "uid": "aria-engine-prod",
    "timezone": "browser",
    "refresh": "30s",
    "panels": [
      {
        "title": "Request Rate (req/s)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "rate(aria_requests_total[5m])",
            "legendFormat": "{{method}} - {{status}}"
          }
        ]
      },
      {
        "title": "Request Duration (p95)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(aria_request_duration_seconds_bucket[5m]))",
            "legendFormat": "p95 {{method}}"
          }
        ]
      },
      {
        "title": "LLM Token Usage",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "targets": [
          {
            "expr": "rate(aria_llm_tokens_input_total[5m])",
            "legendFormat": "Input {{model}}"
          },
          {
            "expr": "rate(aria_llm_tokens_output_total[5m])",
            "legendFormat": "Output {{model}}"
          }
        ]
      },
      {
        "title": "LLM Latency (p95)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(aria_llm_request_duration_seconds_bucket[5m]))",
            "legendFormat": "p95 {{model}}"
          }
        ]
      },
      {
        "title": "Active Sessions",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 16},
        "targets": [
          {"expr": "aria_sessions_active"}
        ]
      },
      {
        "title": "Active Agents",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 6, "y": 16},
        "targets": [
          {"expr": "aria_agents_active"}
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 16},
        "targets": [
          {"expr": "rate(aria_errors_total[5m])"}
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"color": "green", "value": 0},
                {"color": "yellow", "value": 0.01},
                {"color": "red", "value": 0.1}
              ]
            }
          }
        }
      },
      {
        "title": "RSS Memory (MB)",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 18, "y": 16},
        "targets": [
          {"expr": "aria_memory_rss_bytes / 1024 / 1024"}
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "decmbytes",
            "thresholds": {
              "steps": [
                {"color": "green", "value": 0},
                {"color": "yellow", "value": 300},
                {"color": "red", "value": 450}
              ]
            }
          }
        }
      },
      {
        "title": "Agent Pheromone Scores",
        "type": "bargauge",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 20},
        "targets": [
          {"expr": "aria_agent_pheromone_score", "legendFormat": "{{agent_id}}"}
        ]
      },
      {
        "title": "Agent Routing Distribution",
        "type": "piechart",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 20},
        "targets": [
          {
            "expr": "increase(aria_agent_routing_total[1h])",
            "legendFormat": "{{selected_agent}}"
          }
        ]
      },
      {
        "title": "Scheduler Job Status",
        "type": "table",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 28},
        "targets": [
          {
            "expr": "aria_scheduler_last_run_timestamp",
            "format": "table",
            "legendFormat": "{{job_id}}"
          }
        ]
      },
      {
        "title": "DB Query Latency (p95)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 36},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(aria_db_query_duration_seconds_bucket[5m]))",
            "legendFormat": "{{operation}}"
          }
        ]
      },
      {
        "title": "DB Connection Pool",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 36},
        "targets": [
          {"expr": "aria_db_pool_size", "legendFormat": "Total"},
          {"expr": "aria_db_pool_available", "legendFormat": "Available"}
        ]
      }
    ]
  }
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Metrics on each layer |
| 2 | .env for secrets | ✅ | METRICS_PORT env var |
| 3 | models.yaml single source | ❌ | Metrics about models |
| 4 | Docker-first testing | ✅ | Port 8081 exposed |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- `pip install prometheus_client`
- Prometheus scrape config updated for port 8081
- Grafana datasource pointed at Prometheus

## Verification
```bash
# 1. Start metrics server:
python -c "import asyncio; from aria_engine.metrics import start_metrics_server; asyncio.run(start_metrics_server(8081))"

# 2. Check metrics endpoint:
curl http://localhost:8081/metrics | grep "aria_"
# EXPECTED: Multiple aria_* metrics lines

# 3. Verify Grafana dashboard imports:
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @deploy/grafana/dashboards/aria_engine.json

# 4. Run test to verify metrics work:
pytest tests/unit/test_metrics.py -v
```

## Prompt for Agent
```
Create the Prometheus metrics module and Grafana dashboard.

FILES TO READ FIRST:
- aria_engine/metrics.py (this ticket's output)
- stacks/brain/docker-compose.yml (prometheus, grafana services)
- deploy/grafana/ (existing dashboard configs)

STEPS:
1. Create aria_engine/metrics.py with all metric definitions
2. Create deploy/grafana/dashboards/aria_engine.json
3. Integrate metrics into: gateway.py, llm_gateway.py, agent_pool.py, scheduler.py
4. Expose on port 8081 via prometheus_client
5. Import dashboard into Grafana

METRICS TO IMPLEMENT:
- Request: total, duration, in_progress
- LLM: requests, tokens (in/out), duration, circuit breaker, thinking duration
- Agent: routing total, pheromone score, tasks, active count
- Session: active, created, messages, duration
- Scheduler: jobs total, executions, duration, last run
- Skill: executions, duration
- DB: queries, duration, pool size
- System: RSS memory, GC objects
- Errors: total by type and component
```
