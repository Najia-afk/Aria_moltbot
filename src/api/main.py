"""
Aria Brain — FastAPI Application Factory (v3.0)

Modular API with:
  • SQLAlchemy 2.0 async ORM + psycopg 3 driver
  • Sub-routers for every domain
  • Strawberry GraphQL on /graphql
  • Prometheus instrumentation
"""

import logging
import os
import time as _time
import uuid as _uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

from config import API_VERSION
from db import async_engine, ensure_schema


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🧠 Aria Brain API v3.0 starting up…")
    try:
        await ensure_schema()
        print("✅ Database schema ensured (SQLAlchemy 2 + psycopg3)")
    except Exception as e:
        print(f"⚠️  Database init failed: {e}")

    # S4-07: Auto-sync skill graph on startup
    try:
        from graph_sync import sync_skill_graph
        stats = await sync_skill_graph()
        print(f"✅ Skill graph synced: {stats['entities']} entities, {stats['relations']} relations")
    except Exception as e:
        print(f"⚠️  Skill graph sync failed (non-fatal): {e}")

    yield
    await async_engine.dispose()
    print("🔌 Database engine disposed")


# ── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Aria Brain API",
    description=(
        "## Aria Blue Data API v3\n\n"
        "Canonical data API for the Aria AI assistant ecosystem.\n\n"
        "### Stack\n"
        "- **ORM**: SQLAlchemy 2.0 async\n"
        "- **Driver**: psycopg 3\n"
        "- **GraphQL**: Strawberry (at `/graphql`)\n\n"
        "### Domains\n"
        "Activities · Thoughts · Memories · Goals · Sessions · Model Usage · "
        "LiteLLM · Providers · Security · Knowledge Graph · Social · "
        "Records · Admin"
    ),
    version=API_VERSION,
    lifespan=lifespan,
    root_path="/api",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── Middleware ────────────────────────────────────────────────────────────────

_CORS_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5000,http://aria-web:5000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware — rate limiting, injection scanning, security headers
from security_middleware import SecurityMiddleware, RateLimiter

app.add_middleware(
    SecurityMiddleware,
    rate_limiter=RateLimiter(
        requests_per_minute=120,
        requests_per_hour=2000,
        burst_limit=50,
    ),
    max_body_size=2_000_000,
)

Instrumentator().instrument(app).expose(app)

_perf_logger = logging.getLogger("aria.perf")


@app.middleware("http")
async def request_timing_middleware(request, call_next):
    start = _time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (_time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    if elapsed_ms > 100:
        _perf_logger.warning(
            "Slow request: %s %s took %.1fms (status=%s)",
            request.method, request.url.path, elapsed_ms, response.status_code,
        )
    return response


@app.middleware("http")
async def correlation_middleware(request, call_next):
    try:
        from aria_mind.logging_config import correlation_id_var
    except ModuleNotFoundError:
        import contextvars as _ctx
        correlation_id_var = _ctx.ContextVar("correlation_id", default="")
    cid = request.headers.get("X-Correlation-ID", str(_uuid.uuid4())[:8])
    correlation_id_var.set(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.get("/api/metrics")
async def metrics():
    if HAS_PROMETHEUS:
        from starlette.responses import Response
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    return {"error": "prometheus_client not installed"}


# ── REST routers ─────────────────────────────────────────────────────────────

from routers.health import router as health_router
from routers.activities import router as activities_router
from routers.thoughts import router as thoughts_router
from routers.memories import router as memories_router
from routers.goals import router as goals_router
from routers.sessions import router as sessions_router
from routers.model_usage import router as model_usage_router
from routers.litellm import router as litellm_router
from routers.providers import router as providers_router
from routers.security import router as security_router
from routers.knowledge import router as knowledge_router
from routers.social import router as social_router
from routers.operations import router as operations_router
from routers.records import router as records_router
from routers.admin import router as admin_router
from routers.models_config import router as models_config_router
from routers.working_memory import router as working_memory_router
from routers.skills import router as skills_router
from routers.lessons import router as lessons_router
from routers.proposals import router as proposals_router

app.include_router(health_router)
app.include_router(activities_router)
app.include_router(thoughts_router)
app.include_router(memories_router)
app.include_router(goals_router)
app.include_router(sessions_router)
app.include_router(model_usage_router)
app.include_router(litellm_router)
app.include_router(providers_router)
app.include_router(security_router)
app.include_router(knowledge_router)
app.include_router(social_router)
app.include_router(operations_router)
app.include_router(records_router)
app.include_router(admin_router)
app.include_router(models_config_router)
app.include_router(working_memory_router)
app.include_router(skills_router)
app.include_router(lessons_router)
app.include_router(proposals_router)

# ── GraphQL ──────────────────────────────────────────────────────────────────

from gql import graphql_app as gql_router   # noqa: E402

app.include_router(gql_router, prefix="/graphql")

# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", "8000")))
