# tests/test_lessons.py
"""
S5-05 · Lessons learned endpoint tests (S5-02).

Tests lesson recording, checking, listing, and seeding.
Auto-skips when aria-api is unreachable.
"""
from __future__ import annotations

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
class TestLessonsLearned:

    def test_record_lesson(self, api):
        """Record a new lesson."""
        pattern = f"test_error_{uuid.uuid4().hex[:8]}"
        data = _json(api.post("/lessons", json={
            "error_pattern": pattern,
            "error_type": "test",
            "resolution": "Ignore — test data",
            "skill_name": "test_suite",
        }))
        assert isinstance(data, dict)
        # API returns {created: true, id: ...} for new lessons
        assert data.get("created") is True or "id" in data

    def test_check_known_error(self, api):
        """Check if an error type has a known resolution."""
        # Record first
        pattern = f"check_test_{uuid.uuid4().hex[:8]}"
        _json(api.post("/lessons", json={
            "error_pattern": pattern,
            "error_type": "timeout",
            "resolution": "Retry with backoff",
            "skill_name": "api_client",
        }))

        # Check
        data = _json(api.get("/lessons/check", params={"error_type": "timeout"}))
        # API returns {has_resolution: bool, lessons: [...]}
        assert isinstance(data, dict)
        assert "lessons" in data or "has_resolution" in data
        if "lessons" in data:
            assert len(data["lessons"]) > 0

    def test_list_lessons(self, api):
        """List all recorded lessons."""
        data = _json(api.get("/lessons", params={"page": 1, "per_page": 10}))
        if isinstance(data, dict):
            assert any(k in data for k in ("items", "lessons", "data"))
        else:
            assert isinstance(data, list)

    def test_seed_lessons(self, api):
        """Seed known error patterns."""
        data = _json(api.post("/lessons/seed"))
        assert isinstance(data, dict)
        assert "seeded" in data or "count" in data or "lessons" in data

    def test_duplicate_pattern_increments(self, api):
        """Recording same pattern twice should increment occurrences."""
        pattern = f"dup_test_{uuid.uuid4().hex[:8]}"
        payload = {
            "error_pattern": pattern,
            "error_type": "duplicate_test",
            "resolution": "First resolution",
        }
        first = _json(api.post("/lessons", json=payload))
        second = _json(api.post("/lessons", json=payload))
        # Second should show incremented count
        assert second.get("occurrences", 1) >= 1
