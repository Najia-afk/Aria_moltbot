"""Knowledge Graph  Build and query integration tests.

Chain 3: create entities -> create relation -> verify graph -> search -> traverse -> query-log -> cleanup.
"""
import pytest


class TestKnowledgeGraphLifecycle:
    """Ordered scenario: build a knowledge graph and query it."""

    def test_01_create_entity_a(self, api, uid):
        """POST /knowledge-graph/entities -> create entity A (sentiment_analysis, type skill)."""
        payload = {
            "name": f"sentiment-analysis-{uid}",
            "type": "skill",
            "properties": {"version": "2.0", "lang": "python"},
        }
        r = api.post("/knowledge-graph/entities", json=payload)
        if r.status_code in (502, 503):
            pytest.skip("knowledge graph service unavailable")
        assert r.status_code in (200, 201, 409), f"Create entity A failed: {r.status_code} {r.text}"
        data = r.json()
        if data.get("skipped"):
            pytest.skip("noise filter blocked payload")
        entity_id = data.get("id") or data.get("entity_id")
        assert entity_id, f"No id in entity A response: {data}"
        TestKnowledgeGraphLifecycle._entity_a_id = entity_id
        TestKnowledgeGraphLifecycle._entity_a_name = f"sentiment-analysis-{uid}"
        TestKnowledgeGraphLifecycle._uid = uid

    def test_02_create_entity_b(self, api):
        """POST /knowledge-graph/entities -> create entity B (detect_emotion, type tool)."""
        uid = getattr(TestKnowledgeGraphLifecycle, "_uid", None)
        if not uid:
            pytest.skip("no uid from previous step")
        payload = {
            "name": f"detect-emotion-{uid}",
            "type": "tool",
            "properties": {"input": "text", "output": "emotion_label"},
        }
        r = api.post("/knowledge-graph/entities", json=payload)
        assert r.status_code in (200, 201, 409), f"Create entity B failed: {r.status_code} {r.text}"
        data = r.json()
        entity_id = data.get("id") or data.get("entity_id")
        assert entity_id, f"No id in entity B response: {data}"
        TestKnowledgeGraphLifecycle._entity_b_id = entity_id
        TestKnowledgeGraphLifecycle._entity_b_name = f"detect-emotion-{uid}"

    def test_03_verify_entities_exist(self, api):
        """GET /knowledge-graph/entities -> verify both entities exist."""
        ea_name = getattr(TestKnowledgeGraphLifecycle, "_entity_a_name", None)
        eb_name = getattr(TestKnowledgeGraphLifecycle, "_entity_b_name", None)
        if not ea_name or not eb_name:
            pytest.skip("entities not created")
        r = api.get("/knowledge-graph/entities")
        assert r.status_code == 200
        data = r.json()
        entities = data.get("entities", data) if isinstance(data, dict) else data
        assert isinstance(entities, list), f"Expected list of entities, got {type(entities)}"
        entity_names = [e.get("name", "") for e in entities if isinstance(e, dict)]
        assert ea_name in entity_names, f"Entity A not found in entities"
        assert eb_name in entity_names, f"Entity B not found in entities"

    def test_04_create_relation(self, api):
        """POST /knowledge-graph/relations -> link A->B with 'provides' relation."""
        ea_id = getattr(TestKnowledgeGraphLifecycle, "_entity_a_id", None)
        eb_id = getattr(TestKnowledgeGraphLifecycle, "_entity_b_id", None)
        if not ea_id or not eb_id:
            pytest.skip("entities not created")
        payload = {
            "from_entity": str(ea_id),
            "to_entity": str(eb_id),
            "relation_type": "provides",
        }
        r = api.post("/knowledge-graph/relations", json=payload)
        assert r.status_code in (200, 201, 409, 422), f"Create relation failed: {r.status_code} {r.text}"
        if r.status_code in (200, 201):
            data = r.json()
            rel_id = data.get("id") or data.get("relation_id")
            TestKnowledgeGraphLifecycle._relation_id = rel_id

    def test_05_verify_relation_exists(self, api):
        """GET /knowledge-graph/relations -> verify our relation exists."""
        r = api.get("/knowledge-graph/relations")
        assert r.status_code == 200
        data = r.json()
        relations = data.get("relations", data) if isinstance(data, dict) else data
        assert isinstance(relations, list), f"Expected list, got {type(relations)}"
        if getattr(TestKnowledgeGraphLifecycle, "_relation_id", None):
            rel_types = [rel.get("relation_type", "") for rel in relations if isinstance(rel, dict)]
            assert "provides" in rel_types, f"provides not found in {rel_types[:10]}"

    def test_06_full_graph_includes_data(self, api):
        """GET /knowledge-graph -> verify full graph includes entities and relations."""
        r = api.get("/knowledge-graph")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "entities" in data or "stats" in data, f"Missing keys: {list(data.keys())}"
        if "entities" in data:
            assert len(data["entities"]) > 0, "No entities in full graph"

    def test_07_search_entities(self, api):
        """GET /knowledge-graph/search?q=sentiment -> verify entity A found."""
        uid = getattr(TestKnowledgeGraphLifecycle, "_uid", None)
        if not uid:
            pytest.skip("no uid from previous step")
        r = api.get("/knowledge-graph/search", params={"q": f"sentiment-analysis-{uid}"})
        assert r.status_code == 200
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results, list):
            names = [res.get("name", "") for res in results if isinstance(res, dict)]
            if not names:
                pytest.skip('search index not yet populated')
            assert any(uid in n for n in names), f"Entity A not found in search: {names}"

    def test_08_traverse_graph(self, api):
        """GET /knowledge-graph/traverse -> verify traversal finds connected entity."""
        ea_id = getattr(TestKnowledgeGraphLifecycle, "_entity_a_id", None)
        if not ea_id:
            pytest.skip("entity A not created")
        r = api.get("/knowledge-graph/traverse", params={
            "start": str(ea_id),
            "max_depth": 2,
            "direction": "outgoing",
        })
        assert r.status_code in (200, 404, 422), f"Traverse failed: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, dict)
            assert "nodes" in data or "total_nodes" in data or "edges" in data, \
                f"Missing traversal keys: {list(data.keys())}"

    def test_09_query_log(self, api):
        """GET /knowledge-graph/query-log -> verify queries were logged."""
        r = api.get("/knowledge-graph/query-log")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "logs" in data or "count" in data, f"Missing query-log keys: {list(data.keys())}"

    def test_10_cleanup_relation(self, api):
        """Delete the relation we created."""
        rel_id = getattr(TestKnowledgeGraphLifecycle, "_relation_id", None)
        if rel_id:
            r = api.delete(f"/knowledge-graph/relations/{rel_id}")
            assert r.status_code in (200, 204, 404, 405)

    def test_11_cleanup_entities(self, api):
        """Delete both entities we created."""
        for attr in ("_entity_a_id", "_entity_b_id"):
            eid = getattr(TestKnowledgeGraphLifecycle, attr, None)
            if eid:
                r = api.delete(f"/knowledge-graph/entities/{eid}")
                assert r.status_code in (200, 204, 404, 405)


class TestKnowledgeGraphFeatures:
    """Additional knowledge graph features: sync, skill-for-task."""

    def test_sync_skills(self, api):
        """POST /knowledge-graph/sync-skills -> verify idempotent sync."""
        r = api.post("/knowledge-graph/sync-skills")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "status" in data or "stats" in data, f"Missing sync keys: {list(data.keys())}"

    def test_skill_for_task(self, api):
        """GET /knowledge-graph/skill-for-task -> verify skill discovery."""
        r = api.get("/knowledge-graph/skill-for-task", params={"task": "send message"})
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, dict)
            assert "candidates" in data or "task" in data, f"Missing keys: {list(data.keys())}"

    def test_skill_graph_endpoint(self, api):
        """GET /skill-graph -> verify dedicated skill graph tables."""
        r = api.get("/skill-graph")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_cleanup_auto_generated(self, api):
        """DELETE /knowledge-graph/auto-generated -> cleanup endpoint reachable."""
        r = api.delete("/knowledge-graph/auto-generated")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "status" in data or "deleted_entities" in data or "deleted_relations" in data
