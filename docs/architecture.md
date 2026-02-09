# Aria Blue — Architecture Reference

## 5-Layer Architecture

All data access follows a strict layered pattern:

```
┌─────────────────────────────────────────────────┐
│  Layer 5: ARIA (LLM / Cognition / Agents)       │
│  ─ Orchestrates skills, never touches DB         │
├─────────────────────────────────────────────────┤
│  Layer 4: Skills (aria_skills/*)                 │
│  ─ Business logic, calls api_client for data     │
├─────────────────────────────────────────────────┤
│  Layer 3: API Client (aria_skills/api_client)    │
│  ─ httpx calls to aria-api REST endpoints        │
├─────────────────────────────────────────────────┤
│  Layer 2: API (src/api/)                         │
│  ─ FastAPI + SQLAlchemy ORM, the ONLY DB layer   │
├─────────────────────────────────────────────────┤
│  Layer 1: Database (PostgreSQL)                  │
│  ─ Tables, indexes, migrations                   │
└─────────────────────────────────────────────────┘
```

**Data flows one direction:** Skills → api_client → API → SQLAlchemy → DB

## Rules

| Layer | MAY import | MUST NOT import |
|-------|-----------|-----------------|
| `aria_skills/*` | `aria_skills.api_client`, `httpx` | `asyncpg`, `psycopg`, `sqlalchemy` |
| `aria_mind/*` | `aria_skills.*` | `asyncpg`, `psycopg`, `sqlalchemy` |
| `aria_agents/*` | `aria_skills.*`, `aria_mind.*` | `asyncpg`, `psycopg`, `sqlalchemy` |
| `src/api/*` | `sqlalchemy`, `db.models` | direct `asyncpg`/`psycopg` (use SQLAlchemy) |

### Deprecated Exception

`aria_skills/database/` still imports SQLAlchemy directly. It is **deprecated** —
all new code must use `api_client` instead. The architecture lint flags it as
a warning, not a violation.

## Correct vs Incorrect Code

### ✅ Correct — Skill uses api_client

```python
# aria_skills/my_skill/__init__.py
import httpx

async def get_activities(self):
    async with httpx.AsyncClient(base_url=self._api_url) as client:
        resp = await client.get("/api/activities?limit=10")
        resp.raise_for_status()
        return resp.json()
```

### ✅ Correct — Skill uses AriaAPIClient

```python
# Inside a skill that has access to the registry
result = await api_client.get_activities(limit=10)
```

### ❌ WRONG — Skill imports asyncpg directly

```python
# aria_skills/my_skill/__init__.py
import asyncpg  # ← VIOLATION

async def get_data():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM activity_log")
    await conn.close()
    return rows
```

### ❌ WRONG — Skill imports SQLAlchemy

```python
# aria_skills/my_skill/__init__.py
from sqlalchemy import select  # ← VIOLATION

async def get_data(session):
    result = await session.execute(select(ActivityLog))
    return result.scalars().all()
```

## Architecture Lint

An automated check enforces these rules:

```bash
python scripts/check_architecture.py
```

This script scans `aria_skills/`, `aria_mind/`, and `aria_agents/` for forbidden
imports (`asyncpg`, `psycopg`, `psycopg2`, `sqlalchemy`). Files inside
`aria_skills/database/` are flagged as warnings (deprecated) rather than
violations.

Run this before every PR merge. CI should gate on zero violations.

## Related

- [STRUCTURE.md](../STRUCTURE.md) — Project file layout
- [aria_skills/api_client/SKILL.md](../aria_skills/api_client/SKILL.md) — API client reference
- [src/api/](../src/api/) — FastAPI backend (Layer 2)
