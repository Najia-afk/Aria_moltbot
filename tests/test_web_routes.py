"""Web UI route tests — every Flask page must return 200 HTML."""
import pytest

pytestmark = [pytest.mark.web, pytest.mark.usefixtures("_check_web_health")]

# All pages that should return 200 with HTML content
PAGES = [
    "/",
    "/activities",
    "/thoughts",
    "/memories",
    "/sentiment",
    "/patterns",
    "/records",
    "/search",
    "/services",
    "/models",
    "/goals",
    "/heartbeat",
    "/knowledge",
    "/skill-graph",
    "/social",
    "/performance",
    "/security",
    "/sessions",
    "/working-memory",
    "/skills",
    "/proposals",
    "/skill-stats",
    "/skill-health",
    "/soul",
    "/model-usage",
    "/cron",
    "/agents",
    "/agent-dashboard",
    "/rate-limits",
    "/api-key-rotations",
    "/operations",
    "/operations/cron/",
    "/operations/agents/",
    "/operations/health/",
    "/chat/",
]


class TestWebPages:
    @pytest.mark.parametrize("path", PAGES)
    def test_page_loads(self, web, path):
        r = web.get(path, follow_redirects=True)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "text/html" in r.headers.get("content-type", ""), f"{path} not HTML"


class TestWebRedirects:
    def test_dashboard_redirects(self, web):
        r = web.get("/dashboard", follow_redirects=False)
        assert r.status_code in (301, 302, 308)

    def test_litellm_redirects(self, web):
        r = web.get("/litellm", follow_redirects=False)
        assert r.status_code in (301, 302, 308)

    def test_wallets_redirects(self, web):
        r = web.get("/wallets", follow_redirects=False)
        assert r.status_code in (301, 302, 308)

    def test_clawdbot_redirects(self, web):
        r = web.get("/clawdbot/", follow_redirects=False)
        assert r.status_code in (301, 302, 308)


class TestWebApiProxy:
    """Test that the web UI proxies /api/ requests to the backend."""

    def test_api_proxy_health(self, web):
        r = web.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "healthy"

    def test_api_proxy_goals(self, web):
        r = web.get("/api/goals")
        assert r.status_code == 200
