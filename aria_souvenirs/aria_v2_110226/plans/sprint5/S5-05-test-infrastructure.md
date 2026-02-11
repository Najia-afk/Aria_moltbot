# S5-05: Build Test Infrastructure
**Epic:** E15 — Quality | **Priority:** P0 | **Points:** 8 | **Phase:** 4

## Problem
The `tests/` directory exists but has minimal coverage. A production system running 24/7 with 19 API endpoints, 26 skills, and continuous deployment needs automated testing to prevent regressions.

## Root Cause
No test framework set up. No CI pipeline. No test fixtures.

## Fix

### Step 1: Set up pytest + async fixtures
**File: `tests/conftest.py`** (NEW or extend)
```python
import pytest
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

TEST_API_URL = "http://localhost:8000/api"

@pytest.fixture
async def api_client():
    """HTTP client for API testing."""
    async with httpx.AsyncClient(base_url=TEST_API_URL, timeout=30) as client:
        yield client

@pytest.fixture
async def db_session():
    """Direct DB session for test assertions."""
    engine = create_async_engine("postgresql+asyncpg://aria:aria@localhost:5432/aria_test")
    async with AsyncSession(engine) as session:
        yield session
```

### Step 2: Create endpoint tests
**File: `tests/test_goals.py`** (NEW)
```python
import pytest

@pytest.mark.asyncio
async def test_create_goal(api_client):
    resp = await api_client.post("/goals", json={
        "title": "Test Goal", "description": "Auto test",
        "status": "active", "priority": 1
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data or "goal_id" in data

@pytest.mark.asyncio
async def test_list_goals_pagination(api_client):
    resp = await api_client.get("/goals?page=1&per_page=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or isinstance(data, list)

@pytest.mark.asyncio
async def test_priority_sort_order(api_client):
    """Verify S2-01 fix: priority 1 should come first."""
    resp = await api_client.get("/goals?status=active")
    data = resp.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    if len(items) >= 2:
        assert items[0].get("priority", 99) <= items[1].get("priority", 99)
```

### Step 3: Create tests for critical sprints 
- `tests/test_knowledge_graph.py` — entity CRUD, traverse, search
- `tests/test_memories.py` — semantic store/search
- `tests/test_lessons.py` — record/check lessons
- `tests/test_architecture.py` — import checks, no SQLAlchemy in skills

### Step 4: Add pytest config
**File: `pyproject.toml`** (append)
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m not slow')",
    "integration: marks tests requiring running services",
]
```

### Step 5: Create Makefile target
```makefile
test:
	docker compose exec aria-api pytest tests/ -v --tb=short

test-quick:
	docker compose exec aria-api pytest tests/ -v --tb=short -m "not slow and not integration"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Tests verify layer compliance |
| 2-6 | Standard | ✅ | Tests don't modify secrets/soul |

## Dependencies
None — can start anytime.

## Verification
```bash
# Run tests:
docker compose exec aria-api pytest tests/ -v --tb=short
# EXPECTED: all tests pass

# Check coverage:
docker compose exec aria-api pytest tests/ --cov=src/api --cov-report=term-missing
# EXPECTED: coverage report
```

## Prompt for Agent
```
Build test infrastructure for Aria.
FILES: tests/conftest.py, tests/test_goals.py, tests/test_knowledge_graph.py, tests/test_memories.py, pyproject.toml
STEPS: 1. Set up pytest+async 2. Create endpoint tests for all critical routers 3. Add pyproject config 4. Run and verify
```
