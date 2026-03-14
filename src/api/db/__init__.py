"""
Aria database layer — SQLAlchemy 2.0 ORM with psycopg3 async driver.
"""

from .models import Base

# session.py depends on `config.DATABASE_URL` which only exists inside the
# aria-api container.  When the engine imports `db.models` directly, the
# session import would fail — gracefully degrade so models stay usable.
try:
    from .session import async_engine, AsyncSessionLocal, ensure_schema, litellm_engine, LiteLLMSessionLocal
except ImportError:
    async_engine = AsyncSessionLocal = ensure_schema = litellm_engine = LiteLLMSessionLocal = None

__all__ = ["Base", "async_engine", "AsyncSessionLocal", "ensure_schema", "litellm_engine", "LiteLLMSessionLocal"]
