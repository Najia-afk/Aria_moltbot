# S4-06: Agent Performance Dashboard
**Epic:** E3 — Agent Pool | **Priority:** P2 | **Points:** 3 | **Phase:** 3

## Problem
The existing `aria_mind/skill_health_dashboard.py` provides skill-level health metrics but has no visibility into individual agent performance. With the engine's agent pool (S4-01) and pheromone routing (S4-04), operators need a real-time dashboard showing per-agent metrics: messages processed, tokens used, average latency, error rate, uptime, and pheromone score trends. The dashboard should be accessible via the Flask web UI and backed by a FastAPI metrics endpoint.

Reference: `aria_mind/skill_health_dashboard.py` provides the pattern for health dashboards. `aria_engine/agent_pool.py` (S4-01) and `aria_engine/routing.py` (S4-04) provide the data sources.

## Root Cause
Agent metrics are currently scattered across logs, the pheromone scoring system, and the agent_state table. There's no unified view that aggregates per-agent performance data with trend visualization, making it impossible to identify degraded agents or validate routing decisions.

## Fix
### `src/api/routers/engine_agent_metrics.py`
```python
"""
Agent Performance Metrics API — per-agent stats and trends.

Provides:
- GET /api/engine/agents/metrics — all agents with current stats
- GET /api/engine/agents/metrics/{agent_id} — single agent detail
- GET /api/engine/agents/metrics/{agent_id}/history — score history
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from aria_engine.config import EngineConfig

logger = logging.getLogger("aria.api.agent_metrics")
router = APIRouter(
    prefix="/api/engine/agents/metrics",
    tags=["engine-agents"],
)


class AgentMetric(BaseModel):
    """Per-agent performance metric."""

    agent_id: str
    display_name: str
    focus_type: Optional[str] = None
    status: str = "idle"
    pheromone_score: float = 0.500
    messages_processed: int = 0
    total_tokens: int = 0
    avg_latency_ms: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    consecutive_failures: int = 0
    uptime_seconds: int = 0
    last_active_at: Optional[str] = None


class AgentMetricDetail(AgentMetric):
    """Extended metrics for single agent view."""

    recent_sessions: int = 0
    last_error: Optional[str] = None
    score_trend: List[float] = []


class AgentMetricsResponse(BaseModel):
    """Response with all agent metrics."""

    agents: List[AgentMetric]
    total_messages: int = 0
    total_errors: int = 0
    avg_pheromone: float = 0.0
    timestamp: str


async def _get_db():
    """Get database engine from config."""
    config = EngineConfig()
    return config.get_db_engine()


@router.get("", response_model=AgentMetricsResponse)
async def get_all_metrics():
    """Get performance metrics for all agents."""
    db = await _get_db()

    async with db.begin() as conn:
        # Core agent state
        result = await conn.execute(
            text("""
                SELECT
                    a.agent_id,
                    a.display_name,
                    a.focus_type,
                    a.status,
                    a.pheromone_score,
                    a.consecutive_failures,
                    a.last_active_at,
                    a.created_at,
                    COALESCE(m.msg_count, 0) AS messages_processed,
                    COALESCE(m.total_tokens, 0) AS total_tokens,
                    COALESCE(m.avg_latency_ms, 0) AS avg_latency_ms,
                    COALESCE(m.error_count, 0) AS error_count
                FROM aria_engine.agent_state a
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS msg_count,
                        SUM(COALESCE(
                            (metadata->>'token_count')::int, 0
                        )) AS total_tokens,
                        AVG(COALESCE(
                            (metadata->>'latency_ms')::int, 0
                        ))::int AS avg_latency_ms,
                        COUNT(*) FILTER (
                            WHERE metadata->>'error' IS NOT NULL
                        ) AS error_count
                    FROM aria_engine.chat_messages cm
                    WHERE cm.agent_id = a.agent_id
                ) m ON true
                ORDER BY a.pheromone_score DESC
            """)
        )
        rows = result.mappings().all()

    agents = []
    total_messages = 0
    total_errors = 0
    scores = []

    now = datetime.now(timezone.utc)

    for row in rows:
        msg_count = row["messages_processed"]
        err_count = row["error_count"]
        error_rate = (
            round(err_count / msg_count, 3) if msg_count > 0 else 0.0
        )

        created = row["created_at"]
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        uptime = (
            int((now - created).total_seconds()) if created else 0
        )

        score = float(row["pheromone_score"] or 0.5)
        scores.append(score)

        agents.append(
            AgentMetric(
                agent_id=row["agent_id"],
                display_name=row["display_name"] or row["agent_id"],
                focus_type=row["focus_type"],
                status=row["status"] or "idle",
                pheromone_score=score,
                messages_processed=msg_count,
                total_tokens=row["total_tokens"],
                avg_latency_ms=row["avg_latency_ms"],
                error_count=err_count,
                error_rate=error_rate,
                consecutive_failures=row["consecutive_failures"] or 0,
                uptime_seconds=uptime,
                last_active_at=(
                    row["last_active_at"].isoformat()
                    if row["last_active_at"]
                    else None
                ),
            )
        )
        total_messages += msg_count
        total_errors += err_count

    return AgentMetricsResponse(
        agents=agents,
        total_messages=total_messages,
        total_errors=total_errors,
        avg_pheromone=(
            round(sum(scores) / len(scores), 3) if scores else 0.0
        ),
        timestamp=now.isoformat(),
    )


@router.get("/{agent_id}", response_model=AgentMetricDetail)
async def get_agent_metrics(agent_id: str):
    """Get detailed metrics for a single agent."""
    db = await _get_db()

    async with db.begin() as conn:
        # Agent state
        result = await conn.execute(
            text("""
                SELECT * FROM aria_engine.agent_state
                WHERE agent_id = :agent_id
            """),
            {"agent_id": agent_id},
        )
        row = result.mappings().first()

        if not row:
            raise HTTPException(404, f"Agent {agent_id} not found")

        # Message stats
        stats = await conn.execute(
            text("""
                SELECT
                    COUNT(*) AS msg_count,
                    SUM(COALESCE(
                        (metadata->>'token_count')::int, 0
                    )) AS total_tokens,
                    AVG(COALESCE(
                        (metadata->>'latency_ms')::int, 0
                    ))::int AS avg_latency_ms,
                    COUNT(*) FILTER (
                        WHERE metadata->>'error' IS NOT NULL
                    ) AS error_count
                FROM aria_engine.chat_messages
                WHERE agent_id = :agent_id
            """),
            {"agent_id": agent_id},
        )
        msg_row = stats.mappings().first()

        # Recent sessions
        sessions = await conn.execute(
            text("""
                SELECT COUNT(DISTINCT session_id) AS cnt
                FROM aria_engine.chat_messages
                WHERE agent_id = :agent_id
                  AND created_at > NOW() - INTERVAL '24 hours'
            """),
            {"agent_id": agent_id},
        )
        session_row = sessions.mappings().first()

        # Last error
        last_err = await conn.execute(
            text("""
                SELECT metadata->>'error' AS error_msg
                FROM aria_engine.chat_messages
                WHERE agent_id = :agent_id
                  AND metadata->>'error' IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"agent_id": agent_id},
        )
        err_row = last_err.mappings().first()

    msg_count = msg_row["msg_count"] if msg_row else 0
    err_count = msg_row["error_count"] if msg_row else 0

    now = datetime.now(timezone.utc)
    created = row["created_at"]
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    uptime = int((now - created).total_seconds()) if created else 0

    return AgentMetricDetail(
        agent_id=row["agent_id"],
        display_name=row["display_name"] or row["agent_id"],
        focus_type=row["focus_type"],
        status=row["status"] or "idle",
        pheromone_score=float(row["pheromone_score"] or 0.5),
        messages_processed=msg_count,
        total_tokens=msg_row["total_tokens"] if msg_row else 0,
        avg_latency_ms=msg_row["avg_latency_ms"] if msg_row else 0,
        error_count=err_count,
        error_rate=(
            round(err_count / msg_count, 3) if msg_count > 0 else 0.0
        ),
        consecutive_failures=row["consecutive_failures"] or 0,
        uptime_seconds=uptime,
        last_active_at=(
            row["last_active_at"].isoformat()
            if row["last_active_at"]
            else None
        ),
        recent_sessions=session_row["cnt"] if session_row else 0,
        last_error=err_row["error_msg"] if err_row else None,
        score_trend=[],  # Populated by /history endpoint
    )


@router.get("/{agent_id}/history")
async def get_agent_score_history(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=90),
):
    """Get pheromone score history for trend charting."""
    db = await _get_db()

    async with db.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    DATE_TRUNC('hour', created_at) AS bucket,
                    AVG(COALESCE(
                        (metadata->>'pheromone_score')::numeric, 0.5
                    ))::numeric(5,3) AS avg_score,
                    COUNT(*) AS interactions
                FROM aria_engine.chat_messages
                WHERE agent_id = :agent_id
                  AND created_at > NOW() - MAKE_INTERVAL(days => :days)
                GROUP BY bucket
                ORDER BY bucket
            """),
            {"agent_id": agent_id, "days": days},
        )
        rows = result.mappings().all()

    return {
        "agent_id": agent_id,
        "days": days,
        "data_points": [
            {
                "timestamp": row["bucket"].isoformat(),
                "score": float(row["avg_score"]),
                "interactions": row["interactions"],
            }
            for row in rows
        ],
    }
```

### `src/web/templates/engine_agent_dashboard.html`
```html
{% extends "base.html" %}
{% block title %}Agent Performance Dashboard{% endblock %}
{% block content %}
<div class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h4 class="mb-0">🐜 Agent Performance Dashboard</h4>
        <div>
            <span id="lastUpdate" class="text-muted small me-3"></span>
            <button class="btn btn-sm btn-outline-primary" onclick="loadMetrics()">
                ↻ Refresh
            </button>
        </div>
    </div>

    <!-- Summary Cards -->
    <div class="row g-3 mb-4">
        <div class="col-md-3">
            <div class="card text-center">
                <div class="card-body">
                    <h6 class="text-muted">Active Agents</h6>
                    <h2 id="activeCount" class="mb-0">-</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-center">
                <div class="card-body">
                    <h6 class="text-muted">Messages Processed</h6>
                    <h2 id="totalMessages" class="mb-0">-</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-center">
                <div class="card-body">
                    <h6 class="text-muted">Error Rate</h6>
                    <h2 id="errorRate" class="mb-0">-</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-center">
                <div class="card-body">
                    <h6 class="text-muted">Avg Pheromone</h6>
                    <h2 id="avgPheromone" class="mb-0">-</h2>
                </div>
            </div>
        </div>
    </div>

    <!-- Agent Cards -->
    <div class="row g-3" id="agentCards">
        <!-- Populated by JS -->
    </div>
</div>

<script>
const API = '/api/engine/agents/metrics';

function statusBadge(status) {
    const colors = {
        idle: 'success', busy: 'warning',
        error: 'danger', disabled: 'secondary'
    };
    return `<span class="badge bg-${colors[status] || 'secondary'}">${status}</span>`;
}

function scoreColor(score) {
    if (score >= 0.7) return 'success';
    if (score >= 0.4) return 'warning';
    return 'danger';
}

function formatUptime(seconds) {
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d`;
}

function renderAgent(a) {
    const sc = scoreColor(a.pheromone_score);
    return `
    <div class="col-md-6 col-lg-4">
        <div class="card h-100">
            <div class="card-header d-flex justify-content-between align-items-center">
                <strong>${a.display_name}</strong>
                ${statusBadge(a.status)}
            </div>
            <div class="card-body">
                <div class="row text-center mb-3">
                    <div class="col-4">
                        <small class="text-muted d-block">Pheromone</small>
                        <span class="badge bg-${sc} fs-6">${a.pheromone_score.toFixed(3)}</span>
                    </div>
                    <div class="col-4">
                        <small class="text-muted d-block">Messages</small>
                        <strong>${a.messages_processed.toLocaleString()}</strong>
                    </div>
                    <div class="col-4">
                        <small class="text-muted d-block">Errors</small>
                        <strong class="${a.error_rate > 0.1 ? 'text-danger' : ''}">${(a.error_rate * 100).toFixed(1)}%</strong>
                    </div>
                </div>
                <div class="row text-center">
                    <div class="col-4">
                        <small class="text-muted d-block">Avg Latency</small>
                        <strong>${a.avg_latency_ms}ms</strong>
                    </div>
                    <div class="col-4">
                        <small class="text-muted d-block">Tokens</small>
                        <strong>${a.total_tokens.toLocaleString()}</strong>
                    </div>
                    <div class="col-4">
                        <small class="text-muted d-block">Uptime</small>
                        <strong>${formatUptime(a.uptime_seconds)}</strong>
                    </div>
                </div>
                ${a.focus_type ? `<div class="mt-2"><small class="text-muted">Focus: ${a.focus_type}</small></div>` : ''}
                ${a.consecutive_failures > 0 ? `<div class="mt-1"><small class="text-danger">⚠ ${a.consecutive_failures} consecutive failures</small></div>` : ''}
            </div>
            <div class="card-footer text-muted small">
                Last active: ${a.last_active_at ? new Date(a.last_active_at).toLocaleString() : 'Never'}
            </div>
        </div>
    </div>`;
}

async function loadMetrics() {
    try {
        const resp = await fetch(API);
        const data = await resp.json();

        document.getElementById('activeCount').textContent =
            data.agents.filter(a => a.status !== 'disabled').length;
        document.getElementById('totalMessages').textContent =
            data.total_messages.toLocaleString();
        const errRate = data.total_messages > 0
            ? ((data.total_errors / data.total_messages) * 100).toFixed(1) + '%'
            : '0%';
        document.getElementById('errorRate').textContent = errRate;
        document.getElementById('avgPheromone').textContent =
            data.avg_pheromone.toFixed(3);
        document.getElementById('lastUpdate').textContent =
            'Updated: ' + new Date().toLocaleTimeString();

        document.getElementById('agentCards').innerHTML =
            data.agents.map(renderAgent).join('');
    } catch (e) {
        console.error('Failed to load metrics:', e);
    }
}

loadMetrics();
setInterval(loadMetrics, 30000);
</script>
{% endblock %}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API router at API layer, template at web layer |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from config |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL for metrics queries |
| 5 | aria_memories only writable path | ❌ | Read-only dashboard |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S4-01 (AgentPool — agent_state table with metrics)
- S4-04 (Pheromone Routing — pheromone_score updates)
- S1-03 (FastAPI app — router registration)
- S1-04 (Flask dashboard — template base)

## Verification
```bash
# 1. API imports:
python -c "
from src.api.routers.engine_agent_metrics import router, AgentMetric, AgentMetricsResponse
print(f'Routes: {len(router.routes)}')
"
# EXPECTED: Routes: 3

# 2. Schema validation:
python -c "
from src.api.routers.engine_agent_metrics import AgentMetric
m = AgentMetric(
    agent_id='test', display_name='Test Agent', status='idle',
    pheromone_score=0.750, messages_processed=100, total_tokens=5000,
    avg_latency_ms=200, error_count=5, error_rate=0.05,
)
print(m.model_dump_json(indent=2))
"
# EXPECTED: Valid JSON with all fields

# 3. Template exists:
python -c "
import os
assert os.path.exists('src/web/templates/engine_agent_dashboard.html')
print('Template OK')
"
# EXPECTED: Template OK
```

## Prompt for Agent
```
Create an agent performance dashboard with API and web UI.

FILES TO READ FIRST:
- aria_mind/skill_health_dashboard.py (pattern for health dashboards)
- aria_engine/agent_pool.py (S4-01 — AgentPool, agent_state table structure)
- aria_engine/routing.py (S4-04 — pheromone scores and routing table)
- src/web/templates/engine_agents.html (S4-03 — existing agent UI for consistency)
- src/api/routers/engine_agents.py (S4-03 — existing agent API for patterns)

STEPS:
1. Read all files above
2. Create src/api/routers/engine_agent_metrics.py with 3 endpoints
3. GET /api/engine/agents/metrics — all agents with aggregated stats
4. GET /api/engine/agents/metrics/{agent_id} — single agent detail
5. GET /api/engine/agents/metrics/{agent_id}/history — score trend data
6. Create src/web/templates/engine_agent_dashboard.html
7. Summary cards: active count, total messages, error rate, avg pheromone
8. Per-agent cards: score (color-coded), messages, errors, latency, tokens, uptime
9. Auto-refresh every 30 seconds
10. Register router in FastAPI app, add Flask route for dashboard
11. Run verification commands

CONSTRAINTS:
- Metrics aggregated from chat_messages and agent_state tables
- No new tables — uses existing schema
- Cards color-coded by pheromone score (green ≥0.7, yellow ≥0.4, red <0.4)
- Auto-refresh every 30s via setInterval
```
