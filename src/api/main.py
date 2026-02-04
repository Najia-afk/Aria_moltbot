"""
Aria Brain - FastAPI Backend
Main entry point for the Aria AI assistant API
"""
"""
Aria Brain - FastAPI Backend
Canonical data API for Aria Blue (aria_warehouse)
"""

import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
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

# Configuration - uses environment variables for portability
DOCKER_HOST_IP = os.getenv("DOCKER_HOST_IP", "host.docker.internal")
MLX_ENABLED = os.getenv("MLX_ENABLED", "true").lower() == "true"

# Service URLs with specific health check paths
SERVICE_URLS = {
    "grafana": (os.getenv("GRAFANA_URL", "http://grafana:3000"), "/api/health"),
    "prometheus": (os.getenv("PROMETHEUS_URL", "http://prometheus:9090"), "/prometheus/-/healthy"),
    "ollama": (os.getenv("OLLAMA_URL", f"http://{DOCKER_HOST_IP}:11434"), "/api/tags"),
    "mlx": (os.getenv("MLX_URL", f"http://{DOCKER_HOST_IP}:8080"), "/v1/models") if MLX_ENABLED else (None, None),
    "litellm": (os.getenv("LITELLM_URL", "http://litellm:4000"), "/health/liveliness"),
    "clawdbot": (os.getenv("CLAWDBOT_URL", "http://clawdbot:18789"), "/"),
    "pgadmin": (os.getenv("PGADMIN_URL", "http://aria-pgadmin:80"), "/"),
    "browser": ("http://aria-browser:3000", "/"),
    "traefik": (os.getenv("TRAEFIK_URL", "http://traefik:8080"), "/api/overview"),
    "aria-web": (os.getenv("ARIA_WEB_URL", "http://aria-web:5000"), "/"),
    "aria-api": ("http://localhost:8000", "/health"),
}

ARIA_ADMIN_TOKEN = os.getenv("ARIA_ADMIN_TOKEN", "")
SERVICE_CONTROL_ENABLED = os.getenv("ARIA_SERVICE_CONTROL_ENABLED", "false").lower() in {"1", "true", "yes"}

# Remove MLX from services if disabled
if not MLX_ENABLED:
    SERVICE_URLS.pop("mlx", None)

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


# ============================================
# Utility Functions
# ============================================
def serialize_record(row) -> dict:
    """Convert asyncpg Record to JSON-serializable dict"""
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif hasattr(value, '__json__'):
            result[key] = value.__json__()
    return result


def _service_cmd_env(service_id: str, action: str) -> str:
    normalized_service = service_id.upper().replace("-", "_")
    normalized_action = action.upper().replace("-", "_")
    return f"ARIA_SERVICE_CMD_{normalized_service}_{normalized_action}"


async def _run_docker_command(command: str) -> Optional[dict]:
    tokens = command.strip().split()
    if len(tokens) < 3 or tokens[0] != "docker":
        return None

    action = tokens[1]
    target = tokens[2]
    if action not in {"restart", "stop", "start"}:
        return None

    socket_path = "/var/run/docker.sock"
    if not os.path.exists(socket_path):
        return {
            "status": "error",
            "code": 1,
            "stdout": "",
            "stderr": "docker socket not found",
        }

    endpoint = f"/containers/{target}/{action}"
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    async with httpx.AsyncClient(transport=transport, base_url="http://docker") as client:
        resp = await client.post(endpoint)
        if resp.status_code in {204, 200}:
            return {"status": "ok", "code": 0, "stdout": "", "stderr": ""}
        return {
            "status": "error",
            "code": resp.status_code,
            "stdout": "",
            "stderr": resp.text[:2000],
        }


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
async def health_check():
    uptime = (datetime.utcnow() - STARTUP_TIME).total_seconds()
    db_status = "connected" if db_pool else "disconnected"
    return HealthResponse(
        status="healthy",
        uptime_seconds=int(uptime),
        database=db_status,
        version="2.1.0",
    )


@app.get("/status")
async def api_status():
    results = {}
    
    # Check HTTP services
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, (base_url, health_path) in SERVICE_URLS.items():
            try:
                url = base_url.rstrip('/') + health_path
                resp = await client.get(url)
                results[name] = {"status": "up", "code": resp.status_code}
            except Exception as e:
                results[name] = {"status": "down", "code": None, "error": str(e)[:50]}
    
    # Check PostgreSQL via DB pool
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            results["postgres"] = {"status": "up", "code": 200}
        except Exception:
            results["postgres"] = {"status": "down", "code": None}
    else:
        results["postgres"] = {"status": "down", "code": None}
    
    return results


@app.get("/status/{service_id}")
async def api_status_service(service_id: str):
    # Special handling for postgres
    if service_id == "postgres":
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                return {"status": "online", "code": 200}
            except Exception:
                return {"status": "offline", "code": None}
        return {"status": "offline", "code": None}
    
    # HTTP services
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


@app.post("/admin/services/{service_id}/{action}")
async def api_service_control(service_id: str, action: str, request: Request):
    if not SERVICE_CONTROL_ENABLED:
        raise HTTPException(status_code=403, detail="Service control disabled")

    if ARIA_ADMIN_TOKEN:
        token = request.headers.get("X-Admin-Token", "")
        if token != ARIA_ADMIN_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")

    if action not in {"restart", "stop", "start"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    env_key = _service_cmd_env(service_id, action)
    command = os.getenv(env_key)
    if not command:
        raise HTTPException(status_code=400, detail=f"No command configured for {service_id}:{action}")

    try:
        docker_result = await _run_docker_command(command)
        if docker_result is not None:
            return docker_result

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "code": proc.returncode,
            "stdout": (stdout or b"")[-2000:].decode("utf-8", errors="ignore"),
            "stderr": (stderr or b"")[-2000:].decode("utf-8", errors="ignore"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================
# LiteLLM Proxy Endpoints
# ============================================
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
MOONSHOT_KIMI_KEY = os.getenv("MOONSHOT_KIMI_KEY", "")
OPEN_ROUTER_KEY = os.getenv("OPEN_ROUTER_KEY", "")


@app.get("/litellm/models")
async def api_litellm_models():
    """Proxy to LiteLLM models endpoint with authentication"""
    litellm_base = SERVICE_URLS.get("litellm", ("http://litellm:4000", "/health"))[0]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
            resp = await client.get(f"{litellm_base}/models", headers=headers)
            return resp.json()
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.get("/litellm/health")
async def api_litellm_health():
    """Proxy to LiteLLM health endpoint (uses fast liveliness check)"""
    litellm_base = SERVICE_URLS.get("litellm", ("http://litellm:4000", "/health/liveliness"))[0]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
            # Use liveliness endpoint for fast health check
            resp = await client.get(f"{litellm_base}/health/liveliness", headers=headers)
            return {"status": "healthy"} if resp.status_code == 200 else {"status": "unhealthy"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/litellm/spend")
async def api_litellm_spend(limit: int = 20, lite: bool = False):
    """Get LiteLLM spend logs. Use lite=true for lightweight response (charts)."""
    litellm_base = SERVICE_URLS.get("litellm", ("http://litellm:4000", "/health"))[0]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
            resp = await client.get(f"{litellm_base}/spend/logs", headers=headers)
            logs = resp.json()
            # Apply limit (LiteLLM may not support limit param)
            if isinstance(logs, list):
                logs = logs[:limit]
                # Return lightweight version for charts (removes heavy metadata)
                if lite:
                    return [
                        {
                            "model": log.get("model", ""),
                            "prompt_tokens": log.get("prompt_tokens", 0),
                            "completion_tokens": log.get("completion_tokens", 0),
                            "total_tokens": log.get("total_tokens", 0),
                            "spend": log.get("spend", 0),
                            "startTime": log.get("startTime"),
                            "status": log.get("status", "success"),
                        }
                        for log in logs
                    ]
            return logs
    except Exception as e:
        return {"logs": [], "error": str(e)}


@app.get("/litellm/global-spend")
async def api_litellm_global_spend():
    """Get LiteLLM global spend with aggregated token counts"""
    litellm_base = SERVICE_URLS.get("litellm", ("http://litellm:4000", "/health"))[0]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
            
            # Get global spend
            global_resp = await client.get(f"{litellm_base}/global/spend", headers=headers)
            global_data = global_resp.json() if global_resp.status_code == 200 else {}
            
            # Get spend logs for token counts
            logs_resp = await client.get(f"{litellm_base}/spend/logs", headers=headers)
            logs = logs_resp.json() if logs_resp.status_code == 200 else []
            
            # Aggregate token counts from logs
            total_tokens = 0
            input_tokens = 0
            output_tokens = 0
            api_requests = len(logs) if isinstance(logs, list) else 0
            
            if isinstance(logs, list):
                for log in logs:
                    total_tokens += log.get("total_tokens", 0) or 0
                    input_tokens += log.get("prompt_tokens", 0) or 0
                    output_tokens += log.get("completion_tokens", 0) or 0
            
            return {
                "spend": global_data.get("spend", 0) or 0,
                "max_budget": global_data.get("max_budget", 0) or 0,
                "total_tokens": total_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "api_requests": api_requests
            }
    except Exception as e:
        return {"spend": 0, "total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "api_requests": 0, "error": str(e)}


# ============================================
# Provider Balance Endpoints
# ============================================
@app.get("/providers/balances")
async def api_provider_balances():
    """Get balances from all configured providers"""
    balances = {}
    
    # Moonshot/Kimi balance
    if MOONSHOT_KIMI_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {MOONSHOT_KIMI_KEY}"}
                resp = await client.get("https://api.moonshot.ai/v1/users/me/balance", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    balances["kimi"] = {
                        "provider": "Moonshot/Kimi",
                        "available": data.get("data", {}).get("available_balance", 0),
                        "voucher": data.get("data", {}).get("voucher_balance", 0),
                        "cash": data.get("data", {}).get("cash_balance", 0),
                        "currency": "CNY",
                        "status": "ok"
                    }
                else:
                    balances["kimi"] = {"provider": "Moonshot/Kimi", "status": "error", "code": resp.status_code}
        except Exception as e:
            balances["kimi"] = {"provider": "Moonshot/Kimi", "status": "error", "error": str(e)}
    
    # OpenRouter balance
    if OPEN_ROUTER_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {OPEN_ROUTER_KEY}"}
                resp = await client.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    limit_val = data.get("data", {}).get("limit")
                    usage_val = data.get("data", {}).get("usage") or 0
                    # If no limit is set, show usage as negative (prepaid credits spent)
                    # If limit exists, calculate remaining
                    if limit_val is not None:
                        remaining = limit_val - usage_val
                    else:
                        # No credit limit - free tier or prepaid, show balance differently
                        remaining = -usage_val if usage_val > 0 else 0
                    balances["openrouter"] = {
                        "provider": "OpenRouter",
                        "limit": limit_val,
                        "usage": usage_val,
                        "remaining": remaining,
                        "is_free_tier": limit_val is None,
                        "currency": "USD",
                        "status": "ok"
                    }
                else:
                    balances["openrouter"] = {"provider": "OpenRouter", "status": "error", "code": resp.status_code}
        except Exception as e:
            balances["openrouter"] = {"provider": "OpenRouter", "status": "error", "error": str(e)}
    else:
        balances["openrouter"] = {"provider": "OpenRouter", "status": "free_tier", "note": "Using free models only"}
    
    # Local models (free)
    balances["local"] = {
        "provider": "Local (MLX/Ollama)",
        "status": "free",
        "note": "No cost - runs on local hardware"
    }
    
    return balances


@app.get("/stats", response_model=StatsResponse)
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


@app.get("/activities")
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


@app.post("/activities")
async def create_activity(request: Request, conn=Depends(get_db)):
    """Create a new activity log entry"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    details = data.get('details', {})
    await conn.execute(
        """INSERT INTO activity_log (id, action, skill, details, success, error_message, created_at)
           VALUES ($1, $2, $3, $4::jsonb, $5, $6, NOW())""",
        new_id,
        data.get('action'),
        data.get('skill'),
        json_lib.dumps(details) if isinstance(details, dict) else details,
        data.get('success', True),
        data.get('error_message')
    )
    return {"id": str(new_id), "created": True}


# ============================================
# Security Events Endpoints
# ============================================
@app.get("/security-events")
async def api_security_events(
    limit: int = 100,
    threat_level: Optional[str] = None,
    blocked_only: bool = False,
    conn=Depends(get_db)
):
    """Get security events with optional filtering"""
    query = """
        SELECT id, threat_level, threat_type, threat_patterns, input_preview,
               source, user_id, blocked, details, created_at
        FROM security_events
        WHERE 1=1
    """
    params = []
    param_idx = 1
    
    if threat_level:
        query += f" AND threat_level = ${param_idx}"
        params.append(threat_level.upper())
        param_idx += 1
    
    if blocked_only:
        query += " AND blocked = true"
    
    query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
    params.append(limit)
    
    rows = await conn.fetch(query, *params)
    return [
        {
            "id": str(r[0]),
            "threat_level": r[1],
            "threat_type": r[2],
            "threat_patterns": r[3] or [],
            "input_preview": r[4],
            "source": r[5],
            "user_id": r[6],
            "blocked": r[7],
            "details": r[8] or {},
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


@app.post("/security-events")
async def create_security_event(request: Request, conn=Depends(get_db)):
    """Log a new security event"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    
    # Sanitize input preview - truncate and remove sensitive data
    input_preview = data.get('input_preview', '')
    if input_preview and len(input_preview) > 500:
        input_preview = input_preview[:500] + '...'
    
    threat_patterns = data.get('threat_patterns', [])
    details = data.get('details', {})
    
    await conn.execute(
        """INSERT INTO security_events 
           (id, threat_level, threat_type, threat_patterns, input_preview, 
            source, user_id, blocked, details, created_at)
           VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9::jsonb, NOW())""",
        new_id,
        data.get('threat_level', 'LOW'),
        data.get('threat_type', 'unknown'),
        json_lib.dumps(threat_patterns),
        input_preview,
        data.get('source', 'api'),
        data.get('user_id'),
        data.get('blocked', False),
        json_lib.dumps(details)
    )
    return {"id": str(new_id), "created": True}


@app.get("/security-events/stats")
async def api_security_stats(conn=Depends(get_db)):
    """Get security event statistics"""
    total = await conn.fetchval("SELECT COUNT(*) FROM security_events")
    blocked = await conn.fetchval("SELECT COUNT(*) FROM security_events WHERE blocked = true")
    by_level = await conn.fetch("""
        SELECT threat_level, COUNT(*) as count 
        FROM security_events 
        GROUP BY threat_level 
        ORDER BY count DESC
    """)
    by_type = await conn.fetch("""
        SELECT threat_type, COUNT(*) as count 
        FROM security_events 
        GROUP BY threat_type 
        ORDER BY count DESC
        LIMIT 10
    """)
    recent = await conn.fetchval("""
        SELECT COUNT(*) FROM security_events 
        WHERE created_at > NOW() - INTERVAL '24 hours'
    """)
    
    return {
        "total_events": total or 0,
        "blocked_count": blocked or 0,
        "last_24h": recent or 0,
        "by_level": {r[0]: r[1] for r in by_level},
        "by_type": {r[0]: r[1] for r in by_type},
    }


@app.get("/thoughts")
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


@app.post("/thoughts")
async def create_thought(request: Request, conn=Depends(get_db)):
    """Create a new thought"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    metadata = data.get('metadata', {})
    await conn.execute(
        """INSERT INTO thoughts (id, content, category, metadata, created_at)
           VALUES ($1, $2, $3, $4::jsonb, NOW())""",
        new_id,
        data.get('content'),
        data.get('category', 'general'),
        json_lib.dumps(metadata) if isinstance(metadata, dict) else metadata
    )
    return {"id": str(new_id), "created": True}


# ============================================
# Routes: Memories
# ============================================
@app.get("/memories")
async def get_memories(limit: int = 100, category: str = None, conn=Depends(get_db)):
    """Get memories with optional category filter"""
    if category:
        rows = await conn.fetch(
            "SELECT * FROM memories WHERE category = $1 ORDER BY updated_at DESC LIMIT $2",
            category, limit
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM memories ORDER BY updated_at DESC LIMIT $1",
            limit
        )
    return {"memories": [serialize_record(r) for r in rows], "count": len(rows)}


@app.post("/memories")
async def create_or_update_memory(request: Request, conn=Depends(get_db)):
    """Create or update a memory by key (upsert)"""
    import uuid
    import json as json_lib
    data = await request.json()
    key = data.get('key')
    value = data.get('value')
    category = data.get('category', 'general')
    
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    
    # Serialize value to JSON string for JSONB column
    value_json = json_lib.dumps(value) if isinstance(value, (dict, list)) else json_lib.dumps(value)
    
    # Upsert: insert or update on conflict
    result = await conn.fetchrow(
        """INSERT INTO memories (id, key, value, category, created_at, updated_at)
           VALUES (uuid_generate_v4(), $1, $2::jsonb, $3, NOW(), NOW())
           ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, category = $3, updated_at = NOW()
           RETURNING id""",
        key, value_json, category
    )
    return {"id": str(result['id']), "key": key, "upserted": True}


@app.get("/memories/{key}")
async def get_memory_by_key(key: str, conn=Depends(get_db)):
    """Get a specific memory by key"""
    row = await conn.fetchrow(
        "SELECT * FROM memories WHERE key = $1", key
    )
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return serialize_record(row)


@app.delete("/memories/{key}")
async def delete_memory(key: str, conn=Depends(get_db)):
    """Delete a memory by key"""
    await conn.execute("DELETE FROM memories WHERE key = $1", key)
    return {"deleted": True, "key": key}


@app.get("/search")
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


@app.get("/goals")
async def list_goals(limit: int = 100, status: str = None, conn=Depends(get_db)):
    """List all goals with optional status filter"""
    if status:
        rows = await conn.fetch(
            """SELECT id, goal_id, title, description, status, progress, priority, 
                      due_date, created_at, completed_at 
               FROM goals WHERE status = $1 ORDER BY priority DESC, created_at DESC LIMIT $2""",
            status, limit
        )
    else:
        rows = await conn.fetch(
            """SELECT id, goal_id, title, description, status, progress, priority, 
                      due_date, created_at, completed_at 
               FROM goals ORDER BY priority DESC, created_at DESC LIMIT $1""",
            limit
        )
    return [serialize_record(r) for r in rows]


@app.post("/goals")
async def create_goal(request: Request, conn=Depends(get_db)):
    """Create a new goal"""
    data = await request.json()
    import uuid
    new_id = uuid.uuid4()
    goal_id = data.get('goal_id', f"goal-{str(new_id)[:8]}")
    
    await conn.execute(
        """INSERT INTO goals (id, goal_id, title, description, status, progress, priority, due_date, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())""",
        new_id,
        goal_id,
        data.get('title'),
        data.get('description', ''),
        data.get('status', 'pending'),
        data.get('progress', 0),
        data.get('priority', 2),
        data.get('due_date') or data.get('target_date')
    )
    return {"id": str(new_id), "goal_id": goal_id, "created": True}


@app.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, conn=Depends(get_db)):
    """Delete a goal by ID or goal_id"""
    # Try UUID first, then goal_id string
    try:
        import uuid
        uuid.UUID(goal_id)
        await conn.execute("DELETE FROM goals WHERE id = $1", uuid.UUID(goal_id))
    except ValueError:
        await conn.execute("DELETE FROM goals WHERE goal_id = $1", goal_id)
    return {"deleted": True}


@app.patch("/goals/{goal_id}")
async def update_goal(goal_id: str, request: Request, conn=Depends(get_db)):
    """Update goal status and progress"""
    data = await request.json()
    status = data.get('status')
    progress = data.get('progress')
    priority = data.get('priority')
    
    # Build dynamic update
    updates = []
    values = []
    idx = 1
    
    if status is not None:
        updates.append(f"status = ${idx}")
        values.append(status)
        idx += 1
        # If completed, set completed_at
        if status == 'completed':
            updates.append(f"completed_at = NOW()")
    if progress is not None:
        updates.append(f"progress = ${idx}")
        values.append(progress)
        idx += 1
    if priority is not None:
        updates.append(f"priority = ${idx}")
        values.append(priority)
        idx += 1
    
    # Try UUID first, then goal_id string
    try:
        import uuid
        uuid.UUID(goal_id)
        values.append(uuid.UUID(goal_id))
        id_col = "id"
    except ValueError:
        values.append(goal_id)
        id_col = "goal_id"
    
    if updates:
        query = f"UPDATE goals SET {', '.join(updates)} WHERE {id_col} = ${idx}"
        await conn.execute(query, *values)
    
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
@app.get("/status")
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


@app.get("/status/{service_id}")
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


@app.get("/activities")
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


@app.get("/thoughts")
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


@app.get("/search")
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


@app.get("/stats")
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


@app.get("/records")
async def api_records(table: str = "activities", limit: int = 25, page: int = 1, conn=Depends(get_db)):
    table_map = {
        "activities": "activity_log",
        "thoughts": "thoughts",
        "memories": "memories",
        "goals": "goals",
        "social_posts": "social_posts",
        "heartbeat_log": "heartbeat_log",
        "knowledge_entities": "knowledge_entities",
        "knowledge_relations": "knowledge_relations",
        "hourly_goals": "hourly_goals",
        "performance_log": "performance_log",
        "pending_complex_tasks": "pending_complex_tasks",
    }
    # Different tables have different timestamp column names
    order_col_map = {
        "activity_log": "created_at",
        "thoughts": "created_at",
        "memories": "created_at",
        "goals": "created_at",
        "social_posts": "posted_at",
        "heartbeat_log": "created_at",
        "knowledge_entities": "created_at",
        "knowledge_relations": "created_at",
        "hourly_goals": "created_at",
        "performance_log": "created_at",
        "pending_complex_tasks": "created_at",
    }
    if table not in table_map:
        raise HTTPException(status_code=400, detail="Invalid table")

    offset = (page - 1) * limit
    db_table = table_map[table]
    order_col = order_col_map[db_table]

    total = await conn.fetchval(f"SELECT COUNT(*) FROM {db_table}")
    rows = await conn.fetch(f"SELECT * FROM {db_table} ORDER BY {order_col} DESC LIMIT $1 OFFSET $2", limit, offset)
    records = [serialize_record(r) for r in rows]
    return {"records": records, "total": total or 0, "page": page, "limit": limit}


@app.get("/export")
async def api_export(table: str = "activities", conn=Depends(get_db)):
    table_map = {
        "activities": "activity_log",
        "thoughts": "thoughts",
        "memories": "memories",
        "goals": "goals",
        "social_posts": "social_posts",
        "heartbeat_log": "heartbeat_log",
        "knowledge_entities": "knowledge_entities",
        "knowledge_relations": "knowledge_relations",
        "hourly_goals": "hourly_goals",
        "performance_log": "performance_log",
        "pending_complex_tasks": "pending_complex_tasks",
    }
    order_col_map = {
        "activity_log": "created_at",
        "thoughts": "created_at",
        "memories": "created_at",
        "goals": "created_at",
        "social_posts": "posted_at",
        "heartbeat_log": "created_at",
        "knowledge_entities": "created_at",
        "knowledge_relations": "created_at",
        "hourly_goals": "created_at",
        "performance_log": "created_at",
        "pending_complex_tasks": "created_at",
    }
    if table not in table_map:
        raise HTTPException(status_code=400, detail="Invalid table")
    db_table = table_map[table]
    order_col = order_col_map[db_table]
    rows = await conn.fetch(f"SELECT * FROM {db_table} ORDER BY {order_col} DESC")
    records = [serialize_record(r) for r in rows]
    return {"records": records}


# ============================================
# Routes: Heartbeat
# ============================================
@app.get("/heartbeat")
async def get_heartbeats(limit: int = 50, conn=Depends(get_db)):
    """Get recent heartbeat logs"""
    rows = await conn.fetch(
        "SELECT * FROM heartbeat_log ORDER BY created_at DESC LIMIT $1",
        limit
    )
    return {"heartbeats": [serialize_record(r) for r in rows], "count": len(rows)}


@app.post("/heartbeat")
async def create_heartbeat(request: Request, conn=Depends(get_db)):
    """Log a heartbeat"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    details = data.get('details', {})
    await conn.execute(
        """INSERT INTO heartbeat_log (id, beat_number, status, details, created_at)
           VALUES ($1, $2, $3, $4::jsonb, NOW())""",
        new_id,
        data.get('beat_number', 0),
        data.get('status', 'healthy'),
        json_lib.dumps(details) if isinstance(details, dict) else details
    )
    return {"id": str(new_id), "created": True}


@app.get("/heartbeat/latest")
async def get_latest_heartbeat(conn=Depends(get_db)):
    """Get the most recent heartbeat"""
    row = await conn.fetchrow(
        "SELECT * FROM heartbeat_log ORDER BY created_at DESC LIMIT 1"
    )
    if not row:
        return {"error": "No heartbeats found"}
    return serialize_record(row)


# ============================================
# Routes: Knowledge Graph
# ============================================
@app.get("/knowledge-graph")
async def get_knowledge_graph(conn=Depends(get_db)):
    """Get full knowledge graph with entities and relations"""
    entities = await conn.fetch("SELECT * FROM knowledge_entities ORDER BY created_at DESC")
    relations = await conn.fetch("""
        SELECT r.*, e1.name as from_name, e1.type as from_type, 
               e2.name as to_name, e2.type as to_type
        FROM knowledge_relations r
        JOIN knowledge_entities e1 ON r.from_entity = e1.id
        JOIN knowledge_entities e2 ON r.to_entity = e2.id
        ORDER BY r.created_at DESC
    """)
    return {
        "entities": [serialize_record(e) for e in entities],
        "relations": [serialize_record(r) for r in relations],
        "stats": {
            "entity_count": len(entities),
            "relation_count": len(relations)
        }
    }


@app.get("/knowledge-graph/entities")
async def get_knowledge_entities(limit: int = 100, type: str = None, conn=Depends(get_db)):
    """Get knowledge graph entities with optional type filter"""
    if type:
        rows = await conn.fetch(
            "SELECT * FROM knowledge_entities WHERE type = $1 ORDER BY created_at DESC LIMIT $2",
            type, limit
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM knowledge_entities ORDER BY created_at DESC LIMIT $1",
            limit
        )
    return {"entities": [serialize_record(r) for r in rows]}


@app.get("/knowledge-graph/relations")
async def get_knowledge_relations(limit: int = 100, conn=Depends(get_db)):
    """Get knowledge graph relations with entity names"""
    rows = await conn.fetch("""
        SELECT r.*, e1.name as from_name, e1.type as from_type, 
               e2.name as to_name, e2.type as to_type
        FROM knowledge_relations r
        JOIN knowledge_entities e1 ON r.from_entity = e1.id
        JOIN knowledge_entities e2 ON r.to_entity = e2.id
        ORDER BY r.created_at DESC LIMIT $1
    """, limit)
    return {"relations": [serialize_record(r) for r in rows]}


@app.post("/knowledge-graph/entities")
async def create_knowledge_entity(request: Request, conn=Depends(get_db)):
    """Create a new knowledge entity"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    properties = data.get('properties', {})
    await conn.execute(
        """INSERT INTO knowledge_entities (id, name, type, properties, created_at, updated_at)
           VALUES ($1, $2, $3, $4::jsonb, NOW(), NOW())""",
        new_id, data.get('name'), data.get('type'), 
        json_lib.dumps(properties) if isinstance(properties, dict) else properties
    )
    return {"id": str(new_id), "created": True}


@app.post("/knowledge-graph/relations")
async def create_knowledge_relation(request: Request, conn=Depends(get_db)):
    """Create a new knowledge relation"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    properties = data.get('properties', {})
    await conn.execute(
        """INSERT INTO knowledge_relations (id, from_entity, to_entity, relation_type, properties, created_at)
           VALUES ($1, $2, $3, $4, $5::jsonb, NOW())""",
        new_id, 
        uuid.UUID(data.get('from_entity')),
        uuid.UUID(data.get('to_entity')),
        data.get('relation_type'),
        json_lib.dumps(properties) if isinstance(properties, dict) else properties
    )
    return {"id": str(new_id), "created": True}


# ============================================
# Routes: Social Posts (Moltbook)
# ============================================
@app.get("/social")
async def get_social_posts(limit: int = 50, platform: str = None, conn=Depends(get_db)):
    """Get social posts with optional platform filter"""
    if platform:
        rows = await conn.fetch(
            "SELECT * FROM social_posts WHERE platform = $1 ORDER BY posted_at DESC LIMIT $2",
            platform, limit
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM social_posts ORDER BY posted_at DESC LIMIT $1",
            limit
        )
    return {"posts": [serialize_record(r) for r in rows], "count": len(rows)}


@app.post("/social")
async def create_social_post(request: Request, conn=Depends(get_db)):
    """Create a new social post"""
    import uuid
    import json as json_lib
    data = await request.json()
    new_id = uuid.uuid4()
    metadata = data.get('metadata', {})
    await conn.execute(
        """INSERT INTO social_posts (id, platform, post_id, content, visibility, reply_to, url, posted_at, metadata)
           VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8::jsonb)""",
        new_id,
        data.get('platform', 'moltbook'),
        data.get('post_id'),
        data.get('content'),
        data.get('visibility', 'public'),
        data.get('reply_to'),
        data.get('url'),
        json_lib.dumps(metadata) if isinstance(metadata, dict) else metadata
    )
    return {"id": str(new_id), "created": True}


# ============================================
# Routes: Performance Log
# ============================================
@app.get("/performance")
async def get_performance_logs(limit: int = 50, conn=Depends(get_db)):
    """Get performance review logs"""
    rows = await conn.fetch(
        "SELECT * FROM performance_log ORDER BY created_at DESC LIMIT $1",
        limit
    )
    return {"logs": [serialize_record(r) for r in rows], "count": len(rows)}


@app.post("/performance")
async def create_performance_log(request: Request, conn=Depends(get_db)):
    """Create a new performance log entry"""
    data = await request.json()
    await conn.execute(
        """INSERT INTO performance_log (review_period, successes, failures, improvements, created_at)
           VALUES ($1, $2, $3, $4, NOW())""",
        data.get('review_period'),
        data.get('successes'),
        data.get('failures'),
        data.get('improvements')
    )
    return {"created": True}


# ============================================
# Routes: Hourly Goals
# ============================================
@app.get("/hourly-goals")
async def get_hourly_goals(status: str = None, conn=Depends(get_db)):
    """Get hourly goals with optional status filter"""
    if status:
        rows = await conn.fetch(
            "SELECT * FROM hourly_goals WHERE status = $1 ORDER BY hour_slot, created_at DESC",
            status
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM hourly_goals ORDER BY hour_slot, created_at DESC"
        )
    return {"goals": [serialize_record(r) for r in rows], "count": len(rows)}


@app.post("/hourly-goals")
async def create_hourly_goal(request: Request, conn=Depends(get_db)):
    """Create a new hourly goal"""
    data = await request.json()
    await conn.execute(
        """INSERT INTO hourly_goals (hour_slot, goal_type, description, status, created_at)
           VALUES ($1, $2, $3, $4, NOW())""",
        data.get('hour_slot'),
        data.get('goal_type'),
        data.get('description'),
        data.get('status', 'pending')
    )
    return {"created": True}


@app.patch("/hourly-goals/{goal_id}")
async def update_hourly_goal(goal_id: int, request: Request, conn=Depends(get_db)):
    """Update hourly goal status"""
    data = await request.json()
    status = data.get('status')
    if status == 'completed':
        await conn.execute(
            "UPDATE hourly_goals SET status = $1, completed_at = NOW() WHERE id = $2",
            status, goal_id
        )
    else:
        await conn.execute(
            "UPDATE hourly_goals SET status = $1 WHERE id = $2",
            status, goal_id
        )
    return {"updated": True}


# ============================================
# Routes: Pending Complex Tasks
# ============================================
@app.get("/tasks")
async def get_pending_tasks(status: str = None, conn=Depends(get_db)):
    """Get pending complex tasks"""
    if status:
        rows = await conn.fetch(
            "SELECT * FROM pending_complex_tasks WHERE status = $1 ORDER BY created_at DESC",
            status
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM pending_complex_tasks ORDER BY created_at DESC"
        )
    return {"tasks": [serialize_record(r) for r in rows], "count": len(rows)}


@app.post("/tasks")
async def create_pending_task(request: Request, conn=Depends(get_db)):
    """Create a new pending complex task"""
    import uuid
    data = await request.json()
    task_id = data.get('task_id', f"task-{str(uuid.uuid4())[:8]}")
    await conn.execute(
        """INSERT INTO pending_complex_tasks (task_id, task_type, description, agent_type, priority, status, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, NOW())""",
        task_id,
        data.get('task_type'),
        data.get('description'),
        data.get('agent_type'),
        data.get('priority', 'medium'),
        data.get('status', 'pending')
    )
    return {"task_id": task_id, "created": True}


@app.patch("/tasks/{task_id}")
async def update_pending_task(task_id: str, request: Request, conn=Depends(get_db)):
    """Update pending task status and result"""
    data = await request.json()
    status = data.get('status')
    result = data.get('result')
    
    if status == 'completed':
        await conn.execute(
            "UPDATE pending_complex_tasks SET status = $1, result = $2, completed_at = NOW() WHERE task_id = $3",
            status, result, task_id
        )
    else:
        await conn.execute(
            "UPDATE pending_complex_tasks SET status = $1, result = $2 WHERE task_id = $3",
            status, result, task_id
        )
    return {"updated": True}


# ============================================
# Routes: Schedule
# ============================================
@app.get("/schedule")
async def get_schedule(conn=Depends(get_db)):
    """Get current schedule tick status with job stats"""
    row = await conn.fetchrow(
        """SELECT * FROM schedule_tick WHERE id = 1"""
    )
    return dict(row) if row else {"error": "No schedule found"}


@app.post("/schedule/tick")
async def manual_tick(conn=Depends(get_db)):
    """Trigger a manual schedule tick and update job stats from OpenClaw"""
    import json
    
    jobs_path = os.getenv("OPENCLAW_JOBS_PATH", "/openclaw/cron/jobs.json")
    jobs_total = 0
    jobs_successful = 0
    jobs_failed = 0
    last_job_name = None
    last_job_status = None
    next_job_at = None
    
    try:
        with open(jobs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        jobs = data.get("jobs", [])
        jobs_total = len(jobs)
        
        # Find latest run and next run
        latest_run_ms = 0
        earliest_next_ms = float('inf')
        
        for job in jobs:
            state = job.get("state", {})
            if state.get("lastRunAtMs", 0) > latest_run_ms:
                latest_run_ms = state.get("lastRunAtMs", 0)
                last_job_name = job.get("name")
                last_job_status = state.get("lastStatus")
            
            if state.get("nextRunAtMs", 0) < earliest_next_ms and state.get("nextRunAtMs", 0) > 0:
                earliest_next_ms = state.get("nextRunAtMs", 0)
            
            # Count success/fail
            if state.get("lastStatus") == "ok":
                jobs_successful += 1
            elif state.get("lastStatus") == "error":
                jobs_failed += 1
        
        if earliest_next_ms < float('inf'):
            next_job_at = datetime.fromtimestamp(earliest_next_ms / 1000)
    except Exception:
        pass  # If file read fails, just update tick
    
    await conn.execute(
        """UPDATE schedule_tick SET 
           last_tick = NOW(), 
           tick_count = tick_count + 1,
           jobs_total = $1,
           jobs_successful = $2,
           jobs_failed = $3,
           last_job_name = $4,
           last_job_status = $5,
           next_job_at = $6,
           updated_at = NOW()
           WHERE id = 1""",
        jobs_total, jobs_successful, jobs_failed, last_job_name, last_job_status, next_job_at
    )
    return {"ticked": True, "at": datetime.utcnow().isoformat(), "jobs_total": jobs_total}


# ============================================
# Routes: Scheduled Jobs (OpenClaw Sync)
# ============================================
@app.get("/jobs")
async def get_scheduled_jobs(conn=Depends(get_db)):
    """Get all scheduled jobs from database (synced from OpenClaw)"""
    rows = await conn.fetch(
        """SELECT id, agent_id, name, enabled, schedule_kind, schedule_expr,
                  session_target, wake_mode, payload_kind, payload_text,
                  next_run_at, last_run_at, last_status, last_duration_ms,
                  run_count, success_count, fail_count, synced_at
           FROM scheduled_jobs
           ORDER BY name"""
    )
    return {"jobs": [dict(r) for r in rows], "count": len(rows)}


@app.get("/jobs/live")
async def get_jobs_live():
    """
    Get jobs directly from OpenClaw jobs.json file (live, no DB).
    This reads the current state from the mounted volume.
    """
    import json
    
    jobs_path = os.getenv("OPENCLAW_JOBS_PATH", "/openclaw/cron/jobs.json")
    
    try:
        with open(jobs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        jobs = []
        for job in data.get("jobs", []):
            schedule = job.get("schedule", {})
            state = job.get("state", {})
            payload = job.get("payload", {})
            
            jobs.append({
                "id": job.get("id"),
                "agent_id": job.get("agentId", "main"),
                "name": job.get("name"),
                "enabled": job.get("enabled", True),
                "schedule_kind": schedule.get("kind", "cron"),
                "schedule_expr": schedule.get("expr", ""),
                "session_target": job.get("sessionTarget"),
                "wake_mode": job.get("wakeMode"),
                "payload_kind": payload.get("kind"),
                "payload_text": payload.get("text"),
                "next_run_at": datetime.fromtimestamp(state.get("nextRunAtMs", 0) / 1000).isoformat() if state.get("nextRunAtMs") else None,
                "last_run_at": datetime.fromtimestamp(state.get("lastRunAtMs", 0) / 1000).isoformat() if state.get("lastRunAtMs") else None,
                "last_status": state.get("lastStatus"),
                "last_duration_ms": state.get("lastDurationMs"),
            })
        
        return {"jobs": jobs, "count": len(jobs), "source": "live"}
    
    except FileNotFoundError:
        return {"jobs": [], "count": 0, "source": "live", "error": f"File not found: {jobs_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}")
async def get_scheduled_job(job_id: str, conn=Depends(get_db)):
    """Get a specific scheduled job by ID"""
    row = await conn.fetchrow(
        """SELECT * FROM scheduled_jobs WHERE id = $1""", job_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@app.post("/jobs/sync")
async def sync_jobs_from_openclaw(conn=Depends(get_db)):
    """
    Sync scheduled jobs from OpenClaw cron system.
    Reads jobs.json from mounted OpenClaw volume at /openclaw/cron/jobs.json
    """
    import json
    
    jobs_path = os.getenv("OPENCLAW_JOBS_PATH", "/openclaw/cron/jobs.json")
    
    try:
        with open(jobs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        jobs = data.get("jobs", [])
        
        synced = 0
        for job in jobs:
            schedule = job.get("schedule", {})
            state = job.get("state", {})
            payload = job.get("payload", {})
            
            # Convert millisecond timestamps to datetime
            next_run = datetime.fromtimestamp(state.get("nextRunAtMs", 0) / 1000) if state.get("nextRunAtMs") else None
            last_run = datetime.fromtimestamp(state.get("lastRunAtMs", 0) / 1000) if state.get("lastRunAtMs") else None
            
            # Upsert job into database
            await conn.execute("""
                INSERT INTO scheduled_jobs (
                    id, agent_id, name, enabled, schedule_kind, schedule_expr,
                    session_target, wake_mode, payload_kind, payload_text,
                    next_run_at, last_run_at, last_status, last_duration_ms,
                    created_at_ms, updated_at_ms, synced_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    agent_id = EXCLUDED.agent_id,
                    name = EXCLUDED.name,
                    enabled = EXCLUDED.enabled,
                    schedule_kind = EXCLUDED.schedule_kind,
                    schedule_expr = EXCLUDED.schedule_expr,
                    session_target = EXCLUDED.session_target,
                    wake_mode = EXCLUDED.wake_mode,
                    payload_kind = EXCLUDED.payload_kind,
                    payload_text = EXCLUDED.payload_text,
                    next_run_at = EXCLUDED.next_run_at,
                    last_run_at = EXCLUDED.last_run_at,
                    last_status = EXCLUDED.last_status,
                    last_duration_ms = EXCLUDED.last_duration_ms,
                    updated_at_ms = EXCLUDED.updated_at_ms,
                    synced_at = NOW()
            """,
                job.get("id"),
                job.get("agentId", "main"),
                job.get("name"),
                job.get("enabled", True),
                schedule.get("kind", "cron"),
                schedule.get("expr", ""),
                job.get("sessionTarget"),
                job.get("wakeMode"),
                payload.get("kind"),
                payload.get("text"),
                next_run,
                last_run,
                state.get("lastStatus"),
                state.get("lastDurationMs"),
                job.get("createdAtMs"),
                job.get("updatedAtMs")
            )
            synced += 1
        
        return {"synced": synced, "source": jobs_path, "total_in_file": len(jobs)}
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Jobs file not found at {jobs_path}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON from OpenClaw: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
