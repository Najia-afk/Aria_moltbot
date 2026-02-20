"""
Agent Performance Metrics API — per-agent stats and trends.

Provides:
- GET /api/engine/agents/metrics — all agents with current stats
- GET /api/engine/agents/metrics/{agent_id} — single agent detail
- GET /api/engine/agents/metrics/{agent_id}/history — score history
"""
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from aria_engine.config import EngineConfig

logger = logging.getLogger("aria.api.agent_metrics")
router = APIRouter(
    prefix="/engine/agents/metrics",
    tags=["engine-agents"],
)


class AgentMetric(BaseModel):
    """Per-agent performance metric."""

    agent_id: str
    display_name: str
    focus_type: str | None = None
    status: str = "idle"
    pheromone_score: float = 0.500
    messages_processed: int = 0
    total_tokens: int = 0
    avg_latency_ms: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    consecutive_failures: int = 0
    uptime_seconds: int = 0
    last_active_at: str | None = None


class AgentMetricDetail(AgentMetric):
    """Extended metrics for single agent view."""

    recent_sessions: int = 0
    last_error: str | None = None
    score_trend: list[float] = []


class AgentMetricsResponse(BaseModel):
    """Response with all agent metrics."""

    agents: list[AgentMetric]
    total_messages: int = 0
    total_errors: int = 0
    avg_pheromone: float = 0.0
    timestamp: str


async def _get_db():
    """Get database engine from config."""
    from sqlalchemy.ext.asyncio import create_async_engine

    config = EngineConfig()
    db_url = config.database_url
    # Use psycopg3 driver (same as the rest of the API)
    for prefix in ("postgresql://", "postgresql+asyncpg://", "postgres://"):
        if db_url.startswith(prefix):
            db_url = db_url.replace(prefix, "postgresql+psycopg://", 1)
            break
    return create_async_engine(db_url, pool_size=5, max_overflow=10)


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
                    JOIN aria_engine.chat_sessions cs ON cs.id = cm.session_id
                    WHERE cs.agent_id = a.agent_id
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
        if created and hasattr(created, "tzinfo") and created.tzinfo is None:
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
                FROM aria_engine.chat_messages cm
                JOIN aria_engine.chat_sessions cs ON cs.id = cm.session_id
                WHERE cs.agent_id = :agent_id
            """),
            {"agent_id": agent_id},
        )
        msg_row = stats.mappings().first()

        # Recent sessions
        sessions = await conn.execute(
            text("""
                SELECT COUNT(DISTINCT id) AS cnt
                FROM aria_engine.chat_sessions
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
                FROM aria_engine.chat_messages cm
                JOIN aria_engine.chat_sessions cs ON cs.id = cm.session_id
                WHERE cs.agent_id = :agent_id
                  AND metadata->>'error' IS NOT NULL
                ORDER BY cm.created_at DESC
                LIMIT 1
            """),
            {"agent_id": agent_id},
        )
        err_row = last_err.mappings().first()

    msg_count = msg_row["msg_count"] if msg_row else 0
    err_count = msg_row["error_count"] if msg_row else 0

    now = datetime.now(timezone.utc)
    created = row["created_at"]
    if created and hasattr(created, "tzinfo") and created.tzinfo is None:
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
                    DATE_TRUNC('hour', cm.created_at) AS bucket,
                    AVG(COALESCE(
                        (cm.metadata->>'pheromone_score')::numeric, 0.5
                    ))::numeric(5,3) AS avg_score,
                    COUNT(*) AS interactions
                FROM aria_engine.chat_messages cm
                JOIN aria_engine.chat_sessions cs ON cs.id = cm.session_id
                WHERE cs.agent_id = :agent_id
                  AND cm.created_at > NOW() - MAKE_INTERVAL(days => :days)
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
