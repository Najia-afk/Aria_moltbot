"""
Aria Test Suite — Shared Fixtures

Auto-detects Docker vs local environment.
All tests hit the live API via synchronous httpx (no asyncio issues).
No mocks, no SQLAlchemy imports.
"""
import os
import time
import uuid

import httpx
import pytest

# ── Environment Detection ─────────────────────────────────────────────────────

def _detect_api_base() -> str:
    if url := os.getenv("ARIA_TEST_API_URL"):
        return url.rstrip("/")
    if os.path.exists("/.dockerenv"):
        return "http://aria-api:8000"
    return "http://localhost:8000"


def _detect_web_base() -> str:
    if url := os.getenv("ARIA_TEST_WEB_URL"):
        return url.rstrip("/")
    if os.path.exists("/.dockerenv"):
        return "http://aria-web:5000"
    return "http://localhost:5000"


API_BASE = _detect_api_base()
WEB_BASE = _detect_web_base()


# ── Pytest Configuration ──────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "web: tests that require the web UI")
    config.addinivalue_line("markers", "engine: tests that require the engine")
    config.addinivalue_line("markers", "slow: slow tests")
    config.addinivalue_line("markers", "websocket: WebSocket tests")
    config.addinivalue_line("markers", "graphql: GraphQL tests")


# ── HTTP Clients (synchronous) ────────────────────────────────────────────────

class _RetryTransport(httpx.HTTPTransport):
    """Transparent retry on 429 (rate-limit) with back-off.

    The server blocks for 15s on burst and 30s on RPM exceed,
    so we need retries that span at least 30s total.
    """

    MAX_RETRIES = 4
    BACKOFF = (2.0, 5.0, 10.0, 20.0)

    def handle_request(self, request):
        for attempt in range(self.MAX_RETRIES + 1):
            response = super().handle_request(request)
            if response.status_code != 429 or attempt == self.MAX_RETRIES:
                return response
            wait = self.BACKOFF[attempt] if attempt < len(self.BACKOFF) else 20.0
            time.sleep(wait)
        return response  # pragma: no cover


@pytest.fixture(scope="session")
def api():
    """Session-scoped synchronous HTTP client for the API."""
    with httpx.Client(
        base_url=API_BASE,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
        transport=_RetryTransport(),
    ) as client:
        yield client


@pytest.fixture(scope="session")
def web():
    """Session-scoped synchronous HTTP client for the Web UI."""
    with httpx.Client(
        base_url=WEB_BASE,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
        transport=_RetryTransport(),
    ) as client:
        yield client


# ── Health Gate ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _check_api_health():
    """Skip entire session if API is not reachable."""
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{API_BASE}/health")
            ok = r.status_code == 200
    except Exception:
        ok = False
    if not ok:
        pytest.skip(f"API not reachable at {API_BASE}", allow_module_level=True)


# ── Unique ID Helper ─────────────────────────────────────────────────────────

@pytest.fixture
def uid() -> str:
    return uuid.uuid4().hex[:8]
