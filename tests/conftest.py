"""
Aria Test Suite — Shared Fixtures

Auto-detects Docker vs local environment.
Integration tests hit the live API via synchronous httpx (no asyncio issues).
Unit / skill tests use the mock_api_client fixture (S-150).
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

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
    return "http://localhost:5050"


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

@pytest.fixture(scope="session")
def _check_api_health():
    """Skip test if API is not reachable (use as explicit fixture, not autouse)."""
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{API_BASE}/health")
            ok = r.status_code == 200
    except Exception:
        ok = False
    if not ok:
        pytest.skip(f"API not reachable at {API_BASE}", allow_module_level=True)


@pytest.fixture(scope="session")
def api_available() -> bool:
    """Check if API is reachable, return bool without skipping."""
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{API_BASE}/health")
            return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def _check_web_health():
    """Skip test if Web UI is not reachable (use as explicit fixture, not autouse)."""
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{WEB_BASE}/")
            ok = r.status_code == 200
    except Exception:
        ok = False
    if not ok:
        pytest.skip(f"Web UI not reachable at {WEB_BASE}", allow_module_level=True)


# ── Unique ID Helper ─────────────────────────────────────────────────────────

@pytest.fixture
def uid() -> str:
    return uuid.uuid4().hex[:8]


# ── Async Event Loop ─────────────────────────────────────────────────────────

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Mocked API Client (S-150) ────────────────────────────────────────────────

@pytest.fixture
def mock_api_client():
    """Mocked AriaAPIClient with all public methods returning sensible defaults.

    Every method is an ``AsyncMock`` so it can be awaited and inspected with
    the standard ``assert_called*`` helpers.  Override individual return values
    in your tests via::

        mock_api_client.create_goal.return_value = {"ok": True, "data": {"id": "custom"}}
    """
    client = AsyncMock()

    # -- Generic HTTP verbs --------------------------------------------------
    client.get = AsyncMock(return_value={"ok": True, "data": []})
    client.post = AsyncMock(return_value={"ok": True, "data": {}})
    client.patch = AsyncMock(return_value={"ok": True, "data": {}})
    client.put = AsyncMock(return_value={"ok": True, "data": {}})
    client.delete = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Activities ----------------------------------------------------------
    client.get_activities = AsyncMock(return_value={"ok": True, "data": []})
    client.create_activity = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.list_activities = AsyncMock(return_value={"ok": True, "data": []})

    # -- Security ------------------------------------------------------------
    client.get_security_events = AsyncMock(return_value={"ok": True, "data": []})
    client.create_security_event = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.get_security_stats = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Thoughts ------------------------------------------------------------
    client.get_thoughts = AsyncMock(return_value={"ok": True, "data": []})
    client.create_thought = AsyncMock(return_value={"ok": True, "data": {"id": 1}})

    # -- Memories (key-value) ------------------------------------------------
    client.get_memories = AsyncMock(return_value={"ok": True, "data": []})
    client.get_memory = AsyncMock(return_value={"ok": True, "data": {}})
    client.set_memory = AsyncMock(return_value={"ok": True, "data": {}})
    client.delete_memory = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Goals ---------------------------------------------------------------
    client.get_goals = AsyncMock(return_value={"ok": True, "data": []})
    client.create_goal = AsyncMock(return_value={"ok": True, "data": {"id": "test-goal-1"}})
    client.get_goal = AsyncMock(return_value={"ok": True, "data": {"id": "test-goal-1", "title": "Test"}})
    client.list_goals = AsyncMock(return_value={"ok": True, "data": []})
    client.update_goal = AsyncMock(return_value={"ok": True, "data": {}})
    client.delete_goal = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_goal_board = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_goal_archive = AsyncMock(return_value={"ok": True, "data": []})
    client.move_goal = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_sprint_summary = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_goal_history = AsyncMock(return_value={"ok": True, "data": []})

    # -- Hourly Goals --------------------------------------------------------
    client.get_hourly_goals = AsyncMock(return_value={"ok": True, "data": []})
    client.create_hourly_goal = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.update_hourly_goal = AsyncMock(return_value={"ok": True, "data": {}})
    client.set_hourly_goal = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.complete_hourly_goal = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Knowledge Graph -----------------------------------------------------
    client.get_knowledge_graph = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_entities = AsyncMock(return_value={"ok": True, "data": []})
    client.create_entity = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.create_relation = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.graph_traverse = AsyncMock(return_value={"ok": True, "data": {"entities": []}})
    client.graph_search = AsyncMock(return_value={"ok": True, "data": {"results": []}})
    client.kg_traverse = AsyncMock(return_value={"ok": True, "data": {"entities": []}})
    client.kg_search = AsyncMock(return_value={"ok": True, "data": {"results": []}})
    client.kg_add_entity = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.kg_add_relation = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.kg_query = AsyncMock(return_value={"ok": True, "data": {"entities": []}})
    client.kg_get_entity = AsyncMock(return_value={"ok": True, "data": {}})
    client.find_skill_for_task = AsyncMock(return_value={"ok": True, "data": []})
    client.delete_auto_generated_graph = AsyncMock(return_value={"ok": True, "data": {}})
    client.sync_skill_graph = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_query_log = AsyncMock(return_value={"ok": True, "data": []})

    # -- Social --------------------------------------------------------------
    client.get_social_posts = AsyncMock(return_value={"ok": True, "data": []})
    client.create_social_post = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.update_social_post = AsyncMock(return_value={"ok": True, "data": {}})
    client.delete_social_post = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Heartbeats ----------------------------------------------------------
    client.get_heartbeats = AsyncMock(return_value={"ok": True, "data": []})
    client.get_latest_heartbeat = AsyncMock(return_value={"ok": True, "data": {}})
    client.create_heartbeat = AsyncMock(return_value={"ok": True, "data": {"id": 1}})

    # -- Performance ---------------------------------------------------------
    client.get_performance_logs = AsyncMock(return_value={"ok": True, "data": []})
    client.create_performance_log = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.log_agent_performance = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_agent_performance = AsyncMock(return_value={"ok": True, "data": []})
    client.log_review = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.get_reviews = AsyncMock(return_value={"ok": True, "data": []})

    # -- Tasks ---------------------------------------------------------------
    client.get_tasks = AsyncMock(return_value={"ok": True, "data": []})
    client.create_task = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.update_task = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Schedule / Jobs -----------------------------------------------------
    client.get_schedule = AsyncMock(return_value={"ok": True, "data": []})
    client.trigger_schedule_tick = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_jobs = AsyncMock(return_value={"ok": True, "data": []})
    client.sync_jobs = AsyncMock(return_value={"ok": True, "data": {}})
    client.create_job = AsyncMock(return_value={"ok": True, "data": {"id": "job-1"}})
    client.get_job = AsyncMock(return_value={"ok": True, "data": {"id": "job-1"}})
    client.list_jobs = AsyncMock(return_value={"ok": True, "data": []})
    client.update_job = AsyncMock(return_value={"ok": True, "data": {}})
    client.delete_job = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Sessions ------------------------------------------------------------
    client.get_sessions = AsyncMock(return_value={"ok": True, "data": []})
    client.create_session = AsyncMock(return_value={"ok": True, "data": {"session_id": "test-session"}})
    client.update_session = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_session_stats = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Model Usage ---------------------------------------------------------
    client.get_model_usage = AsyncMock(return_value={"ok": True, "data": []})
    client.create_model_usage = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.get_model_usage_stats = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_litellm_models = AsyncMock(return_value={"ok": True, "data": []})
    client.get_litellm_health = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_litellm_spend = AsyncMock(return_value={"ok": True, "data": []})
    client.get_provider_balances = AsyncMock(return_value={"ok": True, "data": []})

    # -- Memory (semantic / working) -----------------------------------------
    client.remember = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.recall = AsyncMock(return_value={"ok": True, "data": {"items": []}})
    client.get_working_memory_context = AsyncMock(return_value={"ok": True, "data": []})
    client.working_memory_checkpoint = AsyncMock(return_value={"ok": True, "data": {}})
    client.restore_working_memory_checkpoint = AsyncMock(return_value={"ok": True, "data": {}})
    client.forget_working_memory = AsyncMock(return_value={"ok": True, "data": {}})
    client.update_working_memory = AsyncMock(return_value={"ok": True, "data": {}})
    client.checkpoint = AsyncMock(return_value={"ok": True, "data": {}})
    client.forget = AsyncMock(return_value={"ok": True, "data": {}})
    client.store_memory_semantic = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.store_sentiment_event = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.search_memories_semantic = AsyncMock(return_value={"ok": True, "data": []})
    client.list_semantic_memories = AsyncMock(return_value={"ok": True, "data": []})
    client.summarize_session = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Lessons Learned ----------------------------------------------------
    client.record_lesson = AsyncMock(return_value={"ok": True, "data": {"id": 1}})
    client.check_known_errors = AsyncMock(return_value={"ok": True, "data": []})
    client.get_lessons = AsyncMock(return_value={"ok": True, "data": []})

    # -- Proposals -----------------------------------------------------------
    client.propose_improvement = AsyncMock(return_value={"ok": True, "data": {"id": "prop-1"}})
    client.get_proposals = AsyncMock(return_value={"ok": True, "data": []})
    client.get_proposal = AsyncMock(return_value={"ok": True, "data": {}})
    client.review_proposal = AsyncMock(return_value={"ok": True, "data": {}})
    client.mark_proposal_implemented = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Skill Invocations ---------------------------------------------------
    client.record_invocation = AsyncMock(return_value={"ok": True, "data": {}})
    client.get_skill_stats = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Artifacts -----------------------------------------------------------
    client.write_artifact = AsyncMock(return_value={"ok": True, "data": {}})
    client.read_artifact = AsyncMock(return_value={"ok": True, "data": {}})
    client.list_artifacts = AsyncMock(return_value={"ok": True, "data": []})
    client.delete_artifact = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Agents --------------------------------------------------------------
    client.list_agents = AsyncMock(return_value={"ok": True, "data": []})
    client.get_agent = AsyncMock(return_value={"ok": True, "data": {}})
    client.spawn_agent = AsyncMock(return_value={"ok": True, "data": {"session_id": "test-session"}})
    client.terminate_agent = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Sprint convenience --------------------------------------------------
    client.sprint_status = AsyncMock(return_value={"ok": True, "data": {}})
    client.sprint_plan = AsyncMock(return_value={"ok": True, "data": {}})
    client.update_sprint = AsyncMock(return_value={"ok": True, "data": {}})

    # -- Pagination helper ---------------------------------------------------
    client.get_all_pages = AsyncMock(return_value={"ok": True, "data": []})

    # -- Lifecycle -----------------------------------------------------------
    client.initialize = AsyncMock(return_value=True)
    client.health_check = AsyncMock(return_value="available")
    client.close = AsyncMock(return_value=None)

    # -- Low-level _client for skills that access it directly ----------------
    client._client = AsyncMock()
    client._client.get = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"data": []})
    )
    client._client.post = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"data": {}})
    )
    client._client.patch = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"data": {}})
    )
    client._client.put = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"data": {}})
    )
    client._client.delete = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"data": {}})
    )

    return client


@pytest.fixture
def mock_skill_context():
    """Standard context dict for skill initialization."""
    return {
        "session_id": "test-session-001",
        "user_id": "test-user",
        "agent_name": "test-agent",
        "workspace": "/tmp/test-workspace",
        "model": "gpt-4",
    }


# ── Helper Functions ──────────────────────────────────────────────────────────

def assert_api_called(mock_client, method: str, path: str | None = None):
    """Assert that an API method was called, optionally with a specific path."""
    method_mock = getattr(mock_client, method)
    assert method_mock.called, f"Expected {method} to be called"
    if path:
        args = method_mock.call_args
        assert path in str(args), f"Expected path {path} in call args {args}"


def assert_skill_result_ok(result):
    """Assert that a skill result indicates success.

    Handles both ``SkillResult`` objects and plain dicts.
    """
    if isinstance(result, dict):
        assert result.get("ok", result.get("success", True)) is True
    elif hasattr(result, "success"):
        assert result.success is True
    elif hasattr(result, "ok"):
        assert result.ok is True
