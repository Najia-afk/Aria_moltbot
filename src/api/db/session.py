"""
Database engine & async session factory.

Driver: psycopg 3 (postgresql+psycopg)
ORM:    SQLAlchemy 2.0 async
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateIndex, CreateTable

from config import DATABASE_URL
from .models import Base


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


# ── Engine + session factory ─────────────────────────────────────────────────

async_engine = create_async_engine(
    _as_psycopg_url(DATABASE_URL),
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Schema bootstrapping ────────────────────────────────────────────────────

async def ensure_schema() -> None:
    """Create all tables and indexes if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        for table in Base.metadata.sorted_tables:
            await conn.execute(CreateTable(table, if_not_exists=True))
            for index in table.indexes:
                await conn.execute(CreateIndex(index, if_not_exists=True))
