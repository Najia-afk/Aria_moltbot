"""
Dashboard page verification — E2E tests for all Flask dashboard pages.

Verifies every registered Flask route returns HTTP 200 (or 301 redirect)
with valid HTML. This is the smoke test for the Aria dashboard after
the OpenClaw→aria_engine migration.

Tests:
- All GET routes return 200 or 301
- Pages contain expected HTML elements
- No template rendering errors
- Redirect routes work properly
- Route completeness check
"""
import os
import re
from collections.abc import Generator
from unittest.mock import patch, MagicMock

import pytest

# Set required env vars before importing the Flask app
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SERVICE_HOST", "localhost")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000/api")
os.environ.setdefault("API_INTERNAL_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Pages to verify (route, expected content substring, description)
# ---------------------------------------------------------------------------

DASHBOARD_PAGES: list[tuple[str, str, str]] = [
    # Core pages
    ("/", "aria", "Home / index page"),
    ("/activities", "activit", "Activities page"),
    ("/thoughts", "thought", "Thoughts page"),
    ("/memories", "memor", "Memories page"),
    ("/sentiment", "sentiment", "Sentiment page"),
    ("/patterns", "pattern", "Patterns page"),
    ("/records", "record", "Records page"),
    ("/search", "search", "Search page"),
    ("/models", "model", "Models page"),
    ("/heartbeat", "heartbeat", "Heartbeat page"),
    ("/knowledge", "knowledge", "Knowledge page"),
    ("/social", "social", "Social page"),
    ("/performance", "performance", "Performance page"),
    ("/security", "security", "Security page"),

    # Operations pages
    ("/sessions", "session", "Sessions page"),
    ("/working-memory", "memory", "Working memory page"),
    ("/skills", "skill", "Skills page"),
    ("/proposals", "proposal", "Proposals page"),
    ("/skill-stats", "skill", "Skill stats page"),
    ("/skill-health", "skill", "Skill health page"),
    ("/soul", "soul", "Soul page"),
    ("/model-usage", "model", "Model usage page"),

    # Engine pages
    ("/cron", "cron", "Cron page"),
    ("/cron/", "cron", "Cron page (trailing slash)"),
    ("/agents", "agent", "Agents page"),
    ("/agents/", "agent", "Agents page (trailing slash)"),
    ("/agent-dashboard", "agent", "Agent dashboard page"),
    ("/agent-dashboard/", "agent", "Agent dashboard (trailing slash)"),

    # Operations hub
    ("/operations", "operation", "Operations hub"),
    ("/operations/", "operation", "Operations hub (trailing slash)"),
    ("/operations/cron/", "cron", "Operations cron"),
    ("/operations/agents/", "agent", "Operations agents"),
    ("/operations/health/", "health", "Operations health"),

    # Chat
    ("/chat/", "chat", "Chat page"),

    # Additional pages
    ("/sprint-board", "sprint", "Sprint board"),
    ("/rate-limits", "rate", "Rate limits"),
    ("/api-key-rotations", "api", "API key rotations"),
]

# Redirect routes (route → expected redirect target)
REDIRECT_ROUTES: list[tuple[str, str, str]] = [
    ("/dashboard", "/", "Dashboard redirects to index"),
    ("/litellm", "/models", "LiteLLM redirects to models"),
    ("/wallets", "/models", "Wallets redirects to models"),
    ("/clawdbot/", "/chat/", "Legacy bot redirects to chat"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """Create a Flask app for testing."""
    from src.web.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app


@pytest.fixture(scope="module")
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture(scope="module")
def registered_routes(app):
    """Get all registered GET routes (without dynamic segments)."""
    routes: set[str] = set()
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and not rule.rule.startswith("/static"):
            # Skip routes with dynamic segments like <agent_id>
            if "<" not in rule.rule:
                routes.add(rule.rule)
    return routes


# ---------------------------------------------------------------------------
# Tests — Page rendering
# ---------------------------------------------------------------------------

class TestDashboardPages:
    """Verify all dashboard pages return 200."""

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_page_returns_200(self, client, route: str, expected: str, desc: str):
        """Each dashboard page returns HTTP 200."""
        response = client.get(route)

        assert response.status_code == 200, (
            f"Page '{desc}' ({route}) returned {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_page_contains_expected_content(self, client, route: str, expected: str, desc: str):
        """Each page contains expected content substring."""
        response = client.get(route)
        if response.status_code != 200:
            pytest.skip(f"Page {route} returned {response.status_code}")

        content = response.get_data(as_text=True).lower()
        assert expected.lower() in content, (
            f"Page '{desc}' ({route}) missing expected content '{expected}'"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_page_has_valid_html(self, client, route: str, expected: str, desc: str):
        """Each HTML page has basic structure."""
        response = client.get(route)
        if response.status_code != 200:
            pytest.skip(f"Page {route} returned {response.status_code}")

        content_type = response.content_type or ""

        # Skip non-HTML responses (metrics, plain text)
        if "json" in content_type or "text/plain" in content_type:
            return

        content = response.get_data(as_text=True)

        # Basic HTML structure checks
        assert "<html" in content.lower() or "<!doctype" in content.lower(), (
            f"Page '{desc}' ({route}) missing <html> or doctype"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_no_template_errors(self, client, route: str, expected: str, desc: str):
        """No Jinja2 template errors visible in output."""
        response = client.get(route)
        if response.status_code != 200:
            pytest.skip(f"Page {route} returned {response.status_code}")

        content = response.get_data(as_text=True)

        error_patterns = [
            "TemplateSyntaxError",
            "UndefinedError",
            "TemplateNotFound",
            "jinja2.exceptions",
            "Traceback (most recent call last)",
        ]
        for pattern in error_patterns:
            assert pattern not in content, (
                f"Page '{desc}' ({route}) contains error: '{pattern}'"
            )


# ---------------------------------------------------------------------------
# Tests — Redirect routes
# ---------------------------------------------------------------------------

class TestRedirectRoutes:
    """Verify redirect routes work correctly."""

    @pytest.mark.integration
    @pytest.mark.parametrize("route,target,desc", REDIRECT_ROUTES)
    def test_redirect_status(self, client, route: str, target: str, desc: str):
        """Redirect routes return 301 or 302."""
        response = client.get(route)
        assert response.status_code in (301, 302, 303, 307, 308), (
            f"Route '{desc}' ({route}) returned {response.status_code}, expected redirect"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,target,desc", REDIRECT_ROUTES)
    def test_redirect_target(self, client, route: str, target: str, desc: str):
        """Redirect routes point to correct target."""
        response = client.get(route)
        if response.status_code not in (301, 302, 303, 307, 308):
            pytest.skip(f"Route {route} not a redirect ({response.status_code})")

        location = response.headers.get("Location", "")
        assert target in location, (
            f"Route '{desc}' ({route}) redirects to '{location}', expected '{target}'"
        )


# ---------------------------------------------------------------------------
# Tests — Route completeness
# ---------------------------------------------------------------------------

class TestRouteCompleteness:
    """Verify route registration is complete."""

    @pytest.mark.integration
    def test_minimum_route_count(self, registered_routes: set[str]):
        """Dashboard has at least 25 registered routes."""
        # Filter out static and favicon
        real_routes = {
            r for r in registered_routes
            if not r.startswith("/static") and r != "/favicon.ico"
        }
        assert len(real_routes) >= 25, (
            f"Only {len(real_routes)} routes registered — expected at least 25. "
            f"Routes: {sorted(real_routes)}"
        )

    @pytest.mark.integration
    def test_core_routes_exist(self, registered_routes: set[str]):
        """Core routes are registered."""
        core_routes = {"/", "/activities", "/memories", "/sessions", "/skills"}
        missing = core_routes - registered_routes
        assert not missing, f"Missing core routes: {missing}"

    @pytest.mark.integration
    def test_engine_routes_exist(self, registered_routes: set[str]):
        """Engine-specific routes are registered."""
        engine_routes = {"/cron", "/agents", "/agent-dashboard", "/chat/"}
        # Check presence — some may have trailing slashes
        for route in engine_routes:
            found = route in registered_routes or route.rstrip("/") in registered_routes
            assert found, f"Engine route '{route}' not registered"

    @pytest.mark.integration
    def test_operations_routes_exist(self, registered_routes: set[str]):
        """Operations hub routes are registered."""
        ops_routes = {"/operations", "/operations/", "/operations/cron/",
                      "/operations/agents/", "/operations/health/"}
        for route in ops_routes:
            found = route in registered_routes or route.rstrip("/") in registered_routes
            assert found, f"Operations route '{route}' not registered"


# ---------------------------------------------------------------------------
# Tests — Chat page
# ---------------------------------------------------------------------------

class TestChatPage:
    """Tests specific to the chat page."""

    @pytest.mark.integration
    def test_chat_page_renders(self, client):
        """Chat page renders successfully."""
        response = client.get("/chat/")
        assert response.status_code == 200

        content = response.get_data(as_text=True).lower()
        assert "chat" in content

    @pytest.mark.integration
    def test_chat_with_session_id(self, client):
        """Chat page accepts session_id parameter."""
        response = client.get("/chat/test-session-123")
        assert response.status_code == 200
