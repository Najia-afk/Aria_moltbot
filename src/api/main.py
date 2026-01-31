"""
Aria Brain - FastAPI Backend
Main entry point for the Aria AI assistant API
"""
"""
Aria Brain - FastAPI Backend
Canonical data API for Aria Blue (aria_warehouse)
"""

import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from schema import ensure_schema

# ============================================
# Configuration
# ============================================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Service URLs with specific health check paths
SERVICE_URLS = {
    "grafana": (os.getenv("GRAFANA_URL", "http://grafana:3000"), "/api/health"),
    "prometheus": (os.getenv("PROMETHEUS_URL", "http://prometheus:9090"), "/prometheus/-/healthy"),
    "ollama": (os.getenv("OLLAMA_URL", "http://host.docker.internal:11434"), "/api/tags"),
    "litellm": (os.getenv("LITELLM_URL", "http://litellm:4000"), "/health/liveliness"),
    "clawdbot": (os.getenv("CLAWDBOT_URL", "http://clawdbot:18789"), "/"),
    "pgadmin": (os.getenv("PGADMIN_URL", "http://aria-pgadmin:80"), "/"),
    "browser": ("http://aria-browser:3000", "/"),
}

STARTUP_TIME = datetime.utcnow()

db_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    print("🧠 Aria Brain API starting up...")
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        print("✅ Database connection pool created")
        await ensure_schema(DATABASE_URL)
        print("✅ Database schema ensured via API")
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
        db_pool = None
    yield
    if db_pool:
        await db_pool.close()
        print("🔌 Database pool closed")


app = FastAPI(
    title="Aria Brain API",
    description="""
## Aria Blue Data API

Canonical data API for the Aria AI assistant ecosystem.

### Features
- **Activities**: Track and query AI agent activities
- **Thoughts**: Store and retrieve reasoning logs
- **Memories**: Long-term memory storage
- **Records**: Generic data table access
- **Services**: Health monitoring for all stack services

### Authentication
Currently open for internal network access.
    """,
    version="2.1.0",
    lifespan=lifespan,
    root_path="/api",  # Mounted behind reverse proxy at /api
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Prometheus metrics instrumentation - exposes /metrics endpoint
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


async def get_db():
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with db_pool.acquire() as conn:
        yield conn


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    uptime = (datetime.utcnow() - STARTUP_TIME).total_seconds()
    db_status = "connected" if db_pool else "disconnected"
    return HealthResponse(
        status="healthy",
        uptime_seconds=int(uptime),
        database=db_status,
        version="2.1.0",
    )


@app.get("/api/status")
async def api_status():
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, (base_url, health_path) in SERVICE_URLS.items():
            try:
                url = base_url.rstrip('/') + health_path
                resp = await client.get(url)
                results[name] = {"status": "up", "code": resp.status_code}
            except Exception as e:
                results[name] = {"status": "down", "code": None, "error": str(e)[:50]}
    return results


@app.get("/api/status/{service_id}")
async def api_status_service(service_id: str):
    service_info = SERVICE_URLS.get(service_id)
    if not service_info:
        raise HTTPException(status_code=404, detail="Unknown service")
    base_url, health_path = service_info
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            url = base_url.rstrip('/') + health_path
            resp = await client.get(url)
        return {"status": "online", "code": resp.status_code}
    except Exception:
        return {"status": "offline", "code": None}


@app.get("/api/stats", response_model=StatsResponse)
async def api_stats(conn=Depends(get_db)):
    activities = await conn.fetchval("SELECT COUNT(*) FROM activity_log")
    thoughts = await conn.fetchval("SELECT COUNT(*) FROM thoughts")
    memories = await conn.fetchval("SELECT COUNT(*) FROM memories")
    last = await conn.fetchval("SELECT MAX(created_at) FROM activity_log")
    return StatsResponse(
        activities_count=activities or 0,
        thoughts_count=thoughts or 0,
        memories_count=memories or 0,
        last_activity=last.isoformat() if last else None,
    )


@app.get("/api/activities")
async def api_activities(limit: int = 100, conn=Depends(get_db)):
    rows = await conn.fetch(
        """
        SELECT id, action, details, created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    results = []
    for r in rows:
        details = r[2] or {}
        if isinstance(details, dict):
            description = details.get("message") or details.get("description") or str(details)
        else:
            description = str(details)
        results.append(
            {
                "id": str(r[0]),
                "type": r[1],
                "description": description,
                "created_at": r[3].isoformat() if r[3] else None,
            }
        )
    return results


@app.get("/api/thoughts")
async def api_thoughts(limit: int = 100, conn=Depends(get_db)):
    rows = await conn.fetch(
        """
        SELECT id, category, content, created_at
        FROM thoughts
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return {
        "thoughts": [
            {
                "id": str(r[0]),
                "category": r[1],
                "content": r[2],
                "timestamp": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ]
    }


@app.get("/api/search")
async def api_search(
    q: str = "",
    activities: bool = True,
    thoughts: bool = True,
    memories: bool = True,
    conn=Depends(get_db),
):
    if not q:
        return {"activities": [], "thoughts": [], "memories": []}

    results = {"activities": [], "thoughts": [], "memories": []}
    like = f"%{q}%"

    if activities:
        rows = await conn.fetch(
            """
            SELECT id, action, details, created_at
            FROM activity_log
            WHERE details::text ILIKE $1 OR action ILIKE $1
            ORDER BY created_at DESC
            LIMIT 20
            """,
            like,
        )
        for r in rows:
            details = r[2] or {}
            if isinstance(details, dict):
                content = details.get("message") or details.get("description") or str(details)
            else:
                content = str(details)
            results["activities"].append(
                {
                    "id": str(r[0]),
                    "type": r[1],
                    "content": content,
                    "timestamp": r[3].isoformat() if r[3] else None,
                }
            )

    if thoughts:
        rows = await conn.fetch(
            """
            SELECT id, category, content, created_at
            FROM thoughts
            WHERE content ILIKE $1 OR category ILIKE $1
            ORDER BY created_at DESC
            LIMIT 20
            """,
            like,
        )
        for r in rows:
            results["thoughts"].append(
                {
                    "id": str(r[0]),
                    "type": r[1],
                    "content": r[2],
                    "timestamp": r[3].isoformat() if r[3] else None,
                }
            )

    if memories:
        rows = await conn.fetch(
            """
            SELECT id, category, value, created_at
            FROM memories
            WHERE value::text ILIKE $1 OR category ILIKE $1
            ORDER BY created_at DESC
            LIMIT 20
            """,
            like,
        )
        for r in rows:
            results["memories"].append(
                {
                    "id": str(r[0]),
                    "type": r[1],
                    "content": str(r[2]),
                    "timestamp": r[3].isoformat() if r[3] else None,
                }
            )

    return results


@app.get("/api/records")
async def api_records(
    table: str = "activities",
    limit: int = 25,
    page: int = 1,
    conn=Depends(get_db),
):
    table_map = {
        "activities": "activity_log",
        "thoughts": "thoughts",
        "memories": "memories",
    }
    if table not in table_map:
        raise HTTPException(status_code=400, detail="Invalid table")

    offset = (page - 1) * limit
    total = await conn.fetchval(f"SELECT COUNT(*) FROM {table_map[table]}")
    rows = await conn.fetch(
        f"SELECT * FROM {table_map[table]} ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    records = [dict(r) for r in rows]
    return {"records": records, "total": total}


@app.get("/api/export")
async def api_export(table: str = "activities", conn=Depends(get_db)):
    table_map = {
        "activities": "activity_log",
        "thoughts": "thoughts",
        "memories": "memories",
    }
    if table not in table_map:
        raise HTTPException(status_code=400, detail="Invalid table")
    rows = await conn.fetch(f"SELECT * FROM {table_map[table]} ORDER BY created_at DESC")
    return {"records": [dict(r) for r in rows]}

@app.patch("/goals/{goal_id}")
async def update_goal(goal_id: str, status: str, progress: int = None, conn=Depends(get_db)):
    """Update goal status and progress"""
    if progress is not None:
        await conn.execute(
            "UPDATE goals SET status = $1, progress = $2 WHERE id = $3",
            status, progress, goal_id
        )
    else:
        await conn.execute(
            "UPDATE goals SET status = $1 WHERE id = $2",
            status, goal_id
        )
    return {"updated": True}


# ============================================
# Routes: Interactions
# ============================================
@app.get("/interactions")
async def list_interactions(limit: int = 50, conn=Depends(get_db)):
    """List recent interactions"""
    rows = await conn.fetch(
        """SELECT id, action, skill, details, success, error_message, created_at
           FROM activity_log ORDER BY created_at DESC LIMIT $1""",
        limit
    )
    return [serialize_record(r) for r in rows]


# ============================================
# Routes: UI API (/api)
# ============================================
@app.get("/api/status")
async def api_status(conn=Depends(get_db)):
    status = {}
    for name, url in SERVICE_URLS.items():
        status[name] = await check_http_status(url)

    # Database status
    try:
        await conn.execute("SELECT 1")
        status["postgres"] = {"status": "up", "code": 200}
    except Exception:
        status["postgres"] = {"status": "down", "code": None}

    return status


@app.get("/api/status/{service_id}")
async def api_service_status(service_id: str, conn=Depends(get_db)):
    service_ports = {
        "ollama": 11434,
        "litellm": 18793,
        "clawdbot": 18789,
        "postgres": 5432,
        "grafana": 3001,
        "prometheus": 9090,
        "pgadmin": 5050,
        "traefik": 8080,
    }

    if service_id == "postgres":
        try:
            await conn.execute("SELECT 1")
            return {"status": "online", "port": service_ports["postgres"]}
        except Exception:
            return {"status": "offline", "port": service_ports["postgres"]}

    if service_id not in SERVICE_URLS:
        return {"status": "unknown", "error": "Unknown service"}

    result = await check_http_status(SERVICE_URLS[service_id])
    return {"status": "online" if result["status"] == "up" else "offline", "port": service_ports.get(service_id), "code": result.get("code")}


@app.get("/api/activities")
async def api_activities(limit: int = 100, conn=Depends(get_db)):
    rows = await conn.fetch(
        """SELECT id, action, details, created_at
           FROM activity_log
           ORDER BY created_at DESC
           LIMIT $1""",
        limit,
    )
    activities = []
    for row in rows:
        record = serialize_record(row)
        activities.append({
            "id": record["id"],
            "type": record["action"],
            "description": json.dumps(record.get("details")) if record.get("details") is not None else None,
            "created_at": record.get("created_at"),
        })
    return activities


@app.get("/api/thoughts")
async def api_thoughts(limit: int = 100, conn=Depends(get_db)):
    rows = await conn.fetch(
        """SELECT id, category, content, created_at
           FROM thoughts
           ORDER BY created_at DESC
           LIMIT $1""",
        limit,
    )
    thoughts = []
    for row in rows:
        record = serialize_record(row)
        thoughts.append({
            "id": record["id"],
            "category": record["category"],
            "content": record["content"],
            "timestamp": record.get("created_at"),
        })
    return {"thoughts": thoughts}


@app.get("/api/search")
async def api_search(q: str = "", activities: bool = True, thoughts: bool = True, memories: bool = True, conn=Depends(get_db)):
    if not q:
        return {"activities": [], "thoughts": [], "memories": []}

    results = {"activities": [], "thoughts": [], "memories": []}

    if activities:
        rows = await conn.fetch(
            """SELECT id, action, details, created_at
               FROM activity_log
               WHERE action ILIKE $1 OR details::text ILIKE $1
               ORDER BY created_at DESC LIMIT 20""",
            f"%{q}%",
        )
        for row in rows:
            record = serialize_record(row)
            results["activities"].append({
                "id": record["id"],
                "type": record["action"],
                "content": json.dumps(record.get("details")) if record.get("details") is not None else None,
                "timestamp": record.get("created_at"),
            })

    if thoughts:
        rows = await conn.fetch(
            """SELECT id, category, content, created_at
               FROM thoughts
               WHERE content ILIKE $1 OR category ILIKE $1
               ORDER BY created_at DESC LIMIT 20""",
            f"%{q}%",
        )
        for row in rows:
            record = serialize_record(row)
            results["thoughts"].append({
                "id": record["id"],
                "type": record["category"],
                "content": record["content"],
                "timestamp": record.get("created_at"),
            })

    if memories:
        rows = await conn.fetch(
            """SELECT id, key, value, category, created_at
               FROM memories
               WHERE key ILIKE $1 OR value::text ILIKE $1
               ORDER BY created_at DESC LIMIT 20""",
            f"%{q}%",
        )
        for row in rows:
            record = serialize_record(row)
            results["memories"].append({
                "id": record["id"],
                "type": record["category"],
                "content": json.dumps(record.get("value")) if record.get("value") is not None else None,
                "timestamp": record.get("created_at"),
            })

    return results


@app.get("/api/stats")
async def api_stats(conn=Depends(get_db)):
    try:
        activities_count = await conn.fetchval("SELECT COUNT(*) FROM activity_log")
        thoughts_count = await conn.fetchval("SELECT COUNT(*) FROM thoughts")
        memories_count = await conn.fetchval("SELECT COUNT(*) FROM memories")
        last_activity = await conn.fetchval("SELECT MAX(created_at) FROM activity_log")
        return {
            "activities_count": activities_count or 0,
            "thoughts_count": thoughts_count or 0,
            "memories_count": memories_count or 0,
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


@app.get("/api/records")
async def api_records(table: str = "activities", limit: int = 25, page: int = 1, conn=Depends(get_db)):
    table_map = {
        "activities": "activity_log",
        "thoughts": "thoughts",
        "memories": "memories",
    }
    if table not in table_map:
        raise HTTPException(status_code=400, detail="Invalid table")

    offset = (page - 1) * limit
    db_table = table_map[table]

    total = await conn.fetchval(f"SELECT COUNT(*) FROM {db_table}")
    rows = await conn.fetch(f"SELECT * FROM {db_table} ORDER BY created_at DESC LIMIT $1 OFFSET $2", limit, offset)
    records = [serialize_record(r) for r in rows]
    return {"records": records, "total": total or 0, "page": page, "limit": limit}


@app.get("/api/export")
async def api_export(table: str = "activities", conn=Depends(get_db)):
    table_map = {
        "activities": "activity_log",
        "thoughts": "thoughts",
        "memories": "memories",
    }
    if table not in table_map:
        raise HTTPException(status_code=400, detail="Invalid table")
    db_table = table_map[table]
    rows = await conn.fetch(f"SELECT * FROM {db_table} ORDER BY created_at DESC")
    records = [serialize_record(r) for r in rows]
    return {"records": records}


# ============================================
# Routes: Schedule
# ============================================
@app.get("/schedule")
async def get_schedule(conn=Depends(get_db)):
    """Get current schedule tick status"""
    row = await conn.fetchrow(
        """SELECT * FROM schedule_tick WHERE id = 1"""
    )
    return dict(row) if row else {"error": "No schedule found"}


@app.post("/schedule/tick")
async def manual_tick(conn=Depends(get_db)):
    """Trigger a manual schedule tick"""
    await conn.execute(
        """UPDATE schedule_tick SET last_tick = NOW(), tick_count = tick_count + 1 WHERE id = 1"""
    )
    return {"ticked": True, "at": datetime.utcnow().isoformat()}


# ============================================
# Routes: Soul Access
# ============================================
@app.get("/soul/{filename}")
async def read_soul_file(filename: str):
    """Read a soul file"""
    allowed = ["SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md", "HEARTBEAT.md", "BOOTSTRAP.md"]
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Soul file not found")
    
    soul_path = f"/app/memory/soul/{filename}"
    try:
        with open(soul_path, "r", encoding="utf-8") as f:
            return {"filename": filename, "content": f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Soul file not found")


# ============================================
# Routes: Activity Feed
# ============================================
@app.get("/activity")
async def get_activity(limit: int = 10, conn=Depends(get_db)):
    """Get recent activity across all types"""
    activities = []
    
    # Recent thoughts
    thoughts = await conn.fetch(
        "SELECT 'thought' as type, content as message, created_at FROM thought ORDER BY created_at DESC LIMIT 3"
    )
    activities.extend([dict(r) for r in thoughts])
    
    # Recent goals
    goals = await conn.fetch(
        "SELECT 'goal' as type, title as message, created_at FROM goal ORDER BY created_at DESC LIMIT 3"
    )
    activities.extend([dict(r) for r in goals])
    
    # Recent API calls
    calls = await conn.fetch(
        "SELECT 'api' as type, agent_name as message, called_at as created_at FROM agent_call ORDER BY called_at DESC LIMIT 3"
    )
    activities.extend([dict(r) for r in calls])
    
    # Sort by time
    activities.sort(key=lambda x: x['created_at'], reverse=True)
    return activities[:limit]


# ============================================
# Main
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
