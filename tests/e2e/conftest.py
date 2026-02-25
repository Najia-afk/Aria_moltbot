"""
E2E test fixtures — ensure Docker services are up before testing (S-30).

Usage:
    pytest tests/e2e/ -v --timeout=120
"""
import os

import pytest
import requests


WEB_URL = os.environ.get("ARIA_WEB_URL", "http://localhost:5050")
API_URL = os.environ.get("ARIA_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session", autouse=True)
def ensure_services_running():
    """Skip the entire E2E suite if Aria services are unreachable."""
    max_retries = 15
    for i in range(max_retries):
        try:
            r = requests.get(f"{API_URL}/api/health", timeout=5)
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        import time
        time.sleep(2)
    pytest.skip(
        "Aria services not running — start with: docker compose up -d\n"
        f"  API:  {API_URL}\n"
        f"  Web:  {WEB_URL}"
    )


@pytest.fixture(scope="session")
def base_url():
    return WEB_URL


@pytest.fixture(scope="session")
def api_url():
    return API_URL
