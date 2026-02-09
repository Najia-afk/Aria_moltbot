# tests/test_endpoints.py
"""
Live endpoint tests for Aria services.
Tests actual running services via HTTP.

These tests require a running Docker stack (aria-api, aria-web)
and are skipped when the services are not available.
"""
import os
import pytest
import requests
from typing import Dict, Any

# Configuration
API_BASE = os.getenv("ARIA_API_BASE", "http://aria-api:8000/api")
WEB_BASE = os.getenv("ARIA_WEB_BASE", "http://aria-web:5000")
TIMEOUT = 5


def _can_reach(base_url: str) -> bool:
    """Check if a service is reachable."""
    try:
        requests.head(base_url.rstrip("/") + "/", timeout=2)
        return True
    except Exception:
        return False


_HAS_API = _can_reach(API_BASE.rsplit("/api", 1)[0])
_HAS_WEB = _can_reach(WEB_BASE)


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.skipif(not _HAS_API, reason="aria-api service not reachable")
class TestAPIEndpoints:
    """Tests for FastAPI backend endpoints."""

    def test_health_endpoint(self):
        """Test /api/health returns healthy status."""
        r = requests.get(f"{API_BASE}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ["ok", "healthy"]
        assert "database" in data

    def test_stats_endpoint(self):
        """Test /api/stats returns statistics."""
        r = requests.get(f"{API_BASE}/stats", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "activities_count" in data
        assert "thoughts_count" in data

    def test_status_endpoint(self):
        """Test /api/status returns service status."""
        r = requests.get(f"{API_BASE}/status", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert any(k in data for k in ["database", "litellm", "grafana"])

    def test_activities_endpoint(self):
        """Test /api/activities returns activity list."""
        r = requests.get(f"{API_BASE}/activities", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_thoughts_endpoint(self):
        """Test /api/thoughts returns thoughts list."""
        r = requests.get(f"{API_BASE}/thoughts", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_litellm_models_endpoint(self):
        """Test /api/litellm/models returns model list."""
        r = requests.get(f"{API_BASE}/litellm/models", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "data" in data or isinstance(data, list)


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.skipif(not _HAS_WEB, reason="aria-web service not reachable")
class TestWebPages:
    """Tests for Flask web pages."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for web tests."""
        self.session = requests.Session()

    def test_index_page(self):
        """Test index page loads."""
        r = self.session.get(f"{WEB_BASE}/", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Aria Blue" in r.text
        assert "<!DOCTYPE html>" in r.text

    def test_dashboard_page(self):
        """Test dashboard page loads."""
        r = self.session.get(f"{WEB_BASE}/dashboard", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Dashboard" in r.text
        assert "stats-grid" in r.text or "metric" in r.text

    def test_litellm_page(self):
        """Test LiteLLM page loads with pricing columns."""
        r = self.session.get(f"{WEB_BASE}/litellm", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "LiteLLM" in r.text
        assert "Input $/1M" in r.text or "$/1M" in r.text
        assert "Output $/1M" in r.text or "pricing" in r.text.lower()

    def test_thoughts_page(self):
        """Test thoughts page loads."""
        r = self.session.get(f"{WEB_BASE}/thoughts", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Thought" in r.text

    def test_activities_page(self):
        """Test activities page loads."""
        r = self.session.get(f"{WEB_BASE}/activities", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Activit" in r.text

    def test_records_page(self):
        """Test records page loads."""
        r = self.session.get(f"{WEB_BASE}/records", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_search_page(self):
        """Test search page loads."""
        r = self.session.get(f"{WEB_BASE}/search", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Search" in r.text or "search" in r.text

    def test_services_page(self):
        """Test services page loads."""
        r = self.session.get(f"{WEB_BASE}/services", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_css_loads(self):
        """Test CSS files load correctly."""
        css_files = [
            "/static/css/variables.css",
            "/static/css/base.css",
            "/static/css/layout.css",
            "/static/css/components.css",
        ]
        for css in css_files:
            r = self.session.get(f"{WEB_BASE}{css}", timeout=TIMEOUT)
            assert r.status_code == 200, f"Failed to load {css}"
            assert "text/css" in r.headers.get("Content-Type", "")


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.skipif(not _HAS_WEB, reason="aria-web service not reachable")
class TestPageContent:
    """Tests for specific page content elements."""

    def test_dashboard_has_stats_grid(self):
        """Test dashboard has the new stats grid."""
        r = requests.get(f"{WEB_BASE}/dashboard", timeout=TIMEOUT)
        assert r.status_code == 200
        html = r.text
        assert "stats-grid" in html or "stat-card" in html

    def test_litellm_has_spend_section(self):
        """Test LiteLLM page has spend summary section."""
        r = requests.get(f"{WEB_BASE}/litellm", timeout=TIMEOUT)
        assert r.status_code == 200
        html = r.text
        assert "spend" in html.lower() or "Total Spend" in html or "global-spend" in html

    def test_base_template_has_header(self):
        """Test pages have sticky header structure."""
        r = requests.get(f"{WEB_BASE}/dashboard", timeout=TIMEOUT)
        assert r.status_code == 200
        html = r.text
        assert "page-header" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
