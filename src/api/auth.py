"""
S-103: Authentication middleware for Aria API.

Two-tier API key authentication:
  - require_api_key: Standard access for all authenticated endpoints
  - require_admin_key: Elevated access for admin/maintenance endpoints

Keys are loaded from environment variables:
  - ARIA_API_KEY: Standard API key (fail-open if unset in dev)
  - ARIA_ADMIN_KEY: Admin API key (fail-open if unset in dev)

Health, docs, and metrics endpoints are exempt from authentication.
"""

import os
import secrets
import logging

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

_logger = logging.getLogger("aria.auth")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Keys loaded from environment at import time
ARIA_API_KEY = os.environ.get("ARIA_API_KEY", "")
ARIA_ADMIN_KEY = os.environ.get("ARIA_ADMIN_KEY", "")

if not ARIA_API_KEY:
    _logger.warning(
        "ARIA_API_KEY not set — API endpoints are UNPROTECTED (dev mode). "
        "Set ARIA_API_KEY in .env for production."
    )
if not ARIA_ADMIN_KEY:
    _logger.warning(
        "ARIA_ADMIN_KEY not set — admin endpoints are UNPROTECTED (dev mode). "
        "Set ARIA_ADMIN_KEY in .env for production."
    )


async def require_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Require valid API key for standard endpoints.

    Fail-open when ARIA_API_KEY is not configured (dev/local mode).
    In production, set ARIA_API_KEY to enforce authentication.
    """
    if not ARIA_API_KEY:
        return "no-auth-configured"
    if not api_key or not secrets.compare_digest(api_key, ARIA_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


async def require_admin_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Require admin API key for privileged endpoints.

    Fail-open when ARIA_ADMIN_KEY is not configured (dev/local mode).
    In production, set ARIA_ADMIN_KEY to enforce admin authentication.
    """
    if not ARIA_ADMIN_KEY:
        return "no-auth-configured"
    if not api_key or not secrets.compare_digest(api_key, ARIA_ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Admin access required")
    return api_key
