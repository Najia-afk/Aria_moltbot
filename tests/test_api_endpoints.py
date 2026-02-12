import os

import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("ARIA_API_BASE", "http://localhost:8000")


def _alive() -> bool:
    try:
        return requests.get(f"{BASE_URL}/health", timeout=3).status_code == 200
    except requests.RequestException:
        return False


@pytest.mark.skipif(not _alive(), reason="API not reachable")
def test_health_endpoint():
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200


@pytest.mark.skipif(not _alive(), reason="API not reachable")
def test_core_read_endpoints():
    for path in ["/social", "/security-events", "/rate-limits"]:
        resp = requests.get(f"{BASE_URL}{path}", timeout=10)
        assert resp.status_code == 200


@pytest.mark.skipif(not _alive(), reason="API not reachable")
def test_graphql_endpoint():
    resp = requests.post(
        f"{BASE_URL}/graphql",
        json={"query": "{ __typename }"},
        timeout=10,
    )
    assert resp.status_code in (200, 400)
