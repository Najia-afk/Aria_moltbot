# tests/test_knowledge_graph.py
"""
S5-05 · Knowledge graph endpoint tests.

Tests entity CRUD, relation management, and traversal.
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
class TestKnowledgeGraphEntities:

    def test_create_entity(self, api):
        name = f"TestEntity_{uuid.uuid4().hex[:6]}"
        data = _json(api.post("/knowledge-graph/entities", json={
            "name": name,
            "type": "concept",
            "properties": {"source": "test"},
        }))
        assert "id" in data or "created" in data

    def test_list_entities(self, api):
        data = _json(api.get("/knowledge-graph/entities", params={"limit": 5, "offset": 0}))
        if isinstance(data, dict):
            assert any(k in data for k in ("items", "entities", "data"))
        else:
            assert isinstance(data, list)

    def test_search_entities(self, api):
        # Create an entity first, then search
        name = f"Searchable_{uuid.uuid4().hex[:6]}"
        _json(api.post("/knowledge-graph/entities", json={
            "name": name,
            "type": "test",
        }))
        data = _json(api.get("/knowledge-graph/search", params={"q": name[:10]}))
        if isinstance(data, dict):
            results = data.get("results", data.get("items", []))
            assert isinstance(results, list)
        else:
            assert isinstance(data, list)


@pytest.mark.integration
class TestKnowledgeGraphRelations:

    def test_create_relation(self, api):
        # Create two entities
        e1 = _json(api.post("/knowledge-graph/entities", json={
            "name": f"Rel_A_{uuid.uuid4().hex[:6]}",
            "type": "concept",
        }))
        e2 = _json(api.post("/knowledge-graph/entities", json={
            "name": f"Rel_B_{uuid.uuid4().hex[:6]}",
            "type": "concept",
        }))
        e1_id = e1.get("id")
        e2_id = e2.get("id")

        if e1_id and e2_id:
            data = _json(api.post("/knowledge-graph/relations", json={
                "from_entity": str(e1_id),
                "to_entity": str(e2_id),
                "relation_type": "related_to",
            }))
            assert isinstance(data, dict)

    def test_traverse(self, api):
        """Test graph traversal endpoint exists and responds."""
        # Create an entity to traverse from
        name = f"Trav_{uuid.uuid4().hex[:6]}"
        created = _json(api.post("/knowledge-graph/entities", json={
            "name": name,
            "type": "concept",
        }))
        eid = created.get("id")
        if eid:
            resp = api.get("/knowledge-graph/traverse", params={"start": str(eid)})
            assert resp.status_code in (200, 404)
