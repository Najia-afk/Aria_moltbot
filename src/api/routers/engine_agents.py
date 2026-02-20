"""
Agent Management API — list, inspect, and manage agents.

Endpoints:
    GET  /api/engine/agents          — list all agents with status
    GET  /api/engine/agents/{id}     — get single agent detail
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aria_engine.agent_pool import AgentPool

logger = logging.getLogger("aria.api.engine_agents")

router = APIRouter(prefix="/engine/agents", tags=["engine-agents"])


class AgentSummary(BaseModel):
    agent_id: str
    display_name: str = ""
    model: str = ""
    status: str = "idle"
    focus_type: str | None = None
    current_session_id: str | None = None
    current_task: str | None = None
    pheromone_score: float = 0.5
    consecutive_failures: int = 0
    last_active_at: str | None = None
    context_length: int = 0


class AgentPoolStatus(BaseModel):
    total_agents: int
    max_concurrent: int
    status_counts: dict[str, int]
    agents: list[AgentSummary]


def get_pool() -> AgentPool:
    """
    Get the agent pool from the global engine instance.

    First tries the global engine. Falls back to creating a DB-backed
    pool for read operations (API-only mode where engine runs separately).
    """
    from aria_engine import get_engine

    engine = get_engine()
    if engine is not None and hasattr(engine, "agent_pool") and engine.agent_pool is not None:
        return engine.agent_pool

    # Fallback: create a DB-backed pool (read-only, loads agents from DB)
    from aria_engine.config import EngineConfig
    from sqlalchemy.ext.asyncio import create_async_engine

    config = EngineConfig()
    db_url = config.database_url
    for prefix in ("postgresql://", "postgresql+asyncpg://", "postgres://"):
        if db_url.startswith(prefix):
            db_url = db_url.replace(prefix, "postgresql+psycopg://", 1)
            break
    db = create_async_engine(db_url, pool_size=5, max_overflow=10)
    return AgentPool(config, db)


@router.get("", response_model=AgentPoolStatus)
async def list_agents(pool: AgentPool = Depends(get_pool)) -> AgentPoolStatus:
    """List all agents with their current status."""
    # Ensure agents are loaded (idempotent if already loaded)
    if not pool._agents:
        await pool.load_agents()
    status = pool.get_status()
    return AgentPoolStatus(**status)


@router.get("/{agent_id}", response_model=AgentSummary)
async def get_agent(
    agent_id: str,
    pool: AgentPool = Depends(get_pool),
) -> AgentSummary:
    """Get details for a single agent."""
    agent = pool.get_agent(agent_id)
    if agent is None:
        raise HTTPException(404, f"Agent {agent_id!r} not found")
    return AgentSummary(**agent.get_summary())
