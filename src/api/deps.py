"""
FastAPI dependencies for the Aria Brain API.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, with automatic rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
