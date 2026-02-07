"""
SQLAlchemy schema for Aria Brain (aria_warehouse).

LEGACY SHIM - The canonical models now live in db/models.py.
This file re-exports Base and ensure_schema for backward compatibility.
"""

from db.models import Base  # noqa: F401
from db.session import ensure_schema  # noqa: F401

# For any code that still does 'from schema import ensure_schema'
__all__ = ["Base", "ensure_schema"]
