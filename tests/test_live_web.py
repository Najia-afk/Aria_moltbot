"""
TICKET-33 · Live Web Dashboard Tests
======================================
Integration tests for every page in aria-web (Flask, port 5000).

• Connects to a running aria-web instance (default: localhost:5000).
• Override with env var  ARIA_WEB_URL=http://<MAC_HOST>:5000
• All tests are marked @pytest.mark.integration and auto-skip when the
  web service is unreachable.

Covers 21 web routes (22 pages — "/" and "/dashboard" share the page).
"""

from __future__ import annotations

import os

import httpx
import pytest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEB_BASE = os.environ.get("ARIA_WEB_URL", "http://localhost:5000")

# ---------------------------------------------------------------------------
# Session-scoped client + reachability gate
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def web_url() -> str:
    return WEB_BASE.rstrip("/")


@pytest.fixture(scope="session")
def web_client(web_url: str) -> httpx.Client:
    """Return a shared httpx client; skip entire session if web is down."""
    client = httpx.Client(
        base_url=web_url,
        timeout=httpx.Timeout(10.0, connect=3.0),
        follow_redirects=True,
    )
    try:
        r = client.get("/")
        if r.status_code not in (200, 302):
            pytest.skip(f"aria-web returned {r.status_code} on / — skipping live web tests")
    except httpx.ConnectError:
        pytest.skip(f"aria-web not reachable at {web_url} — skipping live web tests")
    except Exception as exc:
        pytest.skip(f"aria-web health check failed: {exc}")
    yield client
    client.close()


# ============================================================================
# Helpers
# ============================================================================

def _assert_html(resp: httpx.Response):
    """Assert 200 and that the body looks like HTML."""
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code} for {resp.url}"
    ct = resp.headers.get("content-type", "")
    assert "text/html" in ct, f"Expected text/html, got {ct}"
    body = resp.text
    assert "<html" in body.lower() or "<!doctype" in body.lower(), "Response does not look like HTML"
    return body


# ============================================================================
#  Web page tests — one per route
# ============================================================================

WEB_ROUTES = [
    "/",
    "/dashboard",
    "/activities",
    "/thoughts",
    "/memories",
    "/records",
    "/search",
    "/services",
    "/models",
    "/wallets",
    "/goals",
    "/heartbeat",
    "/knowledge",
    "/social",
    "/performance",
    "/security",
    "/operations",
    "/sessions",
    "/model-usage",
    "/rate-limits",
    "/api-key-rotations",
]


@pytest.mark.integration
class TestWebPages:
    """Each route returns 200 + HTML."""

    @pytest.mark.parametrize("route", WEB_ROUTES, ids=[r.lstrip("/") or "index" for r in WEB_ROUTES])
    def test_page_renders(self, web_client: httpx.Client, route: str):
        resp = web_client.get(route)
        _assert_html(resp)
