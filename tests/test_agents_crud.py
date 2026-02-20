"""Agent CRUD endpoint tests — full lifecycle for /agents/db."""
import pytest

pytestmark = pytest.mark.engine

# Unique agent ID for test isolation
AGENT_ID = "test-agent-crud-auto"


class TestAgentsCRUD:
    """Full CRUD lifecycle: list → create → get → update → disable → enable → delete."""

    def test_01_list_agents(self, api):
        r = api.get("/agents/db")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_02_create_agent(self, api):
        payload = {
            "agent_id": AGENT_ID,
            "display_name": "Test CRUD Agent",
            "agent_type": "agent",
            "model": "moonshotai/kimi-k2",
            "temperature": 0.5,
            "max_tokens": 2048,
            "system_prompt": "You are a test agent.",
            "skills": ["api_client"],
            "capabilities": ["chat"],
            "enabled": True,
        }
        r = api.post("/agents/db", json=payload)
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 201, f"Create failed: {r.text}"
        data = r.json()
        assert data["agent_id"] == AGENT_ID
        assert data["display_name"] == "Test CRUD Agent"
        assert data["model"] == "moonshotai/kimi-k2"
        assert data["temperature"] == 0.5
        assert data["enabled"] is True

    def test_03_create_duplicate_agent(self, api):
        """Duplicate creation should return 409 Conflict."""
        payload = {
            "agent_id": AGENT_ID,
            "display_name": "Duplicate",
            "model": "moonshotai/kimi-k2",
        }
        r = api.post("/agents/db", json=payload)
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 409

    def test_04_get_agent(self, api):
        r = api.get(f"/agents/db/{AGENT_ID}")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["agent_id"] == AGENT_ID
        assert data["display_name"] == "Test CRUD Agent"

    def test_05_get_nonexistent_agent(self, api):
        r = api.get("/agents/db/nonexistent-agent-xyz")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_06_update_agent(self, api):
        payload = {
            "display_name": "Updated CRUD Agent",
            "temperature": 0.9,
            "skills": ["api_client", "llm"],
        }
        r = api.put(f"/agents/db/{AGENT_ID}", json=payload)
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "Updated CRUD Agent"
        assert data["temperature"] == 0.9
        assert "llm" in data["skills"]

    def test_07_update_nonexistent(self, api):
        r = api.put("/agents/db/nonexistent-xyz", json={"display_name": "X"})
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_08_disable_agent(self, api):
        r = api.post(f"/agents/db/{AGENT_ID}/disable")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "disabled"
        # Verify via GET
        r2 = api.get(f"/agents/db/{AGENT_ID}")
        assert r2.json()["enabled"] is False
        assert r2.json()["status"] == "disabled"

    def test_09_enable_agent(self, api):
        r = api.post(f"/agents/db/{AGENT_ID}/enable")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "enabled"
        # Verify via GET
        r2 = api.get(f"/agents/db/{AGENT_ID}")
        assert r2.json()["enabled"] is True

    def test_10_enable_nonexistent(self, api):
        r = api.post("/agents/db/nonexistent-xyz/enable")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_11_list_with_filters(self, api):
        """Test query parameter filtering."""
        r = api.get("/agents/db", params={"enabled": True, "agent_type": "agent"})
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for agent in data:
            assert agent["enabled"] is True
            assert agent["agent_type"] == "agent"

    def test_12_delete_agent(self, api):
        r = api.delete(f"/agents/db/{AGENT_ID}")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "deleted"
        # Verify gone
        r2 = api.get(f"/agents/db/{AGENT_ID}")
        assert r2.status_code == 404

    def test_13_delete_nonexistent(self, api):
        r = api.delete("/agents/db/nonexistent-xyz")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_14_sync_from_md(self, api):
        """Sync agents from AGENTS.md — should succeed or 500 gracefully."""
        r = api.post("/agents/db/sync")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code in (200, 500), f"Unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert data["status"] == "synced"
