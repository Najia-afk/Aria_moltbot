# S-30: Load Tests + End-to-End Tests
**Epic:** E17 — Testing | **Priority:** P2 | **Points:** 3 | **Phase:** 3

## Problem
The test suite has significant coverage gaps:

### 1. No load/stress tests
There are no tests for concurrent requests. This matters because:
- Chat endpoints use streaming (SSE/WebSocket) — untested under load
- LLM gateway has a circuit breaker — never tested at threshold
- In-memory rate limiter (`security_middleware.py` L91-142) — untested at scale
- PostgreSQL connection pool (10 connections by default) — untested at saturation

### 2. No end-to-end browser tests
The web UI has 42 routes and 46 templates, but no automated browser test validates:
- Login → chat → receive streaming response → check DB saved
- Navigation between pages
- WebSocket reconnection
- Chart rendering with real data

### 3. Integration/unit test directories are empty
```
tests/integration/__init__.py  # empty
tests/unit/__init__.py         # empty
```
84 test files exist but they're all at `tests/` root level or in `tests/api/`, `tests/engine/`, `tests/skills/`. The actual integration test directory has no tests.

### 4. No CI test pipeline
No GitHub Actions / CI config that runs tests on push or PR.

## Root Cause
Testing was done manually via Docker. No investment in automated test infrastructure beyond unit-level pytest tests.

## Fix

### Fix 1: Add Locust load tests
**File:** `tests/load/locustfile.py` (NEW)
```python
import os
from locust import HttpUser, task, between
import json

class AriaChatUser(HttpUser):
    wait_time = between(1, 3)
    host = os.environ.get("ARIA_API_URL", f"http://localhost:{os.environ.get('ARIA_API_PORT', '8000')}")

    def on_start(self):
        self.headers = {"Authorization": "Bearer test-api-key"}

    @task(3)
    def health_check(self):
        self.client.get("/api/health")

    @task(5)
    def list_thoughts(self):
        self.client.get("/api/thoughts?limit=20", headers=self.headers)

    @task(2)
    def chat_message(self):
        """Simulate a chat request (non-streaming for load test)."""
        self.client.post(
            "/api/engine/chat",
            json={"message": "Hello Aria", "stream": False},
            headers=self.headers,
            timeout=30,
        )

    @task(1)
    def graphql_query(self):
        self.client.post(
            "/graphql",
            json={"query": "{ thoughts(limit: 10) { id content } }"},
            headers=self.headers,
        )

    @task(1)
    def create_and_delete_thought(self):
        resp = self.client.post(
            "/api/thoughts",
            json={"content": f"load test thought", "category": "test"},
            headers=self.headers,
        )
        if resp.status_code == 200:
            thought_id = resp.json().get("id")
            if thought_id:
                self.client.delete(
                    f"/api/thoughts/{thought_id}",
                    headers=self.headers,
                )


class AriaWebUser(HttpUser):
    wait_time = between(2, 5)
    host = os.environ.get("ARIA_WEB_URL", f"http://localhost:{os.environ.get('ARIA_WEB_PORT', '5050')}")

    @task(3)
    def home_page(self):
        self.client.get("/")

    @task(2)
    def chat_page(self):
        self.client.get("/chat")

    @task(1)
    def engine_operations(self):
        self.client.get("/engine/operations")
```

### Fix 2: Add Playwright E2E tests
**File:** `tests/e2e/test_chat_flow.py` (NEW)
```python
import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("ARIA_WEB_URL", f"http://localhost:{os.environ.get('ARIA_WEB_PORT', '5050')}")

@pytest.fixture(scope="session")
def browser_context(browser):
    context = browser.new_context(base_url=BASE_URL)
    yield context
    context.close()

def test_home_page_loads(page: Page):
    page.goto("/")
    expect(page).to_have_title(re.compile("Aria"))
    expect(page.locator("nav")).to_be_visible()

def test_chat_send_message(page: Page):
    """Full flow: open chat, send message, receive streamed response."""
    page.goto("/chat")

    # Find message input and send button
    input_field = page.locator("textarea, input[type='text']").first
    input_field.fill("Hello Aria, this is an E2E test")
    page.locator("button:has-text('Send'), button[type='submit']").first.click()

    # Wait for response (streaming may take a few seconds)
    response_area = page.locator(".message, .response, .chat-message").last
    expect(response_area).to_be_visible(timeout=30000)

    # Response should contain text
    response_text = response_area.text_content()
    assert len(response_text) > 0, "Chat response was empty"

def test_navigation_all_pages(page: Page):
    """Verify all major nav links work without 500 errors."""
    page.goto("/")
    nav_links = page.locator("nav a[href]").all()

    visited = set()
    for link in nav_links:
        href = link.get_attribute("href")
        if href and href.startswith("/") and href not in visited:
            visited.add(href)
            response = page.goto(href)
            assert response.status < 500, f"{href} returned {response.status}"

def test_engine_operations_page(page: Page):
    page.goto("/engine/operations")
    expect(page.locator("h1, h2, .page-title").first).to_be_visible()
    # Check no JavaScript errors
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.wait_for_timeout(2000)
    assert len(errors) == 0, f"JS errors: {errors}"

def test_api_proxy_returns_data(page: Page):
    """Verify that web UI can reach API via proxy."""
    page.goto("/chat")
    # The page should make API calls via the proxy
    with page.expect_response(lambda r: "/api/" in r.url) as response_info:
        page.reload()
    response = response_info.value
    assert response.status == 200
```

### Fix 3: Add conftest and fixtures
**File:** `tests/e2e/conftest.py` (NEW)
```python
import os
import pytest
import subprocess
import time
import requests

@pytest.fixture(scope="session", autouse=True)
def ensure_services_running():
    """Verify Docker services are up before running E2E tests."""
    max_retries = 30
    api_url = os.environ.get("ARIA_API_URL", f"http://localhost:{os.environ.get('ARIA_API_PORT', '8000')}")
    for i in range(max_retries):
        try:
            r = requests.get(f"{api_url}/api/health", timeout=5)
            if r.status_code == 200:
                break
        except requests.ConnectionError:
            pass
        time.sleep(2)
    else:
        pytest.skip("Services not running — start with: docker compose up -d")
```

### Fix 4: Add load test runner script
**File:** `scripts/run-load-test.sh` (NEW)
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🔥 Running Aria Load Tests"
echo "=========================="
echo "Target: http://localhost:${ARIA_API_PORT:-8000} + http://localhost:${ARIA_WEB_PORT:-5050}"
echo "Users: ${USERS:-10}  Spawn rate: ${RATE:-2}/s  Duration: ${DURATION:-60s}"
echo ""

pip install locust --quiet

locust -f tests/load/locustfile.py \
  --headless \
  --users "${USERS:-10}" \
  --spawn-rate "${RATE:-2}" \
  --run-time "${DURATION:-60s}" \
  --html tests/load/report.html \
  --csv tests/load/results

echo ""
echo "✅ Report saved: tests/load/report.html"
```

### Fix 5: Add test dependencies to pyproject.toml
```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "httpx>=0.24",
    "locust>=2.20",
    "playwright>=1.40",
    "pytest-playwright>=0.4",
]
```

### Fix 6: Add basic CI config
**File:** `.github/workflows/test.yml` (NEW)
```yaml
name: Tests
on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/ -x --ignore=tests/e2e --ignore=tests/load -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: playwright install chromium
      - run: docker compose up -d
      - run: sleep 60  # Wait for services
      - run: pytest tests/e2e/ -v --timeout=120
      - run: docker compose down
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Tests only |
| 2 | .env for secrets | ✅ | Test .env needed |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | E2E tests against Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-28 (first-run) — E2E tests need Docker services running
- S-21 (health check) — load tests use /health endpoint
- S-29 (CRUD) — load tests exercise DELETE endpoint

## Verification
```bash
# 1. Load test runs:
pip install locust
locust -f tests/load/locustfile.py --headless --users 5 --spawn-rate 1 --run-time 10s
# EXPECTED: Stats summary, 0 failures for /api/health

# 2. E2E tests run:
pip install pytest-playwright
playwright install chromium
pytest tests/e2e/ -v --timeout=60
# EXPECTED: All tests pass (assuming Docker services up)

# 3. CI config valid:
cat .github/workflows/test.yml | python3 -c "import yaml,sys; yaml.safe_load(sys.stdin); print('valid')"
# EXPECTED: valid

# 4. Test deps installable:
pip install -e ".[test]"
# EXPECTED: No errors
```

## Prompt for Agent
```
Read these files FIRST:
- tests/ — list all files (understand existing test structure)
- pyproject.toml (full — see existing test config)
- docker-compose.yml (L1-50 — understand service names and ports)
- src/api/main.py (L1-50 — understand API structure)
- src/web/app.py (L1-50 — understand web routes)

CONSTRAINTS: #4 (Docker-first — E2E tests run against Docker services).

STEPS:
1. Create tests/load/locustfile.py with AriaChatUser and AriaWebUser classes
2. Create tests/load/__init__.py
3. Create tests/e2e/conftest.py with service-checking fixture
4. Create tests/e2e/test_chat_flow.py with 5 E2E scenarios
5. Create tests/e2e/__init__.py
6. Create scripts/run-load-test.sh (make executable)
7. Add [project.optional-dependencies] test section to pyproject.toml
8. Create .github/workflows/test.yml CI config
9. Run unit tests (pytest tests/ --ignore=tests/e2e --ignore=tests/load) to verify nothing broken
10. If Docker is running, execute the E2E tests
11. Run load test for 10 seconds to verify it works
12. Generate load test HTML report and verify it's readable
```
