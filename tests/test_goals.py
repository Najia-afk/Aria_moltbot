# tests/test_goals.py
"""
S5-05 · Goal endpoint tests.

Uses a live API (marked @pytest.mark.integration).
Auto-skips when aria-api is unreachable.
"""

import os
import uuid

import httpx
import pytest

API_BASE = os.environ.get("ARIA_API_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def api(request):
    client = httpx.Client(base_url=API_BASE, timeout=httpx.Timeout(15.0, connect=3.0))
    try:
        r = client.get("/health")
        if r.status_code != 200:
            pytest.skip("aria-api not healthy")
    except httpx.ConnectError:
        pytest.skip("aria-api not reachable")
    yield client
    client.close()


def _json(resp, status=200):
    assert resp.status_code == status, f"Expected {status}, got {resp.status_code}: {resp.text[:300]}"
    return resp.json()


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.integration
class TestGoalsCRUD:

    def test_create_goal(self, api):
        uid = uuid.uuid4().hex[:8]
        data = _json(api.post("/goals", json={
            "title": f"Sprint QA Check {uid}",
            "description": "Automated QA validation from S5-05",
            "status": "active",
            "priority": 1,
        }))
        assert "id" in data or "goal_id" in data

    def test_list_goals_pagination(self, api):
        data = _json(api.get("/goals", params={"page": 1, "per_page": 5}))
        # Accept list or paginated dict
        if isinstance(data, dict):
            assert "items" in data or "goals" in data or "data" in data
        else:
            assert isinstance(data, list)

    def test_priority_sort_order(self, api):
        """Verify S2-01 fix: priority 1 should come first."""
        data = _json(api.get("/goals", params={"status": "active", "page": 1, "per_page": 10}))
        items = data.get("items", data) if isinstance(data, dict) else data
        if len(items) >= 2:
            assert items[0].get("priority", 99) <= items[1].get("priority", 99)

    def test_create_and_list_goal(self, api):
        """Create a goal and verify it appears in the list."""
        uid = uuid.uuid4().hex[:8]
        title = f"QA Verification {uid}"
        created = _json(api.post("/goals", json={
            "title": title,
            "description": "Verify round-trip in S5-05",
            "status": "active",
            "priority": 2,
        }))
        goal_id = created.get("id") or created.get("goal_id")
        assert goal_id
        # No GET /goals/{id} endpoint — verify via list
        data = _json(api.get("/goals", params={"page": 1, "per_page": 50}))
        items = data.get("items", data) if isinstance(data, dict) else data
        assert any(
            g.get("title") == title
            for g in items
        ), f"Created goal '{title}' not found in list"
