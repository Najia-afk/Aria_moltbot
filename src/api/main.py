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
import asyncio
import time as _time
import traceback
import uuid as _uuid
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

# Import-path compatibility for mixed absolute/relative imports across src/api.
_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

try:
    from .config import API_VERSION, SKILL_BACKFILL_ON_STARTUP
    from .db import async_engine, ensure_schema
    from .startup_skill_backfill import run_skill_invocation_backfill
except ImportError:
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

    # S-52/S-53: Initialize Aria Engine (chat, streaming, agents)
    try:
        from aria_engine.config import EngineConfig
        from aria_engine.llm_gateway import LLMGateway
        from aria_engine.tool_registry import ToolRegistry
        from aria_engine.chat_engine import ChatEngine
        from aria_engine.streaming import StreamManager
        from aria_engine.context_manager import ContextManager
        from aria_engine.prompts import PromptAssembler
        try:
            from .db import AsyncSessionLocal
        except ImportError:
            from db import AsyncSessionLocal

        engine_cfg = EngineConfig()
        gateway = LLMGateway(engine_cfg)
        tool_registry = ToolRegistry()
        # Auto-discover tools from aria_skills/*/skill.json manifests
        try:
            tool_count = tool_registry.discover_from_manifests()
            print(f"✅ Tool registry: {tool_count} tools discovered from skill manifests")
        except Exception as te:
            print(f"⚠️  Tool manifest discovery failed (non-fatal): {te}")
        chat_engine = ChatEngine(engine_cfg, gateway, tool_registry, AsyncSessionLocal)
        stream_manager = StreamManager(engine_cfg, gateway, tool_registry, AsyncSessionLocal)
        context_manager = ContextManager(engine_cfg)
        prompt_assembler = PromptAssembler(engine_cfg)

        configure_engine(
            config=engine_cfg,
            chat_engine=chat_engine,
            stream_manager=stream_manager,
            context_manager=context_manager,
            prompt_assembler=prompt_assembler,
        )
        print("✅ Aria Engine initialized (chat + streaming + agents)")
    except Exception as e:
        print(f"⚠️  Engine init failed (chat will be degraded): {e}")

    # Seed LLM models from models.yaml → llm_models DB table
    try:
        try:
            from .models_sync import sync_models_from_yaml
        except ImportError:
            from models_sync import sync_models_from_yaml
        try:
            from .db import AsyncSessionLocal as _SeedSessionLocal
        except ImportError:
            from db import AsyncSessionLocal as _SeedSessionLocal
        seed_stats = await sync_models_from_yaml(_SeedSessionLocal)
        print(f"✅ Models synced to DB: {seed_stats['inserted']} new, {seed_stats['updated']} updated ({seed_stats['total']} total)")
    except Exception as e:
        print(f"⚠️  Models DB sync failed (non-fatal): {e}")

    # Auto-sync agents from AGENTS.md → agent_state DB table
    try:
        try:
            from .agents_sync import sync_agents_from_markdown
        except ImportError:
            from agents_sync import sync_agents_from_markdown
        try:
            from .db import AsyncSessionLocal as _AgentSessionLocal
        except ImportError:
            from db import AsyncSessionLocal as _AgentSessionLocal
        agent_stats = await sync_agents_from_markdown(_AgentSessionLocal)
        print(f"✅ Agents synced to DB: {agent_stats.get('inserted', 0)} new, {agent_stats.get('updated', 0)} updated ({agent_stats.get('total', 0)} total)")
    except Exception as e:
        print(f"⚠️  Agents DB sync failed (non-fatal): {e}")

    # S4-07: Auto-sync skill graph on startup
    try:
        try:
            from .graph_sync import sync_skill_graph
        except ImportError:
            from graph_sync import sync_skill_graph
        stats = await sync_skill_graph()
        print(f"✅ Skill graph synced: {stats['entities']} entities, {stats['relations']} relations")
    except Exception as e:
        print(f"⚠️  Skill graph sync failed (non-fatal): {e}")

    # S-54: Auto-sync cron jobs from YAML → DB
    try:
        try:
            from .cron_sync import sync_cron_jobs_from_yaml
        except ImportError:
            from cron_sync import sync_cron_jobs_from_yaml
        cron_summary = await sync_cron_jobs_from_yaml()
        print(f"✅ Cron jobs synced: {cron_summary}")
    except Exception as e:
        print(f"⚠️  Cron job sync failed (non-fatal): {e}")

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

    # S-AUTO: Background sentiment auto-scorer (zero LLM tokens)
    try:
        from .sentiment_autoscorer import run_autoscorer_loop
    except ImportError:
        from sentiment_autoscorer import run_autoscorer_loop
    scorer_task = asyncio.create_task(run_autoscorer_loop())
    print("🎯 Sentiment auto-scorer background task launched")

    yield

    # Graceful shutdown of auto-scorer
    scorer_task.cancel()
    try:
        await scorer_task
    except asyncio.CancelledError:
        pass
    print("🛑 Sentiment auto-scorer stopped")

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
        requests_per_minute=300,
        requests_per_hour=5000,
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

try:
    from .routers.health import router as health_router
    from .routers.activities import router as activities_router
    from .routers.thoughts import router as thoughts_router
    from .routers.memories import router as memories_router
    from .routers.goals import router as goals_router
    from .routers.sessions import router as sessions_router
    from .routers.model_usage import router as model_usage_router
    from .routers.litellm import router as litellm_router
    from .routers.providers import router as providers_router
    from .routers.security import router as security_router
    from .routers.knowledge import router as knowledge_router
    from .routers.social import router as social_router
    from .routers.operations import router as operations_router
    from .routers.records import router as records_router
    from .routers.admin import router as admin_router
    from .routers.models_config import router as models_config_router
    from .routers.models_crud import router as models_crud_router
    from .routers.working_memory import router as working_memory_router
    from .routers.skills import router as skills_router
    from .routers.lessons import router as lessons_router
    from .routers.proposals import router as proposals_router
    from .routers.analysis import router as analysis_router
    from .routers.engine_cron import router as engine_cron_router
    from .routers.engine_sessions import router as engine_sessions_router
    from .routers.engine_agents import router as engine_agents_router
    from .routers.engine_agent_metrics import router as engine_agent_metrics_router
    from .routers.agents_crud import router as agents_crud_router
    from .routers.engine_chat import register_engine_chat, configure_engine
except ImportError:
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
    from routers.models_crud import router as models_crud_router
    from routers.working_memory import router as working_memory_router
    from routers.skills import router as skills_router
    from routers.lessons import router as lessons_router
    from routers.proposals import router as proposals_router
    from routers.analysis import router as analysis_router
    from routers.engine_cron import router as engine_cron_router
    from routers.engine_sessions import router as engine_sessions_router
    from routers.engine_agents import router as engine_agents_router
    from routers.engine_agent_metrics import router as engine_agent_metrics_router
    from routers.agents_crud import router as agents_crud_router
    from routers.engine_chat import register_engine_chat, configure_engine

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
app.include_router(models_crud_router)
app.include_router(working_memory_router)
app.include_router(skills_router)
app.include_router(lessons_router)
app.include_router(proposals_router)
app.include_router(analysis_router)
app.include_router(engine_cron_router)
app.include_router(engine_sessions_router)
app.include_router(engine_agent_metrics_router)
app.include_router(engine_agents_router)
app.include_router(agents_crud_router)

# Engine Chat — REST + WebSocket
register_engine_chat(app)

# ── GraphQL ──────────────────────────────────────────────────────────────────

try:
    from .gql import graphql_app as gql_router   # noqa: E402
except ImportError:
    from gql import graphql_app as gql_router   # noqa: E402

app.include_router(gql_router, prefix="/graphql")

# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", "8000")))
