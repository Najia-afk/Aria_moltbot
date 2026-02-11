"""Shared pagination utilities for all API endpoints."""

import math
from typing import Any


def paginate_query(stmt, page: int = 1, limit: int = 25):
    """Apply offset/limit to a SQLAlchemy select statement.

    Returns (modified_stmt, offset) tuple.
    """
    offset = (max(1, page) - 1) * limit
    return stmt.offset(offset).limit(limit), offset


def build_paginated_response(
    items: list[Any], total: int, page: int, limit: int
) -> dict:
    """Build a standard paginated response dict."""
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total / limit) if limit > 0 else 0,
    }
