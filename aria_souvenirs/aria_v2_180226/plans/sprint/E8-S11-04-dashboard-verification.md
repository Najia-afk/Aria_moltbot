# S11-04: Dashboard Page Verification
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 11

## Problem
Aria Blue has 25+ Flask dashboard pages served by `aria_mind/gateway.py`. After removing OpenClaw and migrating to `aria_engine`, every single page must return HTTP 200 with valid HTML. A single broken page means operators lose visibility into the system. We need an automated test that checks every registered route.

## Root Cause
Dashboard pages depend on template rendering, database queries, session state, and skill data. Any change to the backend (especially the OpenClaw→aria_engine migration) can silently break pages — the only way to know is to request every URL and verify it renders.

## Fix
### `tests/integration/test_dashboard_verification.py`
```python
"""
Dashboard page verification — E2E tests for all Flask pages.

Verifies every registered Flask route returns HTTP 200 with valid HTML.
This is the "smoke test" for the Aria dashboard after the migration.

Tests:
- All GET routes return 200
- Pages contain expected HTML elements
- No template rendering errors
- Navigation links work
- Dashboard-specific data renders
"""
import re
from collections.abc import Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient


# ---------------------------------------------------------------------------
# Pages to verify (route, expected content substring, description)
# ---------------------------------------------------------------------------

DASHBOARD_PAGES: list[tuple[str, str, str]] = [
    # Core pages
    ("/", "Aria", "Home / index page"),
    ("/dashboard", "dashboard", "Main dashboard"),
    ("/chat", "chat", "Chat interface"),
    ("/status", "status", "System status"),

    # Agent pages
    ("/agents", "agent", "Agent list"),
    ("/agents/researcher", "researcher", "Researcher agent detail"),
    ("/agents/coder", "coder", "Coder agent detail"),
    ("/agents/analyst", "analyst", "Analyst agent detail"),
    ("/agents/writer", "writer", "Writer agent detail"),
    ("/agents/ops", "ops", "Ops agent detail"),
    ("/agents/coordinator", "coordinator", "Coordinator agent detail"),

    # Skill pages
    ("/skills", "skill", "Skill catalog"),
    ("/skills/health", "health", "Health skill detail"),

    # Memory pages
    ("/memory", "memory", "Memory browser"),
    ("/memory/search", "search", "Memory search"),

    # Session pages
    ("/sessions", "session", "Session list"),

    # Schedule pages
    ("/schedule", "schedule", "Cron schedule"),
    ("/schedule/history", "history", "Scheduler history"),

    # Monitoring pages
    ("/health", "ok", "Health check endpoint"),
    ("/health/dashboard", "health", "Health dashboard"),
    ("/metrics", "aria_", "Prometheus metrics"),

    # Goals & Plans
    ("/goals", "goal", "Goals page"),
    ("/goals/sprint", "sprint", "Sprint goals"),

    # Knowledge pages
    ("/knowledge", "knowledge", "Knowledge graph"),

    # Settings
    ("/settings", "settings", "Settings page"),
    ("/settings/models", "model", "Model configuration"),
]

# API endpoints (return JSON)
API_ENDPOINTS: list[tuple[str, str, str]] = [
    ("/api/status", "status", "API status"),
    ("/api/health", "ok", "API health check"),
    ("/api/agents", "agents", "API agent list"),
    ("/api/sessions", "sessions", "API session list"),
    ("/api/skills", "skills", "API skill list"),
    ("/api/models", "models", "API model list"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app() -> Generator[Flask, None, None]:
    """Create a Flask app for testing."""
    from aria_mind.gateway import create_app

    app = create_app(testing=True)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for tests
    yield app


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    """Create a test client."""
    return app.test_client()


@pytest.fixture(scope="module")
def registered_routes(app: Flask) -> set[str]:
    """Get all registered GET routes."""
    routes: set[str] = set()
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and not rule.rule.startswith("/static"):
            # Skip routes with dynamic segments for now
            if "<" not in rule.rule:
                routes.add(rule.rule)
    return routes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardPages:
    """Verify all dashboard pages return 200."""

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_page_returns_200(self, client: FlaskClient, route: str, expected: str, desc: str):
        """Each dashboard page returns HTTP 200."""
        response = client.get(route)

        assert response.status_code == 200, (
            f"Page '{desc}' ({route}) returned {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_page_contains_expected_content(
        self, client: FlaskClient, route: str, expected: str, desc: str,
    ):
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
    def test_page_has_valid_html(
        self, client: FlaskClient, route: str, expected: str, desc: str,
    ):
        """Each HTML page has basic structure."""
        response = client.get(route)
        if response.status_code != 200:
            pytest.skip(f"Page {route} returned {response.status_code}")

        content_type = response.content_type or ""

        # Skip non-HTML responses (metrics, API endpoints)
        if "json" in content_type or "text/plain" in content_type:
            return

        content = response.get_data(as_text=True)

        # Basic HTML structure checks
        assert "<html" in content.lower() or "<!doctype" in content.lower(), (
            f"Page '{desc}' ({route}) missing <html> tag"
        )
        assert "</html>" in content.lower(), (
            f"Page '{desc}' ({route}) missing closing </html>"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", DASHBOARD_PAGES)
    def test_no_template_errors(
        self, client: FlaskClient, route: str, expected: str, desc: str,
    ):
        """No Jinja2 template errors visible in output."""
        response = client.get(route)
        if response.status_code != 200:
            pytest.skip(f"Page {route} returned {response.status_code}")

        content = response.get_data(as_text=True)

        # Jinja2 error patterns
        assert "TemplateSyntaxError" not in content
        assert "UndefinedError" not in content
        assert "TemplateNotFound" not in content
        assert "jinja2.exceptions" not in content
        # Python traceback in HTML
        assert "Traceback (most recent call last)" not in content


class TestAPIEndpoints:
    """Verify API endpoints return valid JSON."""

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", API_ENDPOINTS)
    def test_api_returns_200(self, client: FlaskClient, route: str, expected: str, desc: str):
        """API endpoints return 200."""
        response = client.get(route)
        assert response.status_code == 200, (
            f"API '{desc}' ({route}) returned {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.parametrize("route,expected,desc", API_ENDPOINTS)
    def test_api_returns_json(self, client: FlaskClient, route: str, expected: str, desc: str):
        """API endpoints return valid JSON."""
        response = client.get(route)
        if response.status_code != 200:
            pytest.skip(f"API {route} returned {response.status_code}")

        assert response.content_type is not None
        assert "json" in response.content_type, (
            f"API '{desc}' ({route}) returned {response.content_type}, expected JSON"
        )

        data = response.get_json()
        assert data is not None, f"API '{desc}' ({route}) returned invalid JSON"


class TestRouteCompleteness:
    """Verify all registered routes are tested."""

    @pytest.mark.integration
    def test_no_untested_routes(self, registered_routes: set[str]):
        """All registered GET routes have corresponding tests."""
        tested_routes = {route for route, _, _ in DASHBOARD_PAGES + API_ENDPOINTS}

        untested = registered_routes - tested_routes
        # Filter out known special routes
        special = {"/static", "/favicon.ico", "/robots.txt", "/sitemap.xml"}
        untested = {r for r in untested if not any(r.startswith(s) for s in special)}

        if untested:
            pytest.fail(
                f"Untested routes found — add them to DASHBOARD_PAGES or API_ENDPOINTS:\n"
                + "\n".join(f"  {r}" for r in sorted(untested))
            )

    @pytest.mark.integration
    def test_minimum_route_count(self, registered_routes: set[str]):
        """Dashboard has at least 25 registered routes."""
        # Filter out static files
        real_routes = {r for r in registered_routes if not r.startswith("/static")}
        assert len(real_routes) >= 25, (
            f"Only {len(real_routes)} routes registered — expected at least 25. "
            f"Routes: {sorted(real_routes)}"
        )


class TestNavigationLinks:
    """Verify navigation links point to valid routes."""

    @pytest.mark.integration
    def test_main_nav_links_valid(self, client: FlaskClient, registered_routes: set[str]):
        """All navigation links in the dashboard point to valid routes."""
        response = client.get("/dashboard")
        if response.status_code != 200:
            pytest.skip("Dashboard page not available")

        content = response.get_data(as_text=True)

        # Extract href values
        hrefs = re.findall(r'href="(/[^"]*)"', content)

        invalid_links: list[str] = []
        for href in hrefs:
            # Skip external links, anchors, static files
            if href.startswith("//") or href.startswith("/static") or "#" in href:
                continue

            # Check if route exists
            link_response = client.get(href)
            if link_response.status_code not in (200, 301, 302, 308):
                invalid_links.append(f"{href} → {link_response.status_code}")

        assert not invalid_links, (
            f"Invalid navigation links found:\n"
            + "\n".join(f"  {link}" for link in invalid_links)
        )


class TestDashboardData:
    """Verify dashboard shows real data (not empty)."""

    @pytest.mark.integration
    def test_agent_list_shows_agents(self, client: FlaskClient):
        """Agent list page shows registered agents."""
        response = client.get("/agents")
        if response.status_code != 200:
            pytest.skip("Agents page not available")

        content = response.get_data(as_text=True).lower()
        # Should show at least some agent names
        assert any(
            name in content
            for name in ["researcher", "coder", "analyst", "writer", "ops", "coordinator"]
        ), "Agent list page shows no agent names"

    @pytest.mark.integration
    def test_skill_catalog_shows_skills(self, client: FlaskClient):
        """Skill catalog page shows registered skills."""
        response = client.get("/skills")
        if response.status_code != 200:
            pytest.skip("Skills page not available")

        content = response.get_data(as_text=True).lower()
        assert any(
            skill in content
            for skill in ["health", "llm", "research", "brainstorm", "memory"]
        ), "Skill catalog page shows no skill names"

    @pytest.mark.integration
    def test_status_page_shows_system_info(self, client: FlaskClient):
        """Status page shows system information."""
        response = client.get("/status")
        if response.status_code != 200:
            pytest.skip("Status page not available")

        content = response.get_data(as_text=True).lower()
        assert any(
            info in content
            for info in ["version", "uptime", "python", "database", "status"]
        ), "Status page shows no system information"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Tests the web/API layer |
| 2 | .env for secrets | ✅ | TEST_DATABASE_URL |
| 3 | models.yaml single source | ❌ | No LLM calls |
| 4 | Docker-first testing | ✅ | Requires Flask app + DB |
| 5 | aria_memories only writable path | ❌ | Read-only page checks |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- `aria_mind/gateway.py` must have `create_app(testing=True)` factory
- All Flask templates must exist
- Database schema initialized

## Verification
```bash
# 1. Run dashboard verification:
TEST_DATABASE_URL=postgresql://aria:aria_test@localhost:5432/aria_test pytest tests/integration/test_dashboard_verification.py -v --timeout=60

# 2. Quick smoke test — just check pages return 200:
pytest tests/integration/test_dashboard_verification.py::TestDashboardPages::test_page_returns_200 -v

# 3. Check for untested routes:
pytest tests/integration/test_dashboard_verification.py::TestRouteCompleteness -v -s

# 4. Count total pages tested:
pytest tests/integration/test_dashboard_verification.py --collect-only | grep "test_page_returns_200"
# EXPECTED: ~25+ items collected
```

## Prompt for Agent
```
Create dashboard page verification tests for all 25+ Flask pages.

FILES TO READ FIRST:
- aria_mind/gateway.py (Flask app factory, route definitions)
- aria_mind/skills/skill_health_dashboard.py (dashboard pages)
- aria_mind/kernel/ (any dashboard blueprints)
- aria_mind/config/ (template configuration)

STEPS:
1. Create tests/integration/test_dashboard_verification.py
2. List all routes from gateway.py
3. Parametrize tests over every route
4. Check: HTTP 200, expected content, valid HTML, no template errors
5. Verify API endpoints return valid JSON
6. Check navigation links point to valid routes
7. Verify data pages show real data (not empty)

CONSTRAINTS:
- Use Flask test client (no real HTTP server needed)
- Parametrize over DASHBOARD_PAGES list for easy addition
- Check at least 25 pages
- Test completeness: flag any untested registered routes
```
