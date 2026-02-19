# S-55: Unify Heartbeat Systems to HeartbeatLog Table
**Epic:** E9 — Database Integration | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem

There are **two separate heartbeat systems** that use **different storage** and **neither**
writes to the `heartbeat_log` DB table:

| System | File | Writes To |
|--------|------|-----------|
| aria_mind heartbeat | `aria_mind/heartbeat.py` | `activity_log` via api_client (line 155) |
| aria_engine heartbeat | `aria_engine/heartbeat.py` | `engine_agent_state` via raw SQL |

The `HeartbeatLog` model exists in `src/api/db/models.py` (line 339):
```python
class HeartbeatLog(Base):
    __tablename__ = "heartbeat_log"
    id = Column(UUID, primary_key=True)
    beat_number = Column(Integer)
    status = Column(String(20))
    details = Column(JSONB)
    created_at = Column(DateTime)
```

The API has endpoints for it in `src/api/routers/operations.py`:
- `GET /heartbeat` — list heartbeats
- `POST /heartbeat` — create heartbeat entry
- `GET /heartbeat/latest` — most recent heartbeat

The web UI has `src/web/templates/heartbeat.html` that reads from these endpoints.

**Result:** The heartbeat page shows no data, and the `heartbeat_log` table is empty.

## Root Cause

Neither heartbeat system calls the `/heartbeat` API endpoint. The aria_mind system
calls `/activities` instead (line 155: `api_client.create_activity(action="heartbeat")`).
The aria_engine system uses raw SQL to update `engine_agent_state` directly.

The `heartbeat_log` table and its API were created but never wired to the actual
heartbeat producers.

## Fix

### Change 1: aria_engine heartbeat → also writes to HeartbeatLog via API

**File:** `aria_engine/heartbeat.py`

After each heartbeat check completes, make an HTTP call to the API:
```python
async def _record_heartbeat(self, agent_id: str, beat_number: int, status: str, details: dict):
    """Record heartbeat in the heartbeat_log table via API."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._api_base}/heartbeat",
                json={
                    "beat_number": beat_number,
                    "status": status,
                    "details": {"agent_id": agent_id, **details},
                },
                timeout=5.0,
            )
    except Exception as e:
        logger.warning("Failed to record heartbeat for %s: %s", agent_id, e)
```

### Change 2: aria_mind heartbeat → also writes to HeartbeatLog via api_client

**File:** `aria_mind/heartbeat.py`

Add a call to the heartbeat API alongside the existing activity log call:
```python
# Existing (keep):
await api_client.create_activity(action="heartbeat", ...)

# Add:
await api_client.create_heartbeat(beat_number=self.beat_count, status=status, details=details)
```

### Change 3: Add `create_heartbeat()` to api_client

**File:** `aria_skills/api_client/__init__.py`

Add method:
```python
async def create_heartbeat(self, beat_number: int, status: str, details: dict = None) -> dict:
    return await self._post("/heartbeat", json={
        "beat_number": beat_number,
        "status": status,
        "details": details or {},
    })
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Heartbeats persist via API, not direct DB |
| 2 | .env for secrets (zero in code) | ✅ | API_BASE_URL from env |
| 3 | models.yaml single source of truth | ❌ | No model names involved |
| 4 | Docker-first testing | ✅ | Must test inter-container API calls |
| 5 | aria_memories only writable path | ❌ | Writes to DB via API |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- None — can be executed independently.
- S-56 (api_client audit) should verify the new `create_heartbeat()` method.

## Verification
```bash
# 1. api_client has create_heartbeat:
grep -n "create_heartbeat" aria_skills/api_client/__init__.py
# EXPECTED: method definition found

# 2. aria_engine heartbeat records to API:
grep -n "_record_heartbeat\|/heartbeat" aria_engine/heartbeat.py
# EXPECTED: _record_heartbeat method found, POST to /heartbeat

# 3. aria_mind heartbeat calls create_heartbeat:
grep -n "create_heartbeat" aria_mind/heartbeat.py
# EXPECTED: call to api_client.create_heartbeat found

# 4. HeartbeatLog table has data after a heartbeat cycle:
docker compose exec aria-db psql -U aria_admin -d aria -c "SELECT COUNT(*) FROM heartbeat_log;"
# EXPECTED: count > 0 (after at least one heartbeat cycle)

# 5. Heartbeat API works:
curl -s http://localhost:8000/heartbeat/latest | python -m json.tool
# EXPECTED: JSON with beat_number, status, details
```

## Prompt for Agent
Read these files first:
- `aria_engine/heartbeat.py` (all ~425 lines)
- `aria_mind/heartbeat.py` (all ~200 lines)
- `src/api/routers/operations.py` — search for "heartbeat" to find the 3 endpoints
- `src/api/db/models.py` line 339 (HeartbeatLog model)
- `aria_skills/api_client/__init__.py` — search for "create_activity" to see the pattern

Steps:
1. Add `create_heartbeat()` method to `aria_skills/api_client/__init__.py` following the `create_activity()` pattern
2. In `aria_engine/heartbeat.py`, add a `_record_heartbeat()` method that POSTs to the API
3. Call `_record_heartbeat()` after each agent heartbeat check
4. In `aria_mind/heartbeat.py`, add `await api_client.create_heartbeat()` alongside the existing `create_activity()` call
5. Verify the heartbeat API returns data after a cycle

Constraints: #1 (write via API, not direct DB), #2 (API URL from env), #4 (Docker test)
