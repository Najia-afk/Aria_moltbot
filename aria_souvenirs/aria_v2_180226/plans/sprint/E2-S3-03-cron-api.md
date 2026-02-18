# S3-03: Cron CRUD API Endpoints
**Epic:** E2 — Scheduler & Heartbeat | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
There is no REST API to manage cron jobs. The web UI and external tools need endpoints to list, create, update, delete, and manually trigger cron jobs. The scheduler (S3-01) provides the backend; this ticket exposes it via FastAPI with Pydantic validation, pagination, and proper error handling.

Reference: The `EngineScheduler` class (S3-01) already has `add_job()`, `update_job()`, `remove_job()`, `trigger_job()`, `list_jobs()`, `get_job()`, and `get_job_history()`. Existing API routers live in `src/api/routers/` and follow `APIRouter` patterns with `tags`, `responses`, and Pydantic models.

## Root Cause
OpenClaw managed cron jobs via its own CLI (`openclaw cron add/list/remove`). No REST API was exposed. The new engine scheduler needs a proper API layer so the web UI (S3-04) and automation scripts can manage jobs through standard HTTP.

## Fix
### `src/api/routers/engine_cron.py`
```python
"""
Cron Job Management API — CRUD + trigger + history.

Endpoints:
    GET    /api/engine/cron               — list all cron jobs
    POST   /api/engine/cron               — create a new cron job
    GET    /api/engine/cron/{job_id}       — get a single job
    PUT    /api/engine/cron/{job_id}       — update a job
    DELETE /api/engine/cron/{job_id}       — delete a job
    POST   /api/engine/cron/{job_id}/trigger — manually trigger a job
    GET    /api/engine/cron/{job_id}/history — execution history
    GET    /api/engine/cron/status         — scheduler status
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from aria_engine.scheduler import EngineScheduler, parse_schedule, SchedulerError

logger = logging.getLogger("aria.api.engine_cron")

router = APIRouter(prefix="/api/engine/cron", tags=["engine-cron"])


# ── Pydantic Models ─────────────────────────────────────────────────


class CronJobCreate(BaseModel):
    """Request body for creating a cron job."""

    id: Optional[str] = Field(
        None,
        description="Job ID (auto-generated if omitted)",
        max_length=100,
    )
    name: str = Field(
        ...,
        description="Human-readable job name",
        max_length=200,
        min_length=1,
    )
    schedule: str = Field(
        ...,
        description="Cron expression (5 or 6 field) or interval shorthand (15m, 1h)",
        max_length=100,
    )
    agent_id: str = Field(
        "main",
        description="Agent to execute this job",
        max_length=100,
    )
    enabled: bool = Field(True, description="Whether the job is active")
    payload_type: str = Field(
        "prompt",
        description="Execution type: prompt, skill, or pipeline",
        pattern="^(prompt|skill|pipeline)$",
    )
    payload: str = Field(
        ...,
        description="Job payload (prompt text, skill reference, or pipeline name)",
    )
    session_mode: str = Field(
        "isolated",
        description="Session mode: isolated, shared, or persistent",
        pattern="^(isolated|shared|persistent)$",
    )
    max_duration_seconds: int = Field(
        300,
        description="Maximum execution time in seconds",
        ge=10,
        le=3600,
    )
    retry_count: int = Field(
        0,
        description="Number of retry attempts on failure",
        ge=0,
        le=5,
    )

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: str) -> str:
        """Validate that the schedule string is parseable."""
        try:
            parse_schedule(v)
        except Exception as e:
            raise ValueError(f"Invalid schedule expression: {e}") from e
        return v


class CronJobUpdate(BaseModel):
    """Request body for updating a cron job (all fields optional)."""

    name: Optional[str] = Field(None, max_length=200)
    schedule: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    enabled: Optional[bool] = None
    payload_type: Optional[str] = Field(None, pattern="^(prompt|skill|pipeline)$")
    payload: Optional[str] = None
    session_mode: Optional[str] = Field(
        None, pattern="^(isolated|shared|persistent)$"
    )
    max_duration_seconds: Optional[int] = Field(None, ge=10, le=3600)
    retry_count: Optional[int] = Field(None, ge=0, le=5)

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                parse_schedule(v)
            except Exception as e:
                raise ValueError(f"Invalid schedule expression: {e}") from e
        return v


class CronJobResponse(BaseModel):
    """Response model for a cron job."""

    id: str
    name: str
    schedule: str
    agent_id: str
    enabled: bool
    payload_type: str
    session_mode: str
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_duration_ms: Optional[int] = None
    last_error: Optional[str] = None
    next_run_at: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CronJobListResponse(BaseModel):
    """Response for listing cron jobs."""

    total: int
    jobs: List[CronJobResponse]
    scheduler_running: bool


class CronHistoryEntry(BaseModel):
    """Single execution history entry."""

    id: Optional[Any] = None
    action: str
    skill: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    success: Optional[bool] = None
    created_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class CronHistoryResponse(BaseModel):
    """Response for job execution history."""

    job_id: str
    total: int
    entries: List[CronHistoryEntry]


class SchedulerStatusResponse(BaseModel):
    """Scheduler status summary."""

    running: bool
    active_executions: int
    active_job_ids: List[str]
    max_concurrent: int


class TriggerResponse(BaseModel):
    """Response after manually triggering a job."""

    triggered: bool
    job_id: str
    message: str


# ── Dependency ───────────────────────────────────────────────────────


def get_scheduler() -> EngineScheduler:
    """
    Get the global EngineScheduler instance.

    Injected at app startup via app.state.scheduler.
    """
    from aria_engine import get_engine

    engine = get_engine()
    if engine is None or engine.scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="Scheduler not available — engine not started",
        )
    return engine.scheduler


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=CronJobListResponse)
async def list_cron_jobs(
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> CronJobListResponse:
    """List all cron jobs with current state."""
    jobs = await scheduler.list_jobs()
    return CronJobListResponse(
        total=len(jobs),
        jobs=[CronJobResponse(**j) for j in jobs],
        scheduler_running=scheduler.is_running,
    )


@router.post("", response_model=CronJobResponse, status_code=201)
async def create_cron_job(
    body: CronJobCreate,
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> CronJobResponse:
    """Create a new cron job."""
    job_data = body.model_dump(exclude_none=True)

    try:
        job_id = await scheduler.add_job(job_data)
    except SchedulerError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to create cron job: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create job") from e

    job = await scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=500, detail="Job created but not found")

    return CronJobResponse(**job)


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> SchedulerStatusResponse:
    """Get scheduler status (before /{job_id} to avoid path conflict)."""
    return SchedulerStatusResponse(**scheduler.get_status())


@router.get("/{job_id}", response_model=CronJobResponse)
async def get_cron_job(
    job_id: str,
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> CronJobResponse:
    """Get a single cron job by ID."""
    job = await scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return CronJobResponse(**job)


@router.put("/{job_id}", response_model=CronJobResponse)
async def update_cron_job(
    job_id: str,
    body: CronJobUpdate,
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> CronJobResponse:
    """Update an existing cron job."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = await scheduler.update_job(job_id, updates)
    except SchedulerError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not updated:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    job = await scheduler.get_job(job_id)
    return CronJobResponse(**job)


@router.delete("/{job_id}", status_code=204)
async def delete_cron_job(
    job_id: str,
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> None:
    """Delete a cron job."""
    removed = await scheduler.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")


@router.post("/{job_id}/trigger", response_model=TriggerResponse)
async def trigger_cron_job(
    job_id: str,
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> TriggerResponse:
    """Manually trigger a cron job (run now)."""
    triggered = await scheduler.trigger_job(job_id)
    if not triggered:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    return TriggerResponse(
        triggered=True,
        job_id=job_id,
        message=f"Job {job_id!r} triggered — running in background",
    )


@router.get("/{job_id}/history", response_model=CronHistoryResponse)
async def get_job_history(
    job_id: str,
    limit: int = Query(50, ge=1, le=500),
    scheduler: EngineScheduler = Depends(get_scheduler),
) -> CronHistoryResponse:
    """Get execution history for a cron job."""
    # Verify job exists
    job = await scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    entries = await scheduler.get_job_history(job_id, limit=limit)
    return CronHistoryResponse(
        job_id=job_id,
        total=len(entries),
        entries=[CronHistoryEntry(**e) for e in entries],
    )
```

### Router Registration in `src/api/main.py`
```python
# Add to existing router includes:
from src.api.routers.engine_cron import router as engine_cron_router

app.include_router(engine_cron_router)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API layer calls scheduler (infrastructure) |
| 2 | .env for secrets (zero in code) | ✅ | No secrets in router code |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires running engine for integration tests |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S3-01 (EngineScheduler class with management methods)
- S1-01 (aria_engine package with get_engine())

## Verification
```bash
# 1. Module imports:
python -c "from src.api.routers.engine_cron import router; print(f'Routes: {len(router.routes)}')"
# EXPECTED: Routes: 8

# 2. Pydantic models:
python -c "
from src.api.routers.engine_cron import CronJobCreate
job = CronJobCreate(name='Test', schedule='15m', payload='Do something')
print(job.model_dump())
"
# EXPECTED: {'id': None, 'name': 'Test', 'schedule': '15m', ...}

# 3. Schedule validation:
python -c "
from src.api.routers.engine_cron import CronJobCreate
try:
    CronJobCreate(name='Bad', schedule='not-valid', payload='x')
except Exception as e:
    print(f'Validation error: {e}')
"
# EXPECTED: Validation error: ... Invalid schedule expression

# 4. API docs (requires running server):
# curl http://localhost:8000/docs → should show /api/engine/cron endpoints
```

## Prompt for Agent
```
Create the cron CRUD API router for the Aria Engine scheduler.

FILES TO READ FIRST:
- aria_engine/scheduler.py (created in S3-01 — EngineScheduler class, all management methods)
- src/api/routers/ (any existing router for pattern reference)
- src/api/main.py (how routers are registered)
- MASTER_PLAN.md (lines 87-130 — cron_jobs table schema)

STEPS:
1. Read all files above
2. Create src/api/routers/engine_cron.py
3. Define Pydantic models: CronJobCreate, CronJobUpdate, CronJobResponse, etc.
4. Add schedule validation in CronJobCreate (call parse_schedule)
5. Implement GET /api/engine/cron — list all jobs
6. Implement POST /api/engine/cron — create job
7. Implement GET/PUT/DELETE /api/engine/cron/{job_id}
8. Implement POST /api/engine/cron/{job_id}/trigger — manual trigger
9. Implement GET /api/engine/cron/{job_id}/history — execution history
10. Register router in src/api/main.py
11. Run verification commands

CONSTRAINTS:
- Constraint 1: Router calls EngineScheduler methods (no direct DB access from router)
- All endpoints return proper HTTP status codes (201 for create, 204 for delete, 404 for not found)
- Pydantic v2 models with field_validator
```
