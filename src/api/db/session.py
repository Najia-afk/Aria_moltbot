"""
Database engine & async session factory.

Driver: psycopg 3 (postgresql+psycopg)
ORM:    SQLAlchemy 2.0 async
"""

import logging
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateIndex, CreateTable

from config import DATABASE_URL
from .models import Base

logger = logging.getLogger("aria.db")


# ── URL helpers ──────────────────────────────────────────────────────────────

def _as_psycopg_url(url: str) -> str:
    """Convert any PostgreSQL URL to the runtime async dialect.

    Windows: asyncpg (psycopg async has Proactor loop limitations)
    Others:  psycopg
    """
    target_prefix = (
        "postgresql+asyncpg://"
        if os.name == "nt"
        else "postgresql+psycopg://"
    )
    for prefix in (
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
        "postgresql://",
    ):
        if url.startswith(prefix):
            return url.replace(prefix, target_prefix, 1)
    return url


def _litellm_url_from(url: str) -> str:
    """Derive LiteLLM database URL from the main DATABASE_URL.

    Same host/credentials, different database name (litellm).
    postgresql://user:pass@host:5432/aria_warehouse → …/litellm
    """
    # Replace the last path segment (database name) with 'litellm'
    base = url.rsplit("/", 1)[0]
    return f"{base}/litellm"


# ── Engine + session factory ─────────────────────────────────────────────────

async_engine = create_async_engine(
    _as_psycopg_url(DATABASE_URL),
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── LiteLLM database (separate DB, same PG instance) ────────────────────────

litellm_engine = create_async_engine(
    _as_psycopg_url(_litellm_url_from(DATABASE_URL)),
    pool_size=3,
    max_overflow=5,
    pool_timeout=15,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)

LiteLLMSessionLocal = async_sessionmaker(
    litellm_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Schema bootstrapping ────────────────────────────────────────────────────

async def ensure_schema() -> None:
    """Create all tables and indexes if they don't exist.

    Installs required extensions (uuid-ossp, pg_trgm, pgvector) first,
    then creates each table individually so one failure doesn't cascade.
    """
    async with async_engine.begin() as conn:
        # Create named schemas — nothing in public
        for schema_name in ("aria_data", "aria_engine"):
            try:
                await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                logger.info("Schema '%s' ensured", schema_name)
            except Exception as e:
                logger.warning("Could not create %s schema: %s", schema_name, e)

        # Extensions — pgvector MUST be installed before SemanticMemory table
        for ext in ("uuid-ossp", "pg_trgm", "vector"):
            try:
                await conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))
                logger.info("Extension '%s' ensured", ext)
            except Exception as e:
                logger.warning("Extension '%s' not available: %s", ext, e)

        # Tables — create each individually so one failure doesn't block others
        created = []
        failed = []
        for table in Base.metadata.sorted_tables:
            try:
                await conn.execute(CreateTable(table, if_not_exists=True))
                created.append(table.name)
            except Exception as e:
                failed.append(table.name)
                logger.error("Failed to create table '%s': %s", table.name, e)

        # ── Column migrations (add columns to existing tables) ─────────
        _column_migrations = [
            # (table, column, type_sql, default)
            ("sentiment_events", "speaker", "VARCHAR(20)", None),
            ("sentiment_events", "agent_id", "VARCHAR(100)", None),
            # Agent state new columns for agent management
            ("aria_engine.agent_state", "agent_type", "VARCHAR(30)", "'agent'"),
            ("aria_engine.agent_state", "parent_agent_id", "VARCHAR(100)", None),
            ("aria_engine.agent_state", "fallback_model", "VARCHAR(200)", None),
            ("aria_engine.agent_state", "enabled", "BOOLEAN", "true"),
            ("aria_engine.agent_state", "skills", "JSONB", "'[]'::jsonb"),
            ("aria_engine.agent_state", "capabilities", "JSONB", "'[]'::jsonb"),
            ("aria_engine.agent_state", "timeout_seconds", "INTEGER", "600"),
            ("aria_engine.agent_state", "rate_limit", "JSONB", "'{}'::jsonb"),
        ]
        for tbl, col, col_type, default in _column_migrations:
            try:
                ddl = f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                if default is not None:
                    ddl += f" DEFAULT {default}"
                await conn.execute(text(ddl))
                logger.info("Column '%s.%s' ensured", tbl, col)
            except Exception as e:
                logger.warning("Column migration '%s.%s' failed: %s", tbl, col, e)

        # ── Migrate data from public.engine_* to aria_engine.* ─────────
        # One-time migration for existing deployments that had data in
        # the old public-schema tables before we moved to aria_engine.
        _migration_pairs = [
            ("engine_cron_jobs",      "aria_engine.cron_jobs"),
            ("engine_agent_state",    "aria_engine.agent_state"),
            ("engine_config",         "aria_engine.config"),
            ("engine_agent_tools",    "aria_engine.agent_tools"),
            ("engine_chat_sessions",  "aria_engine.chat_sessions"),
            ("engine_chat_messages",  "aria_engine.chat_messages"),
        ]
        for old_tbl, new_tbl in _migration_pairs:
            try:
                # Check if old table exists and has rows
                check = await conn.execute(text(
                    f"SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    f"WHERE table_schema='public' AND table_name='{old_tbl}')"
                ))
                if not check.scalar():
                    continue
                cnt = await conn.execute(text(f"SELECT count(*) FROM public.{old_tbl}"))
                row_count = cnt.scalar()
                if row_count == 0:
                    continue
                # Copy rows that don't already exist in the target
                # Use ON CONFLICT DO NOTHING to be idempotent
                pk_check = await conn.execute(text(
                    f"SELECT column_name FROM information_schema.key_column_usage "
                    f"WHERE table_schema='aria_engine' AND table_name='{new_tbl.split('.')[-1]}' "
                    f"AND constraint_name LIKE '%pkey'"
                ))
                pk_col = pk_check.scalar() or "id"
                await conn.execute(text(
                    f"INSERT INTO {new_tbl} SELECT * FROM public.{old_tbl} "
                    f"ON CONFLICT ({pk_col}) DO NOTHING"
                ))
                logger.info("Migrated %d rows from public.%s → %s", row_count, old_tbl, new_tbl)
            except Exception as e:
                logger.warning("Migration public.%s → %s failed: %s", old_tbl, new_tbl, e)

        # ── Backfill speaker/agent_id from session_messages ──────────
        try:
            await conn.execute(text("""
                UPDATE sentiment_events se
                SET speaker  = sm.role,
                    agent_id = sm.agent_id
                FROM session_messages sm
                WHERE se.message_id = sm.id
                  AND se.speaker IS NULL
            """))
            logger.info("Backfilled speaker/agent_id on sentiment_events")
        except Exception as e:
            logger.warning("Backfill speaker/agent_id failed: %s", e)

        # Indexes — same per-index error isolation
        for table in Base.metadata.sorted_tables:
            for index in table.indexes:
                try:
                    await conn.execute(CreateIndex(index, if_not_exists=True))
                except Exception as e:
                    logger.warning("Failed to create index '%s': %s", index.name, e)

        if failed:
            logger.warning("Schema bootstrap: %d tables created, %d failed: %s",
                           len(created), len(failed), failed)
        else:
            logger.info("Schema bootstrap: all %d tables ensured", len(created))


async def check_database_health() -> dict:
    """Return database health info: existing tables, missing tables, extensions."""
    expected_tables = {t.name for t in Base.metadata.sorted_tables}
    async with async_engine.connect() as conn:
        # Existing tables across both schemas
        result = await conn.execute(text(
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname IN ('aria_data', 'aria_engine')"
        ))
        existing_tables = {row[0] for row in result.all()}

        # Extensions
        result = await conn.execute(text(
            "SELECT extname FROM pg_extension"
        ))
        extensions = [row[0] for row in result.all()]

        missing = expected_tables - existing_tables
        table_status = {t: t in existing_tables for t in sorted(expected_tables)}

        return {
            "status": "ok" if not missing else "degraded",
            "tables": table_status,
            "missing": sorted(missing),
            "existing_count": len(existing_tables & expected_tables),
            "expected_count": len(expected_tables),
            "pgvector_installed": "vector" in extensions,
            "extensions": extensions,
        }
