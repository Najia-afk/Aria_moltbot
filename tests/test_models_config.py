"""Models Config endpoint tests."""
import pytest


class TestModelsConfig:
    def test_get_models_config(self, api):
        r = api.get("/models/config")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_get_models_pricing(self, api):
        r = api.get("/models/pricing")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_reload_models(self, api):
        r = api.post("/models/reload")
        assert r.status_code == 200
