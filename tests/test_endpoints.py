# tests/test_endpoints.py
"""
Live endpoint tests for Aria services.
Tests actual running services via HTTP.

These tests require a running Docker stack (aria-api, aria-web)
and are skipped when the services are not available.

Route mapping:
  - API routes live under /api/ (FastAPI with root_path="/api")
  - Web pages are served by Flask on port 5000
  - /knowledge-graph is the API path (not /knowledge)
  - /heartbeat is the web page for health monitoring (not /health)
  - /health is an API-only endpoint (no web page)
"""
import os
import pytest
import requests
from typing import Any

pytestmark = pytest.mark.integration

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


# ---------------------------------------------------------------------------
# API Endpoints (FastAPI)
# ---------------------------------------------------------------------------
@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.skipif(not _HAS_API, reason="aria-api service not reachable")
class TestAPIEndpoints:
    """Tests for FastAPI backend endpoints."""

    # -- health / status ----------------------------------------------------
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

    # -- core data ----------------------------------------------------------
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

    def test_memories_endpoint(self):
        """Test /api/memories returns memories."""
        r = requests.get(f"{API_BASE}/memories", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_records_endpoint(self):
        """Test /api/records/thoughts returns records."""
        r = requests.get(f"{API_BASE}/records/thoughts", timeout=TIMEOUT)
        assert r.status_code == 200

    # -- goals & sessions ---------------------------------------------------
    def test_goals_endpoint(self):
        """Test /api/goals returns goal list."""
        r = requests.get(f"{API_BASE}/goals", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_hourly_goals_endpoint(self):
        """Test /api/hourly-goals returns goals with count."""
        r = requests.get(f"{API_BASE}/hourly-goals", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "goals" in data
        assert "count" in data

    def test_sessions_endpoint(self):
        """Test /api/sessions returns session list."""
        r = requests.get(f"{API_BASE}/sessions", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    # -- skills & social ----------------------------------------------------
    def test_skills_endpoint(self):
        """Test /api/skills returns skill list."""
        r = requests.get(f"{API_BASE}/skills", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_social_endpoint(self):
        """Test /api/social returns posts."""
        r = requests.get(f"{API_BASE}/social", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "posts" in data
        assert "count" in data

    # -- knowledge-graph (NOT /knowledge) -----------------------------------
    def test_knowledge_graph_endpoint(self):
        """Test /api/knowledge-graph returns graph data.

        NOTE: The API path is /knowledge-graph, not /knowledge.
        The Flask web page /knowledge renders knowledge.html which
        calls /api/knowledge-graph internally.
        """
        r = requests.get(f"{API_BASE}/knowledge-graph", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    # -- working memory -----------------------------------------------------
    def test_working_memory_endpoint(self):
        """Test /api/working-memory/context returns context items."""
        r = requests.get(f"{API_BASE}/working-memory/context", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    # -- operations & security ----------------------------------------------
    def test_rate_limits_endpoint(self):
        """Test /api/rate-limits returns rate limit list."""
        r = requests.get(f"{API_BASE}/rate-limits", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_security_events_endpoint(self):
        """Test /api/security-events returns events."""
        r = requests.get(f"{API_BASE}/security-events", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_schedule_endpoint(self):
        """Test /api/schedule returns scheduled jobs."""
        r = requests.get(f"{API_BASE}/schedule", timeout=TIMEOUT)
        assert r.status_code == 200

    # -- models & litellm ---------------------------------------------------
    def test_litellm_models_endpoint(self):
        """Test /api/litellm/models returns model list."""
        r = requests.get(f"{API_BASE}/litellm/models", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "data" in data or isinstance(data, list)

    def test_models_config_endpoint(self):
        """Test /api/models/config returns model catalog from models.yaml."""
        r = requests.get(f"{API_BASE}/models/config", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_model_usage_endpoint(self):
        """Test /api/litellm/spend returns spend logs."""
        r = requests.get(f"{API_BASE}/litellm/spend?limit=5", timeout=TIMEOUT)
        assert r.status_code == 200

    # -- admin / soul -------------------------------------------------------
    def test_soul_files_endpoint(self):
        """Test /api/admin/soul lists soul files."""
        r = requests.get(f"{API_BASE}/admin/soul", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))


# ---------------------------------------------------------------------------
# Web Pages (Flask)
# ---------------------------------------------------------------------------
@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.skipif(not _HAS_WEB, reason="aria-web service not reachable")
class TestWebPages:
    """Tests for Flask web pages.

    NOTE: There is NO /health web page. Health monitoring is at:
      - /heartbeat  (web page)
      - /api/health (API endpoint)
    """

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

    def test_models_page(self):
        """Test models page loads (also reachable via /litellm redirect)."""
        r = self.session.get(f"{WEB_BASE}/models", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_litellm_redirects_to_models(self):
        """Test /litellm redirects to /models."""
        r = self.session.get(f"{WEB_BASE}/litellm", timeout=TIMEOUT)
        assert r.status_code == 200

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

    def test_memories_page(self):
        """Test memories page loads."""
        r = self.session.get(f"{WEB_BASE}/memories", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_goals_page(self):
        """Test goals page loads."""
        r = self.session.get(f"{WEB_BASE}/goals", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Goal" in r.text

    def test_sessions_page(self):
        """Test sessions page loads."""
        r = self.session.get(f"{WEB_BASE}/sessions", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_skills_page(self):
        """Test skills page loads."""
        r = self.session.get(f"{WEB_BASE}/skills", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Skill" in r.text

    def test_social_page(self):
        """Test social page loads."""
        r = self.session.get(f"{WEB_BASE}/social", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_knowledge_page(self):
        """Test knowledge page loads (calls /api/knowledge-graph internally)."""
        r = self.session.get(f"{WEB_BASE}/knowledge", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_heartbeat_page(self):
        """Test heartbeat page loads (this is the health monitoring page)."""
        r = self.session.get(f"{WEB_BASE}/heartbeat", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_operations_page(self):
        """Test operations page loads."""
        r = self.session.get(f"{WEB_BASE}/operations", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_security_page(self):
        """Test security page loads."""
        r = self.session.get(f"{WEB_BASE}/security", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_performance_page(self):
        """Test performance page loads."""
        r = self.session.get(f"{WEB_BASE}/performance", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_working_memory_page(self):
        """Test working memory page loads."""
        r = self.session.get(f"{WEB_BASE}/working-memory", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_soul_page(self):
        """Test soul page loads."""
        r = self.session.get(f"{WEB_BASE}/soul", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_model_usage_page(self):
        """Test model usage page loads."""
        r = self.session.get(f"{WEB_BASE}/model-usage", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_rate_limits_page(self):
        """Test rate limits page loads."""
        r = self.session.get(f"{WEB_BASE}/rate-limits", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_wallets_page(self):
        """Test wallets page loads."""
        r = self.session.get(f"{WEB_BASE}/wallets", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_api_key_rotations_page(self):
        """Test API key rotations page loads."""
        r = self.session.get(f"{WEB_BASE}/api-key-rotations", timeout=TIMEOUT)
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


# ---------------------------------------------------------------------------
# Page Content Checks
# ---------------------------------------------------------------------------
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

    def test_goals_page_has_chart(self):
        """Test goals page has a chart canvas."""
        r = requests.get(f"{WEB_BASE}/goals", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "canvas" in r.text.lower() or "chart" in r.text.lower()

    def test_skills_page_has_seed_button(self):
        """Test skills page has the seed button."""
        r = requests.get(f"{WEB_BASE}/skills", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Seed" in r.text or "seed" in r.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
