"""
FastAPI dependencies for the Aria Brain API.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal, LiteLLMSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, with automatic rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_litellm_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-only async session to the LiteLLM database."""
    async with LiteLLMSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
