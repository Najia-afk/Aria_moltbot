"""
Aria Brain — FastAPI Backend v3.0
Modular architecture with SQLAlchemy 2.0 ORM, psycopg3, and GraphQL.

All business logic lives in routers/ and graphql/ sub-packages.
This file is the slim application factory.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from config import API_VERSION
from db import async_engine, ensure_schema
from graphql import graphql_app

# ── Router imports ───────────────────────────────────────────────────────────
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


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🧠 Aria Brain API v3.0 starting up (SQLAlchemy + psycopg3)…")
    try:
        await ensure_schema()
        print("✅ Database schema ensured via SQLAlchemy")
    except Exception as e:
        print(f"⚠️ Schema bootstrap failed: {e}")
    yield
    await async_engine.dispose()
    print("🔌 Database engine disposed")


# ── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Aria Brain API",
    description="""
## Aria Blue Data API v3

Canonical data API for the Aria AI assistant ecosystem.

### Stack
- **ORM**: SQLAlchemy 2.0 async
- **Driver**: psycopg 3
- **GraphQL**: Strawberry (`/graphql`)
- **REST**: FastAPI modular routers

### Features
- Activities, Thoughts, Memories, Goals — full CRUD
- Agent sessions & model usage analytics
- LiteLLM proxy with merged spend data
- Knowledge graph traversal
- Security event tracking
- Service health monitoring
    """,
    version=API_VERSION,
    lifespan=lifespan,
    root_path="/api",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── Middleware ────────────────────────────────────────────────────────────────

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────────────────────

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

# ── GraphQL ──────────────────────────────────────────────────────────────────

app.include_router(graphql_app, prefix="/graphql")

# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
