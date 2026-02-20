"""
End-to-end smoke tests — validate the entire stack is operational.

Runs a full lifecycle: health → create data → read → update → delete.
This is the single most important test file: if smoke passes, the stack is up.
"""
import pytest


class TestStackSmoke:
    """Verify the entire Aria stack is operational."""

    def test_api_health(self, api):
        """API must be healthy."""
        r = api.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    def test_database_health(self, api):
        """Database must be connected."""
        r = api.get("/health/db")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_full_goal_lifecycle(self, api, uid):
        """Create → read → update → delete a goal."""
        # Create
        r = api.post("/goals", json={
            "title": "Improve API performance",
            "description": f"Reduce average latency on critical endpoints — run {uid}",
            "status": "active",
            "priority": 1,
        })
        assert r.status_code in (200, 201)
        data = r.json()
        if data.get("skipped"):
            pytest.skip("noise filter blocked payload")
        goal_id = data.get("id") or data.get("goal_id")
        assert goal_id

        # Read
        r = api.get(f"/goals/{goal_id}")
        assert r.status_code == 200

        # Update
        r = api.patch(f"/goals/{goal_id}", json={"status": "completed"})
        assert r.status_code == 200

        # Delete
        r = api.delete(f"/goals/{goal_id}")
        assert r.status_code in (200, 204)

        # Verify deleted
        r = api.get(f"/goals/{goal_id}")
        assert r.status_code == 404, f"Goal {goal_id} still exists after delete: {r.status_code}"

    def test_full_activity_lifecycle(self, api, uid):
        """Create and list activities."""
        r = api.post("/activities", json={
            "action": "deploy",
            "skill": "ci_cd",
            "details": {"environment": "production", "run_id": uid},
            "success": True,
        })
        assert r.status_code in (200, 201), f"Activity create failed: {r.status_code} {r.text}"
        data = r.json()
        activity_id = data.get("id") or data.get("activity_id")

        r = api.get("/activities")
        assert r.status_code == 200

        # Cleanup
        if activity_id:
            r = api.delete(f"/activities/{activity_id}")
            assert r.status_code in (200, 204, 404, 405)

    def test_full_memory_lifecycle(self, api, uid):
        """Create → read → delete a memory."""
        key = f"smoke-{uid}"
        r = api.post("/memories", json={
            "key": key,
            "content": f"Cache warmup completed for region us-east — run {uid}",
            "memory_type": "config",
        })
        assert r.status_code in (200, 201)

        r = api.get(f"/memories/{key}")
        assert r.status_code == 200

        r = api.delete(f"/memories/{key}")
        assert r.status_code in (200, 204)

    def test_full_session_lifecycle(self, api, uid):
        """Create → update → delete a session."""
        r = api.post("/sessions", json={
            "title": f"Smoke session {uid}",
            "session_type": "test",
            "agent_id": "pytest",
        })
        assert r.status_code in (200, 201)
        data = r.json()
        sid = data.get("id") or data.get("session_id")
        assert sid

        r = api.patch(f"/sessions/{sid}", json={"title": f"Updated {uid}"})
        assert r.status_code == 200

        r = api.delete(f"/sessions/{sid}")
        assert r.status_code in (200, 204)

    def test_knowledge_graph_accessible(self, api):
        """Knowledge graph must respond."""
        r = api.get("/knowledge-graph")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_skills_catalog(self, api):
        """Skills catalog must load."""
        r = api.get("/skills")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_models_config(self, api):
        """Models config must load from models.yaml."""
        r = api.get("/models/config")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_engine_chat_reachable(self, api):
        """Engine chat endpoint must respond (200 or 503)."""
        r = api.get("/engine/chat/sessions")
        assert r.status_code in (200, 503)

    def test_table_stats(self, api):
        """Table stats show DB tables."""
        r = api.get("/table-stats")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))
