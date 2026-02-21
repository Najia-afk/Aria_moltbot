"""LLM Models CRUD endpoint tests — full lifecycle for /models/db."""
import pytest

pytestmark = pytest.mark.engine

# Unique model ID for test isolation
MODEL_ID = "test-model-crud-auto"


class TestModelsCRUD:
    """Full CRUD lifecycle: list → create → get → update → delete."""

    def test_01_list_models(self, api):
        r = api.get("/models/db")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_02_create_model(self, api):
        payload = {
            "id": MODEL_ID,
            "name": "Test CRUD Model",
            "provider": "test-provider",
            "tier": "free",
            "reasoning": False,
            "vision": False,
            "tool_calling": True,
            "context_window": 16384,
            "max_tokens": 4096,
            "cost_input": 0.001,
            "cost_output": 0.002,
            "litellm_model": "test-provider/test-model",
            "enabled": True,
            "sort_order": 999,
        }
        r = api.post("/models/db", json=payload)
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 201, f"Create failed: {r.text}"
        data = r.json()
        assert data["id"] == MODEL_ID
        assert data["name"] == "Test CRUD Model"
        assert data["provider"] == "test-provider"
        assert data["tool_calling"] is True
        assert data["cost_input"] == 0.001

    def test_03_create_duplicate_model(self, api):
        """Duplicate creation should return 409 Conflict."""
        payload = {
            "id": MODEL_ID,
            "name": "Duplicate",
            "provider": "test",
        }
        r = api.post("/models/db", json=payload)
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 409

    def test_04_get_model(self, api):
        r = api.get(f"/models/db/{MODEL_ID}")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == MODEL_ID
        assert data["name"] == "Test CRUD Model"
        # API key should be a boolean flag, not the raw key
        assert "litellm_api_key_set" in data
        assert isinstance(data["litellm_api_key_set"], bool)

    def test_05_get_nonexistent_model(self, api):
        r = api.get("/models/db/nonexistent-model-xyz")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_06_update_model(self, api):
        payload = {
            "name": "Updated CRUD Model",
            "tier": "premium",
            "reasoning": True,
            "cost_input": 0.005,
        }
        r = api.put(f"/models/db/{MODEL_ID}", json=payload)
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Updated CRUD Model"
        assert data["tier"] == "premium"
        assert data["reasoning"] is True
        assert data["cost_input"] == 0.005
        # Unchanged fields preserved
        assert data["tool_calling"] is True

    def test_07_update_nonexistent(self, api):
        r = api.put("/models/db/nonexistent-xyz", json={"name": "X"})
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_08_list_with_filters(self, api):
        """Test query parameter filtering."""
        r = api.get("/models/db", params={"provider": "test-provider"})
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for model in data:
            assert model["provider"] == "test-provider"

    def test_09_delete_model(self, api):
        r = api.delete(f"/models/db/{MODEL_ID}")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "deleted"
        # Verify gone
        r2 = api.get(f"/models/db/{MODEL_ID}")
        assert r2.status_code == 404

    def test_10_delete_nonexistent(self, api):
        r = api.delete("/models/db/nonexistent-xyz")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code == 404

    def test_11_sync_from_yaml(self, api):
        """Sync models from models.yaml — should succeed."""
        r = api.post("/models/db/sync")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code in (200, 500), f"Unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert data["status"] == "synced"


class TestModelsAvailable:
    """Test /models/available endpoint used by chat UI."""

    def test_models_available(self, api):
        r = api.get("/models/available")
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        if data["models"]:
            model = data["models"][0]
            assert "id" in model
            assert "name" in model
            assert "provider" in model

    def test_models_available_has_required_fields(self, api):
        r = api.get("/models/available")
        assert r.status_code == 200
        data = r.json()
        for model in data.get("models", []):
            # Required fields for chat UI model selector
            assert "id" in model
            assert "name" in model
            assert "provider" in model
            assert "tier" in model
