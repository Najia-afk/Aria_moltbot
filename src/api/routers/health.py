"""
Health, status, and stats endpoints.
"""

from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import DOCKER_HOST_IP, SERVICE_URLS, STARTUP_TIME, API_VERSION
from db.session import async_engine
from db.models import ActivityLog, Thought, Memory
from deps import get_db

router = APIRouter(tags=["Health"])


# ── Response models ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    uptime_seconds: int
    database: str
    version: str


class StatsResponse(BaseModel):
    activities_count: int
    thoughts_count: int
    memories_count: int
    last_activity: Optional[str]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    uptime = (datetime.utcnow() - STARTUP_TIME).total_seconds()
    return HealthResponse(
        status="healthy",
        uptime_seconds=int(uptime),
        database="connected",
        version=API_VERSION,
    )


@router.get("/host-stats")
async def host_stats():
    stats = {
        "ram": {"used_gb": 0, "total_gb": 16, "percent": 0},
        "swap": {"used_gb": 0, "total_gb": 0, "percent": 0},
        "disk": {"used_gb": 0, "total_gb": 500, "percent": 0},
        "smart": {"status": "unknown", "healthy": True},
        "timestamp": datetime.utcnow().isoformat(),
        "source": "unavailable",
    }
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://{DOCKER_HOST_IP}:8888/stats")
            if resp.status_code == 200:
                stats.update(resp.json())
                stats["source"] = "host"
    except Exception:
        pass
    return stats


@router.get("/status")
async def api_status():
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, (base_url, health_path) in SERVICE_URLS.items():
            try:
                url = base_url.rstrip("/") + health_path
                resp = await client.get(url)
                results[name] = {"status": "up", "code": resp.status_code}
            except Exception as e:
                results[name] = {"status": "down", "code": None, "error": str(e)[:50]}

    # Check PostgreSQL via SQLAlchemy engine
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        results["postgres"] = {"status": "up", "code": 200}
    except Exception:
        results["postgres"] = {"status": "down", "code": None}
    return results


@router.get("/status/{service_id}")
async def api_status_service(service_id: str):
    if service_id == "postgres":
        try:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "online", "code": 200}
        except Exception:
            return {"status": "offline", "code": None}

    service_info = SERVICE_URLS.get(service_id)
    if not service_info:
        raise HTTPException(status_code=404, detail="Unknown service")
    base_url, health_path = service_info
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            url = base_url.rstrip("/") + health_path
            resp = await client.get(url)
        return {"status": "online", "code": resp.status_code}
    except Exception:
        return {"status": "offline", "code": None}


@router.get("/stats", response_model=StatsResponse)
async def api_stats(db: AsyncSession = Depends(get_db)):
    activities = (await db.execute(select(func.count(ActivityLog.id)))).scalar() or 0
    thoughts = (await db.execute(select(func.count(Thought.id)))).scalar() or 0
    memories = (await db.execute(select(func.count(Memory.id)))).scalar() or 0
    last = (await db.execute(select(func.max(ActivityLog.created_at)))).scalar()
    return StatsResponse(
        activities_count=activities,
        thoughts_count=thoughts,
        memories_count=memories,
        last_activity=last.isoformat() if last else None,
    )


@router.get("/stats-extended")
async def api_stats_extended(db: AsyncSession = Depends(get_db)):
    try:
        activities_count = (await db.execute(select(func.count(ActivityLog.id)))).scalar() or 0
        thoughts_count = (await db.execute(select(func.count(Thought.id)))).scalar() or 0
        memories_count = (await db.execute(select(func.count(Memory.id)))).scalar() or 0
        last_activity = (await db.execute(select(func.max(ActivityLog.created_at)))).scalar()
        return {
            "activities_count": activities_count,
            "thoughts_count": thoughts_count,
            "memories_count": memories_count,
            "last_activity": last_activity.isoformat() if last_activity else None,
        }
    except Exception as e:
        return {
            "error": str(e),
            "activities_count": 0,
            "thoughts_count": 0,
            "memories_count": 0,
            "last_activity": None,
        }
