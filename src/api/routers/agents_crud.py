"""
Agent CRUD Router — manage the agent catalog stored in ``aria_engine.agent_state``.

Endpoints:
  GET    /agents/db                    — list all agents (with filtering)
  GET    /agents/db/{agent_id}         — get one agent
  POST   /agents/db                    — create a new agent
  PUT    /agents/db/{agent_id}         — update an agent
  DELETE /agents/db/{agent_id}         — delete an agent
  POST   /agents/db/{agent_id}/enable  — enable agent
  POST   /agents/db/{agent_id}/disable — disable agent
  POST   /agents/db/sync              — re-sync from AGENTS.md → DB
"""
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func

logger = logging.getLogger("aria.api.agents_crud")

router = APIRouter(tags=["Agents DB"])


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(default="", max_length=200)
    agent_type: str = Field(default="agent", max_length=30)
    parent_agent_id: str | None = None
    model: str = Field(..., min_length=1, max_length=200)
    fallback_model: str | None = None
    temperature: float = 0.7
    max_tokens: int = Field(default=4096, ge=1)
    system_prompt: str | None = None
    focus_type: str | None = None
    skills: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True
    timeout_seconds: int = 600
    rate_limit: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    display_name: str | None = None
    agent_type: str | None = None
    parent_agent_id: str | None = None
    model: str | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None
    focus_type: str | None = None
    skills: list[str] | None = None
    capabilities: list[str] | None = None
    enabled: bool | None = None
    status: str | None = None
    timeout_seconds: int | None = None
    rate_limit: dict | None = None
    metadata: dict | None = None


class AgentResponse(BaseModel):
    agent_id: str
    display_name: str
    agent_type: str
    parent_agent_id: str | None
    model: str
    fallback_model: str | None
    temperature: float
    max_tokens: int
    system_prompt: str | None
    focus_type: str | None
    status: str
    enabled: bool
    skills: list[str]
    capabilities: list[str]
    current_session_id: str | None
    current_task: str | None
    consecutive_failures: int
    pheromone_score: float
    timeout_seconds: int
    rate_limit: dict
    last_active_at: str | None
    metadata: dict
    created_at: str | None
    updated_at: str | None


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_db():
    try:
        from db import AsyncSessionLocal
    except ImportError:
        from .db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        yield db


def _row_to_response(row) -> AgentResponse:
    return AgentResponse(
        agent_id=row.agent_id,
        display_name=row.display_name or "",
        agent_type=getattr(row, "agent_type", None) or "agent",
        parent_agent_id=getattr(row, "parent_agent_id", None),
        model=row.model,
        fallback_model=getattr(row, "fallback_model", None),
        temperature=float(row.temperature or 0.7),
        max_tokens=row.max_tokens or 4096,
        system_prompt=row.system_prompt,
        focus_type=row.focus_type,
        status=row.status or "idle",
        enabled=getattr(row, "enabled", True) if hasattr(row, "enabled") else True,
        skills=getattr(row, "skills", None) or [],
        capabilities=getattr(row, "capabilities", None) or [],
        current_session_id=str(row.current_session_id) if row.current_session_id else None,
        current_task=row.current_task,
        consecutive_failures=row.consecutive_failures or 0,
        pheromone_score=float(row.pheromone_score or 0.5),
        timeout_seconds=getattr(row, "timeout_seconds", None) or 600,
        rate_limit=getattr(row, "rate_limit", None) or {},
        last_active_at=row.last_active_at.isoformat() if row.last_active_at else None,
        metadata=row.metadata_json if hasattr(row, "metadata_json") else (getattr(row, "metadata", None) or {}),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/agents/db", response_model=list[AgentResponse])
async def list_agents_db(
    agent_type: str | None = Query(default=None, description="Filter by type: agent, sub_agent, sub_aria, swarm, focus"),
    focus_type: str | None = Query(default=None, description="Filter by focus type"),
    status: str | None = Query(default=None, description="Filter by status: idle, busy, error, disabled"),
    enabled: bool | None = Query(default=None, description="Filter by enabled state"),
    parent: str | None = Query(default=None, description="Filter by parent agent ID"),
):
    """List all agents from DB, with optional filtering."""
    from db.models import EngineAgentState

    async for db in _get_db():
        q = select(EngineAgentState).order_by(
            EngineAgentState.agent_id.asc(),
        )
        if agent_type is not None:
            q = q.where(EngineAgentState.agent_type == agent_type)
        if focus_type is not None:
            q = q.where(EngineAgentState.focus_type == focus_type)
        if status is not None:
            q = q.where(EngineAgentState.status == status)
        if enabled is not None:
            q = q.where(EngineAgentState.enabled == enabled)
        if parent is not None:
            q = q.where(EngineAgentState.parent_agent_id == parent)

        result = await db.execute(q)
        rows = result.scalars().all()
        return [_row_to_response(r) for r in rows]


@router.get("/agents/db/{agent_id}", response_model=AgentResponse)
async def get_agent_db(agent_id: str):
    """Get a single agent by ID."""
    from db.models import EngineAgentState

    async for db in _get_db():
        result = await db.execute(
            select(EngineAgentState).where(EngineAgentState.agent_id == agent_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        return _row_to_response(row)


@router.post("/agents/db", response_model=AgentResponse, status_code=201)
async def create_agent_db(body: AgentCreate):
    """Create a new agent entry."""
    from db.models import EngineAgentState

    async for db in _get_db():
        existing = await db.execute(
            select(EngineAgentState).where(EngineAgentState.agent_id == body.agent_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, f"Agent '{body.agent_id}' already exists")

        row = EngineAgentState(
            agent_id=body.agent_id,
            display_name=body.display_name,
            agent_type=body.agent_type,
            parent_agent_id=body.parent_agent_id,
            model=body.model,
            fallback_model=body.fallback_model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            system_prompt=body.system_prompt,
            focus_type=body.focus_type,
            skills=body.skills,
            capabilities=body.capabilities,
            enabled=body.enabled,
            timeout_seconds=body.timeout_seconds,
            rate_limit=body.rate_limit,
            metadata_json=body.metadata,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row_to_response(row)


@router.put("/agents/db/{agent_id}", response_model=AgentResponse)
async def update_agent_db(agent_id: str, body: AgentUpdate):
    """Update an existing agent. Only provided fields are changed."""
    from db.models import EngineAgentState

    async for db in _get_db():
        result = await db.execute(
            select(EngineAgentState).where(EngineAgentState.agent_id == agent_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")

        updates = body.model_dump(exclude_unset=True)
        # Map 'metadata' to 'metadata_json' column name
        if "metadata" in updates:
            updates["metadata_json"] = updates.pop("metadata")
        for k, v in updates.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _row_to_response(row)


@router.delete("/agents/db/{agent_id}")
async def delete_agent_db(agent_id: str):
    """Delete an agent entry."""
    from db.models import EngineAgentState

    async for db in _get_db():
        result = await db.execute(
            select(EngineAgentState).where(EngineAgentState.agent_id == agent_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        await db.delete(row)
        await db.commit()
        return {"status": "deleted", "agent_id": agent_id}


@router.post("/agents/db/{agent_id}/enable")
async def enable_agent(agent_id: str):
    """Enable an agent."""
    from db.models import EngineAgentState

    async for db in _get_db():
        result = await db.execute(
            select(EngineAgentState).where(EngineAgentState.agent_id == agent_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        row.enabled = True
        row.status = "idle"
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "enabled", "agent_id": agent_id}


@router.post("/agents/db/{agent_id}/disable")
async def disable_agent(agent_id: str):
    """Disable an agent."""
    from db.models import EngineAgentState

    async for db in _get_db():
        result = await db.execute(
            select(EngineAgentState).where(EngineAgentState.agent_id == agent_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        row.enabled = False
        row.status = "disabled"
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "disabled", "agent_id": agent_id}


@router.post("/agents/db/sync")
async def sync_agents_from_md():
    """Sync agents from AGENTS.md → DB (upsert)."""
    try:
        from agents_sync import sync_agents_from_markdown
    except ImportError:
        from .agents_sync import sync_agents_from_markdown
    try:
        from db import AsyncSessionLocal
    except ImportError:
        from .db import AsyncSessionLocal

    stats = await sync_agents_from_markdown(AsyncSessionLocal)
    return {"status": "synced", **stats}
