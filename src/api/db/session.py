"""
Database engine & async session factory.

Driver: psycopg 3 (postgresql+psycopg)
ORM:    SQLAlchemy 2.0 async
"""

import logging
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
    """Convert any PostgreSQL URL to the psycopg3 async dialect."""
    for prefix in (
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
        "postgresql://",
    ):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql+psycopg://", 1)
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
        # Existing tables
        result = await conn.execute(text(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
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
