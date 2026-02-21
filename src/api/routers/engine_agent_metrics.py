"""
Agent Performance Metrics API — per-agent stats and trends.

Provides:
- GET /api/engine/agents/metrics — all agents with current stats
- GET /api/engine/agents/metrics/{agent_id} — single agent detail
- GET /api/engine/agents/metrics/{agent_id}/history — score history

Architecture: Pure SQLAlchemy ORM — zero raw SQL.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, cast, Integer, Numeric
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from aria_engine.config import EngineConfig

try:
    from db.models import EngineAgentState, EngineChatMessage, EngineChatSession
except ImportError:
    from .db.models import EngineAgentState, EngineChatMessage, EngineChatSession

logger = logging.getLogger("aria.api.agent_metrics")
router = APIRouter(
    prefix="/engine/agents/metrics",
    tags=["engine-agents"],
)


# ── Pydantic response models ────────────────────────────────────────────────

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


# ── DB helper ────────────────────────────────────────────────────────────────

_engine_cache = None


async def _get_db_engine():
    """Get or create a cached async engine (psycopg3 driver)."""
    global _engine_cache
    if _engine_cache is not None:
        return _engine_cache

    config = EngineConfig()
    db_url = config.database_url
    for prefix in ("postgresql://", "postgresql+asyncpg://", "postgres://"):
        if db_url.startswith(prefix):
            db_url = db_url.replace(prefix, "postgresql+psycopg://", 1)
            break
    _engine_cache = create_async_engine(db_url, pool_size=5, max_overflow=10)
    return _engine_cache


async def _msg_stats_for_agent(db: AsyncSession, agent_id: str | None = None):
    """Compute message stats per agent using ORM joins.

    Returns dict keyed by agent_id with msg_count, total_tokens, avg_latency_ms, error_count.
    If agent_id is given, filters to that single agent.
    """
    # Join messages → sessions to get agent_id
    query = (
        select(
            EngineChatSession.agent_id.label("agent_id"),
            func.count(EngineChatMessage.id).label("msg_count"),
            func.coalesce(
                func.sum(
                    cast(
                        EngineChatMessage.metadata_json["token_count"].as_string(),
                        Integer,
                    )
                ),
                0,
            ).label("total_tokens"),
            func.coalesce(
                cast(
                    func.avg(
                        cast(
                            EngineChatMessage.metadata_json["latency_ms"].as_string(),
                            Integer,
                        )
                    ),
                    Integer,
                ),
                0,
            ).label("avg_latency_ms"),
            func.count(
                case(
                    (EngineChatMessage.metadata_json["error"].as_string().is_not(None), 1),
                )
            ).label("error_count"),
        )
        .join(EngineChatSession, EngineChatSession.id == EngineChatMessage.session_id)
        .group_by(EngineChatSession.agent_id)
    )

    if agent_id is not None:
        query = query.where(EngineChatSession.agent_id == agent_id)

    result = await db.execute(query)
    return {row.agent_id: row._mapping for row in result.all()}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=AgentMetricsResponse)
async def get_all_metrics():
    """Get performance metrics for all agents."""
    engine = await _get_db_engine()
    now = datetime.now(timezone.utc)

    async with AsyncSession(engine) as db:
        # All agents ordered by pheromone score
        agent_rows = (
            await db.execute(
                select(EngineAgentState).order_by(EngineAgentState.pheromone_score.desc())
            )
        ).scalars().all()

        # Aggregate message stats per agent
        stats_map = await _msg_stats_for_agent(db)

    agents: list[AgentMetric] = []
    total_messages = 0
    total_errors = 0
    scores: list[float] = []

    for agent in agent_rows:
        stats = stats_map.get(agent.agent_id, {})
        msg_count = int(stats.get("msg_count", 0))
        err_count = int(stats.get("error_count", 0))
        error_rate = round(err_count / msg_count, 3) if msg_count > 0 else 0.0

        created = agent.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        uptime = int((now - created).total_seconds()) if created else 0

        score = float(agent.pheromone_score or 0.5)
        scores.append(score)

        agents.append(
            AgentMetric(
                agent_id=agent.agent_id,
                display_name=agent.display_name or agent.agent_id,
                focus_type=agent.focus_type,
                status=agent.status or "idle",
                pheromone_score=score,
                messages_processed=msg_count,
                total_tokens=int(stats.get("total_tokens", 0)),
                avg_latency_ms=int(stats.get("avg_latency_ms", 0)),
                error_count=err_count,
                error_rate=error_rate,
                consecutive_failures=agent.consecutive_failures or 0,
                uptime_seconds=uptime,
                last_active_at=agent.last_active_at.isoformat() if agent.last_active_at else None,
            )
        )
        total_messages += msg_count
        total_errors += err_count

    return AgentMetricsResponse(
        agents=agents,
        total_messages=total_messages,
        total_errors=total_errors,
        avg_pheromone=round(sum(scores) / len(scores), 3) if scores else 0.0,
        timestamp=now.isoformat(),
    )


@router.get("/{agent_id}", response_model=AgentMetricDetail)
async def get_agent_metrics(agent_id: str):
    """Get detailed metrics for a single agent."""
    engine = await _get_db_engine()
    now = datetime.now(timezone.utc)

    async with AsyncSession(engine) as db:
        # Agent state
        agent = (
            await db.execute(
                select(EngineAgentState).where(EngineAgentState.agent_id == agent_id)
            )
        ).scalar_one_or_none()

        if not agent:
            raise HTTPException(404, f"Agent {agent_id} not found")

        # Message stats
        stats_map = await _msg_stats_for_agent(db, agent_id=agent_id)
        stats = stats_map.get(agent_id, {})

        # Recent sessions (last 24h)
        recent_count_result = await db.execute(
            select(func.count(EngineChatSession.id)).where(
                EngineChatSession.agent_id == agent_id,
                EngineChatSession.created_at > now - timedelta(hours=24),
            )
        )
        recent_sessions = recent_count_result.scalar() or 0

        # Last error from messages metadata
        last_err_result = await db.execute(
            select(EngineChatMessage.metadata_json["error"].as_string())
            .join(EngineChatSession, EngineChatSession.id == EngineChatMessage.session_id)
            .where(
                EngineChatSession.agent_id == agent_id,
                EngineChatMessage.metadata_json["error"].as_string().is_not(None),
            )
            .order_by(EngineChatMessage.created_at.desc())
            .limit(1)
        )
        last_error = last_err_result.scalar_one_or_none()

    msg_count = int(stats.get("msg_count", 0))
    err_count = int(stats.get("error_count", 0))

    created = agent.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    uptime = int((now - created).total_seconds()) if created else 0

    return AgentMetricDetail(
        agent_id=agent.agent_id,
        display_name=agent.display_name or agent.agent_id,
        focus_type=agent.focus_type,
        status=agent.status or "idle",
        pheromone_score=float(agent.pheromone_score or 0.5),
        messages_processed=msg_count,
        total_tokens=int(stats.get("total_tokens", 0)),
        avg_latency_ms=int(stats.get("avg_latency_ms", 0)),
        error_count=err_count,
        error_rate=round(err_count / msg_count, 3) if msg_count > 0 else 0.0,
        consecutive_failures=agent.consecutive_failures or 0,
        uptime_seconds=uptime,
        last_active_at=agent.last_active_at.isoformat() if agent.last_active_at else None,
        recent_sessions=recent_sessions,
        last_error=last_error,
        score_trend=[],  # Populated by /history endpoint
    )


@router.get("/{agent_id}/history")
async def get_agent_score_history(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=90),
):
    """Get pheromone score history for trend charting."""
    engine = await _get_db_engine()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # date_trunc via func
    bucket = func.date_trunc("hour", EngineChatMessage.created_at).label("bucket")

    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(
                bucket,
                func.coalesce(
                    cast(
                        func.avg(
                            cast(
                                EngineChatMessage.metadata_json["pheromone_score"].as_string(),
                                Numeric,
                            )
                        ),
                        Numeric(5, 3),
                    ),
                    0.5,
                ).label("avg_score"),
                func.count().label("interactions"),
            )
            .join(EngineChatSession, EngineChatSession.id == EngineChatMessage.session_id)
            .where(
                EngineChatSession.agent_id == agent_id,
                EngineChatMessage.created_at > cutoff,
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        rows = result.all()

    return {
        "agent_id": agent_id,
        "days": days,
        "data_points": [
            {
                "timestamp": row.bucket.isoformat(),
                "score": float(row.avg_score),
                "interactions": row.interactions,
            }
            for row in rows
        ],
    }
