"""Health & Status endpoint tests."""
import pytest


class TestHealth:
    def test_health(self, api):
        r = api.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert "version" in data

    def test_health_db(self, api):
        r = api.get("/health/db")
        assert r.status_code == 200

    def test_host_stats(self, api):
        r = api.get("/host-stats")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_status_all_services(self, api):
        r = api.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_status_single_service(self, api):
        r = api.get("/status/aria-api")
        assert r.status_code in (200, 404)  # depends on service discovery

    def test_status_unknown_service(self, api):
        r = api.get("/status/nonexistent-fake-svc")
        assert r.status_code == 404

    def test_stats(self, api):
        r = api.get("/stats")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_api_metrics(self, api):
        """GET /api/metrics -> Prometheus metrics or error JSON."""
        r = api.get("/api/metrics")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        if "text/plain" in content_type:
            # Prometheus text format
            text = r.text
            assert len(text) > 0, "Empty metrics response"
            # Should contain at least one metric line
            assert any(line and not line.startswith("#") for line in text.split("\n") if line.strip()), \
                "No metric lines found in Prometheus output"
        else:
            # JSON fallback (prometheus_client not installed)
            data = r.json()
            assert isinstance(data, dict)
