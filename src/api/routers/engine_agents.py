"""
Agent Management API — list, inspect, and manage agents.

Endpoints:
    GET  /api/engine/agents          — list all agents with status
    GET  /api/engine/agents/{id}     — get single agent detail
"""
import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aria_engine.agent_pool import AgentPool

logger = logging.getLogger("aria.api.engine_agents")

router = APIRouter(prefix="/engine/agents", tags=["engine-agents"])

# ── Cached fallback pool (avoids creating a new DB engine per request) ────
_fallback_pool: AgentPool | None = None
_fallback_pool_lock = None  # initialized lazily


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
    system_prompt: str = ""
    skills: list[str] = []
    enabled: bool = True


class AgentUpdate(BaseModel):
    """Fields that can be patched on a live agent."""
    model: str | None = None
    system_prompt: str | None = None
    focus_type: str | None = None
    temperature: float | None = None
    skills: list[str] | None = None


class AgentPoolStatus(BaseModel):
    total_agents: int
    max_concurrent: int
    status_counts: dict[str, int]
    agents: list[AgentSummary]


class DelegateRequest(BaseModel):
    """Request to delegate a task to a specific agent."""
    agent_id: str
    message: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


class DelegateResponse(BaseModel):
    """Response from a delegated agent task."""
    agent_id: str
    session_id: str | None = None
    response: str = ""
    status: str = "completed"
    duration_ms: int = 0
    metadata: dict[str, Any] | None = None


def get_pool() -> AgentPool:
    """
    Get the agent pool from the global engine instance.

    First tries the global engine. Falls back to a **cached** DB-backed
    pool for read operations (API-only mode where engine runs separately).
    """
    global _fallback_pool, _fallback_pool_lock

    from aria_engine import get_engine

    engine = get_engine()
    if engine is not None and hasattr(engine, "agent_pool") and engine.agent_pool is not None:
        return engine.agent_pool

    # Return cached fallback pool if available
    if _fallback_pool is not None:
        return _fallback_pool

    # Create once and cache
    from aria_engine.config import EngineConfig
    from sqlalchemy.ext.asyncio import create_async_engine

    config = EngineConfig()
    db_url = config.database_url
    # Ensure we use psycopg async driver
    for prefix in ("postgresql://", "postgresql+asyncpg://", "postgres://"):
        if db_url.startswith(prefix):
            db_url = db_url.replace(prefix, "postgresql+psycopg://", 1)
            break
    db = create_async_engine(db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
    _fallback_pool = AgentPool(config, db)
    logger.info("Created cached fallback AgentPool (API-only mode)")
    return _fallback_pool


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


@router.patch("/{agent_id}", response_model=AgentSummary)
async def update_agent(
    agent_id: str,
    body: AgentUpdate,
    pool: AgentPool = Depends(get_pool),
) -> AgentSummary:
    """Patch config fields on a live agent (model, prompt, focus, temperature, skills)."""
    try:
        agent = await pool.update_agent_config(
            agent_id,
            model=body.model,
            system_prompt=body.system_prompt,
            focus_type=body.focus_type,
            temperature=body.temperature,
            skills=body.skills,
        )
        return AgentSummary(**agent.get_summary())
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/delegate", response_model=DelegateResponse)
async def delegate_task(
    req: DelegateRequest,
    pool: AgentPool = Depends(get_pool),
) -> DelegateResponse:
    """Delegate a task to a specific agent (S-11).

    Sends a message to the target agent via the pool's process_with_agent()
    method and returns the result.
    """
    import time

    if not pool._agents:
        await pool.load_agents()

    agent = pool.get_agent(req.agent_id)
    if agent is None:
        raise HTTPException(404, f"Agent {req.agent_id!r} not found")

    kwargs: dict[str, Any] = {}
    if req.session_id:
        kwargs["session_id"] = req.session_id
    if req.context:
        kwargs["context"] = req.context

    t0 = time.perf_counter()
    try:
        result = await pool.process_with_agent(req.agent_id, req.message, **kwargs)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return DelegateResponse(
            agent_id=req.agent_id,
            session_id=result.get("session_id") or req.session_id,
            response=result.get("response", result.get("content", "")),
            status="completed",
            duration_ms=duration_ms,
            metadata=result.get("metadata"),
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.warning("Delegate to %s failed: %s", req.agent_id, exc)
        raise HTTPException(502, f"Agent delegation failed: {exc}") from exc
