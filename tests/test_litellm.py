"""LiteLLM proxy endpoint tests."""
import pytest


class TestLiteLLM:
    def test_litellm_models(self, api):
        r = api.get("/litellm/models")
        if r.status_code in (502, 503):
            pytest.skip("LiteLLM proxy unavailable")
        assert r.status_code == 200

    def test_litellm_health(self, api):
        r = api.get("/litellm/health")
        if r.status_code in (502, 503):
            pytest.skip("LiteLLM proxy unavailable")
        assert r.status_code == 200

    def test_litellm_spend(self, api):
        r = api.get("/litellm/spend")
        if r.status_code in (502, 503):
            pytest.skip("LiteLLM proxy unavailable")
        assert r.status_code == 200

    def test_litellm_global_spend(self, api):
        r = api.get("/litellm/global-spend")
        if r.status_code in (502, 503):
            pytest.skip("LiteLLM proxy unavailable")
        assert r.status_code == 200
