"""Engine Agents & Metrics endpoint tests."""
import pytest

pytestmark = pytest.mark.engine


class TestEngineAgents:
    def test_list_agents(self, api):
        r = api.get("/engine/agents")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, (dict, list))

    def test_get_nonexistent_agent(self, api):
        r = api.get("/engine/agents/nonexistent-agent")
        assert r.status_code in (404, 503)


class TestEngineAgentMetrics:
    def test_list_metrics(self, api):
        r = api.get("/engine/agents/metrics")
        assert r.status_code in (200, 503)

    def test_get_agent_metrics(self, api):
        r = api.get("/engine/agents/metrics/default")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code} {r.text}"

    def test_get_agent_metrics_history(self, api):
        r = api.get("/engine/agents/metrics/default/history")
        if r.status_code == 503:
            pytest.skip("engine DB not accessible")
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code} {r.text}"
