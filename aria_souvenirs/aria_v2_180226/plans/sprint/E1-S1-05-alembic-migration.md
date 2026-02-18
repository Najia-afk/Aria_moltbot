# S1-05: Alembic Migration for `aria_engine` Schema
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
The new `aria_engine` PostgreSQL schema (6 tables: `chat_sessions`, `chat_messages`, `cron_jobs`, `agent_state`, `config`, `agent_tools`) needs to be created via Alembic migration alongside the existing 45 `public` schema tables.

## Root Cause
The current database uses SQLAlchemy `ensure_schema()` in `src/api/db/session.py` which calls `Base.metadata.create_all()`. The `aria_engine` schema tables need proper Alembic migrations for:
- Schema creation (`CREATE SCHEMA IF NOT EXISTS aria_engine`)
- Table creation with all indexes and constraints
- Forward/backward migration support
- Production-safe deployment

## Fix
### New ORM models in `src/api/db/models.py`
Add at the end of the file:

```python
# ── Aria Engine (v2.0) ───────────────────────────────────────────────────────
# Standalone engine tables — replaces OpenClaw runtime state

class EngineBase(DeclarativeBase):
    """Base for aria_engine schema tables."""
    __abstract__ = True
    metadata = MetaData(schema="aria_engine")


class EngineChatSession(Base):
    __tablename__ = "engine_chat_sessions"
    
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'main'"))
    session_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'interactive'"))
    title: Mapped[str | None] = mapped_column(String(500))
    system_prompt: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(200))
    temperature: Mapped[float] = mapped_column(Float, server_default=text("0.7"))
    max_tokens: Mapped[int] = mapped_column(Integer, server_default=text("4096"))
    context_window: Mapped[int] = mapped_column(Integer, server_default=text("50"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    message_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    total_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    total_cost: Mapped[float] = mapped_column(Numeric(10, 6), server_default=text("0"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["EngineChatMessage"]] = relationship("EngineChatMessage", back_populates="session", cascade="all, delete-orphan")


class EngineChatMessage(Base):
    __tablename__ = "engine_chat_messages"
    
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    session_id: Mapped[Any] = mapped_column(UUID(as_uuid=True), ForeignKey("engine_chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)
    tool_results: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(200))
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Numeric(10, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    session: Mapped["EngineChatSession"] = relationship("EngineChatSession", back_populates="messages")


class EngineCronJob(Base):
    __tablename__ = "engine_cron_jobs"
    
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(100), server_default=text("'main'"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    payload_type: Mapped[str] = mapped_column(String(50), server_default=text("'prompt'"))
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    session_mode: Mapped[str] = mapped_column(String(50), server_default=text("'isolated'"))
    max_duration_seconds: Mapped[int] = mapped_column(Integer, server_default=text("300"))
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(20))
    last_duration_ms: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    fail_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class EngineAgentState(Base):
    __tablename__ = "engine_agent_state"
    
    agent_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, server_default=text("0.7"))
    max_tokens: Mapped[int] = mapped_column(Integer, server_default=text("4096"))
    system_prompt: Mapped[str | None] = mapped_column(Text)
    focus_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'idle'"))
    current_session_id: Mapped[Any | None] = mapped_column(UUID(as_uuid=True))
    current_task: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pheromone_score: Mapped[float] = mapped_column(Numeric(5, 3), server_default=text("0.500"))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class EngineConfig(Base):
    __tablename__ = "engine_config"
    
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_by: Mapped[str] = mapped_column(String(100), server_default=text("'system'"))


class EngineAgentTool(Base):
    __tablename__ = "engine_agent_tools"
    
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    function_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
```

### Alembic migration file
```python
# src/api/alembic/versions/xxxx_add_aria_engine_tables.py
"""Add aria engine tables for standalone runtime.

Revision ID: auto-generated
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Engine chat sessions
    op.create_table(
        "engine_chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", sa.String(100), nullable=False, server_default="main"),
        sa.Column("session_type", sa.String(50), nullable=False, server_default="interactive"),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("temperature", sa.Float, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, server_default="4096"),
        sa.Column("context_window", sa.Integer, server_default="50"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("total_cost", sa.Numeric(10, 6), server_default="0"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_ecs_agent", "engine_chat_sessions", ["agent_id"])
    op.create_index("idx_ecs_status", "engine_chat_sessions", ["status"])
    op.create_index("idx_ecs_created", "engine_chat_sessions", ["created_at"])

    # Engine chat messages
    op.create_table(
        "engine_chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("engine_chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("thinking", sa.Text, nullable=True),
        sa.Column("tool_calls", JSONB, nullable=True),
        sa.Column("tool_results", JSONB, nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("tokens_input", sa.Integer, nullable=True),
        sa.Column("tokens_output", sa.Integer, nullable=True),
        sa.Column("cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ecm_session", "engine_chat_messages", ["session_id"])
    op.create_index("idx_ecm_role", "engine_chat_messages", ["role"])
    op.create_index("idx_ecm_created", "engine_chat_messages", ["created_at"])

    # Engine cron jobs
    op.create_table(
        "engine_cron_jobs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("schedule", sa.String(100), nullable=False),
        sa.Column("agent_id", sa.String(100), server_default="main"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("payload_type", sa.String(50), server_default="prompt"),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("session_mode", sa.String(50), server_default="isolated"),
        sa.Column("max_duration_seconds", sa.Integer, server_default="300"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
        sa.Column("last_duration_ms", sa.Integer, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer, server_default="0"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("fail_count", sa.Integer, server_default="0"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ecj_enabled", "engine_cron_jobs", ["enabled"])
    op.create_index("idx_ecj_next_run", "engine_cron_jobs", ["next_run_at"])

    # Engine agent state
    op.create_table(
        "engine_agent_state",
        sa.Column("agent_id", sa.String(100), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("temperature", sa.Float, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, server_default="4096"),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("focus_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("current_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("current_task", sa.Text, nullable=True),
        sa.Column("consecutive_failures", sa.Integer, server_default="0"),
        sa.Column("pheromone_score", sa.Numeric(5, 3), server_default="0.500"),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # Engine config (key-value store)
    op.create_table(
        "engine_config",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.String(100), server_default="system"),
    )

    # Engine agent tools
    op.create_table(
        "engine_agent_tools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("function_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("parameters", JSONB, server_default="{}"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_eat_agent", "engine_agent_tools", ["agent_id"])


def downgrade():
    op.drop_table("engine_agent_tools")
    op.drop_table("engine_config")
    op.drop_table("engine_agent_state")
    op.drop_table("engine_cron_jobs")
    op.drop_table("engine_chat_messages")
    op.drop_table("engine_chat_sessions")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | DB schema at Layer 0 (data layer) |
| 2 | .env for secrets | ✅ | DATABASE_URL from env |
| 3 | models.yaml | ❌ | No model references |
| 4 | Docker-first | ✅ | Migration runs in Docker container |
| 5 | aria_memories writable | ❌ | Database writes only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-01 must complete first (needs aria_engine package for model imports)

## Verification
```bash
# 1. Migration generates:
cd src/api && alembic revision --autogenerate -m "add aria engine tables"
# EXPECTED: new migration file created

# 2. Migration applies:
cd src/api && alembic upgrade head
# EXPECTED: 6 tables created

# 3. Tables exist:
python -c "
from db import async_engine
from db.models import EngineChatSession, EngineCronJob, EngineAgentState
print('Models imported OK')
"
# EXPECTED: Models imported OK
```

## Prompt for Agent
```
Create Alembic migration for 6 new aria_engine tables.

FILES TO READ FIRST:
- src/api/db/models.py (full file — existing 45 table models)
- src/api/db/session.py (full file — engine setup, ensure_schema)
- src/api/alembic/env.py (full file — Alembic config)
- src/api/alembic.ini (Alembic config)
- MASTER_PLAN.md "New PostgreSQL Schema" section

STEPS:
1. Add 6 new ORM model classes to src/api/db/models.py
2. Create Alembic migration with alembic revision --autogenerate
3. Review generated migration for correctness
4. Test with alembic upgrade head
5. Verify tables created

CONSTRAINTS:
- Constraint 1: Tables are at the DB layer — accessed only via ORM
- Constraint 2: DATABASE_URL from environment
- Constraint 4: Must work in Docker (aria-db container)
```
