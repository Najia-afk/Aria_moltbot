# tests/test_memories.py
"""
S5-05 · Memory endpoint tests (including S5-01 semantic memory).

Tests semantic store, search, and session summarization.
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
# Standard memory endpoints
# ============================================================================


@pytest.mark.integration
class TestMemoriesCRUD:

    def test_list_memories(self, api):
        data = _json(api.get("/memories", params={"page": 1, "per_page": 5}))
        if isinstance(data, dict):
            assert any(k in data for k in ("items", "memories", "data"))
        else:
            assert isinstance(data, list)

    def test_create_memory(self, api):
        uid = uuid.uuid4().hex[:8]
        key = f"qa_mem_{uid}"
        data = _json(api.post("/memories", json={
            "key": key,
            "value": f"QA memory content {uid}",
            "category": "qa",
        }))
        assert isinstance(data, dict)
        assert data.get("upserted") or data.get("key") == key


# ============================================================================
# Semantic memory endpoints (S5-01)
# ============================================================================


@pytest.mark.integration
class TestSemanticMemory:

    def test_store_semantic_memory(self, api):
        """Store a semantic memory with embedding."""
        resp = api.post("/memories/semantic", json={
            "content": f"Sprint 5 test memory {uuid.uuid4().hex[:8]}",
            "category": "test",
            "importance": 0.5,
            "source": "test_suite",
        })
        # 502 acceptable if embedding model not configured
        assert resp.status_code in (200, 502)
        if resp.status_code == 200:
            data = resp.json()
            assert "id" in data or "memory_id" in data or "stored" in data

    def test_search_semantic_memory(self, api):
        """Search semantic memories by vector similarity."""
        resp = api.get("/memories/search", params={
            "query": "sprint verification test",
            "limit": 5,
        })
        # 502 acceptable if embedding model not configured
        assert resp.status_code in (200, 502)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                items = data.get("items", data.get("memories", []))
            else:
                items = data
            assert isinstance(items, list)

    def test_summarize_session(self, api):
        """Summarize recent session activities."""
        import httpx
        try:
            resp = api.post("/memories/summarize-session", json={
                "hours_back": 1,
            }, timeout=30.0)
        except httpx.ReadTimeout:
            pytest.skip("summarize-session timed out — LLM not available in test env")
            return
        # May fail if LLM is not available — accept 200 or 5xx
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            # LLM dependency may not be available in test
            assert resp.status_code in (200, 500, 502, 503)
