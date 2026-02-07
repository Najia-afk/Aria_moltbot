# src/database/models.py
"""
DEPRECATED — This file is NOT used in production.

The canonical database schema lives in:
    src/api/db/models.py  (SQLAlchemy 2.0 ORM with psycopg3 async driver)

The production database connects via:
    aria_skills/api_client  → HTTP to aria-api (preferred)
    aria_skills/database    → Direct asyncpg to PostgreSQL (last resort)

This file remains only for reference. Do NOT import from here.
"""
raise ImportError(
    "src/database/models.py is deprecated. "
    "Use src/api/db/models.py for DB models or aria_skills/api_client for data access."
)
