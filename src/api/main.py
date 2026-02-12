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
import traceback
import uuid as _uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

from config import API_VERSION, SKILL_BACKFILL_ON_STARTUP
from db import async_engine, ensure_schema
from startup_skill_backfill import run_skill_invocation_backfill

_logger = logging.getLogger("aria.api")


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

    # Auto-heal skill telemetry gaps on startup (idempotent, toggleable).
    if SKILL_BACKFILL_ON_STARTUP:
        try:
            summary = await run_skill_invocation_backfill()
            print(
                "✅ Skill invocation backfill complete: "
                f"{summary['total']} inserted "
                f"(sessions={summary['agent_sessions']}, "
                f"model_usage={summary['model_usage']}, "
                f"activity_log={summary['activity_log']})"
            )
        except Exception as e:
            print(f"⚠️  Skill invocation backfill failed (non-fatal): {e}")
    else:
        print("ℹ️  Skill invocation backfill skipped (SKILL_BACKFILL_ON_STARTUP=false)")

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


# ── Global Exception Handlers (S6-07) ────────────────────────────────────────
# Catch SQLAlchemy errors globally so missing tables return clean 503 JSON
# instead of crashing the connection (server disconnect).

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — return 500 JSON instead of disconnect."""
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__ or ""

    # SQLAlchemy ProgrammingError (missing table, bad column, etc.)
    if "ProgrammingError" in exc_type or "UndefinedTableError" in exc_type:
        _logger.error("Database schema error on %s %s: %s",
                       request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database table not available",
                "detail": str(exc).split("\n")[0][:200],
                "path": request.url.path,
                "hint": "Run ensure_schema() or check pgvector extension",
            },
        )

    # SQLAlchemy OperationalError (connection issues, etc.)
    if "OperationalError" in exc_type:
        _logger.error("Database connection error on %s %s: %s",
                       request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database connection error",
                "detail": str(exc).split("\n")[0][:200],
                "path": request.url.path,
            },
        )

    # Everything else — log full traceback but return clean JSON
    _logger.error("Unhandled exception on %s %s: %s\n%s",
                   request.method, request.url.path, exc,
                   traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)[:200],
            "type": exc_type,
            "path": request.url.path,
        },
    )


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
