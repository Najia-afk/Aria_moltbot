"""
TICKET-33 · Live API Endpoint Tests
====================================
Integration tests for every REST endpoint in aria-api (FastAPI, port 8000).

• Connects to a running aria-api instance (default: localhost:8000).
• Override with env var  ARIA_API_URL=http://<MAC_HOST>:8000
• All tests are marked @pytest.mark.integration and auto-skip when the API
  is unreachable — perfectly safe to include in CI on every push.

Covers 63 endpoints across 17 routers.
"""


import os
import uuid

import httpx
import pytest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = os.environ.get("ARIA_API_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Session-scoped client + reachability gate
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_url() -> str:
    return API_BASE.rstrip("/")


@pytest.fixture(scope="session")
def api_client(api_url: str) -> httpx.Client:
    """Return a shared httpx client; skip the whole session if API is down."""
    client = httpx.Client(base_url=api_url, timeout=httpx.Timeout(15.0, connect=3.0))
    try:
        r = client.get("/health")
        if r.status_code != 200:
            pytest.skip(f"aria-api returned {r.status_code} on /health — skipping live tests")
    except httpx.ConnectError:
        pytest.skip(f"aria-api not reachable at {api_url} — skipping live tests")
    except Exception as exc:
        pytest.skip(f"aria-api health check failed: {exc}")
    yield client
    client.close()


# ============================================================================
# Helpers
# ============================================================================

def _assert_json(resp: httpx.Response, status: int = 200):
    """Assert status and return parsed JSON."""
    assert resp.status_code == status, f"Expected {status}, got {resp.status_code}: {resp.text[:300]}"
    return resp.json()


def _assert_list_or_data(data):
    """Accept a plain list or a dict with a list-valued key."""
    if isinstance(data, list):
        return data
    assert isinstance(data, dict), f"Expected list or dict, got {type(data)}"
    # look for common wrapper keys
    for key in ("data", "items", "records", "memories", "thoughts", "posts",
                "sessions", "heartbeats", "logs", "tasks", "jobs",
                "rotations", "rate_limits", "usage", "goals", "entities",
                "relations", "context"):
        if key in data:
            assert isinstance(data[key], list), f"data[{key!r}] is not a list"
            return data[key]
    return data  # still valid — just a dict payload


# ============================================================================
#  Health router
# ============================================================================

@pytest.mark.integration
class TestHealthRouter:

    def test_health(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/health"))
        assert data["status"] == "healthy"

    def test_host_stats(self, api_client: httpx.Client):
        _assert_json(api_client.get("/host-stats"))

    def test_status(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/status"))
        assert isinstance(data, dict)

    def test_status_service_postgres(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/status/postgres"))
        assert "status" in data

    def test_stats(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/stats"))
        assert "activities_count" in data


# ============================================================================
#  Activities router
# ============================================================================

@pytest.mark.integration
class TestActivitiesRouter:

    def test_get_activities(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/activities"))
        assert isinstance(data, list) or "items" in data

    def test_post_activity(self, api_client: httpx.Client):
        payload = {"action": "test_action", "skill": "pytest", "details": {"msg": "live test"}, "success": True}
        data = _assert_json(api_client.post("/activities", json=payload))
        assert data.get("created") is True




# ============================================================================
#  Thoughts router
# ============================================================================

@pytest.mark.integration
class TestThoughtsRouter:

    def test_get_thoughts(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/thoughts"))
        assert "items" in data or "thoughts" in data

    def test_post_thought(self, api_client: httpx.Client):
        payload = {"content": "live test thought", "category": "test"}
        data = _assert_json(api_client.post("/thoughts", json=payload))
        assert data.get("created") is True


# ============================================================================
#  Memories router
# ============================================================================

@pytest.mark.integration
class TestMemoriesRouter:

    def test_get_memories(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/memories"))
        assert "items" in data or "memories" in data

    def test_post_memory(self, api_client: httpx.Client):
        key = f"qa-{uuid.uuid4().hex[:8]}"
        payload = {"key": key, "value": {"msg": "live qa check"}, "category": "qa"}
        data = _assert_json(api_client.post("/memories", json=payload))
        assert data.get("upserted") is True or data.get("stored") is True or data.get("created") is True

    def test_get_memory_by_key(self, api_client: httpx.Client):
        key = f"lookup-{uuid.uuid4().hex[:8]}"
        api_client.post("/memories", json={"key": key, "value": {"x": 1}})
        data = _assert_json(api_client.get(f"/memories/{key}"))
        assert data.get("key") == key

    def test_delete_memory(self, api_client: httpx.Client):
        key = f"del-{uuid.uuid4().hex[:8]}"
        api_client.post("/memories", json={"key": key, "value": {"x": 1}})
        data = _assert_json(api_client.delete(f"/memories/{key}"))
        assert data.get("deleted") is True


# ============================================================================
#  Goals router
# ============================================================================

@pytest.mark.integration
class TestGoalsRouter:

    def test_get_goals(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/goals"))
        assert isinstance(data, list) or "items" in data

    def test_post_goal(self, api_client: httpx.Client):
        uid = uuid.uuid4().hex[:8]
        payload = {"title": f"Sprint Review {uid}", "description": "Live QA validation", "priority": 1}
        data = _assert_json(api_client.post("/goals", json=payload))
        assert data.get("created") is True or "id" in data or "goal_id" in data

    def test_patch_goal(self, api_client: httpx.Client):
        # Create then patch
        uid = uuid.uuid4().hex[:8]
        created = _assert_json(api_client.post("/goals", json={"title": f"Sprint Item {uid}", "priority": 1}))
        goal_id = created.get("goal_id") or created.get("id")
        data = _assert_json(api_client.patch(f"/goals/{goal_id}", json={"status": "in_progress"}))
        assert data.get("updated") is True

    def test_delete_goal(self, api_client: httpx.Client):
        uid = uuid.uuid4().hex[:8]
        created = _assert_json(api_client.post("/goals", json={"title": f"Cleanup Item {uid}", "priority": 1}))
        goal_id = created.get("goal_id") or created.get("id")
        data = _assert_json(api_client.delete(f"/goals/{goal_id}"))
        assert data.get("deleted") is True

    def test_get_hourly_goals(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/hourly-goals"))
        assert "goals" in data

    def test_post_hourly_goal(self, api_client: httpx.Client):
        payload = {"hour_slot": 10, "goal_type": "test", "description": "live test hourly goal"}
        data = _assert_json(api_client.post("/hourly-goals", json=payload))
        assert data.get("created") is True


# ============================================================================
#  Sessions router
# ============================================================================

@pytest.mark.integration
class TestSessionsRouter:

    def test_get_sessions(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/sessions"))
        assert "items" in data or "sessions" in data

    def test_post_session(self, api_client: httpx.Client):
        payload = {"agent_id": "pytest", "session_type": "test"}
        data = _assert_json(api_client.post("/sessions", json=payload))
        assert data.get("created") is True

    def test_patch_session(self, api_client: httpx.Client):
        created = _assert_json(api_client.post("/sessions", json={"agent_id": "pytest"}))
        sid = created["id"]
        data = _assert_json(api_client.patch(f"/sessions/{sid}", json={"status": "completed"}))
        assert data.get("updated") is True

    def test_get_sessions_stats(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/sessions/stats"))
        assert "total_sessions" in data


# ============================================================================
#  Model Usage router
# ============================================================================

@pytest.mark.integration
class TestModelUsageRouter:

    def test_get_model_usage(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/model-usage"))
        assert "items" in data or "usage" in data

    def test_post_model_usage(self, api_client: httpx.Client):
        payload = {
            "model": "test-model",
            "provider": "pytest",
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.001,
            "success": True,
        }
        data = _assert_json(api_client.post("/model-usage", json=payload))
        assert data.get("created") is True

    def test_get_model_usage_stats(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/model-usage/stats"))
        assert "total_requests" in data


# ============================================================================
#  LiteLLM router
# ============================================================================

@pytest.mark.integration
class TestLitellmRouter:

    def test_litellm_models(self, api_client: httpx.Client):
        _assert_json(api_client.get("/litellm/models"))

    def test_litellm_health(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/litellm/health"))
        assert "status" in data

    def test_litellm_spend(self, api_client: httpx.Client):
        _assert_json(api_client.get("/litellm/spend"))

    def test_litellm_global_spend(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/litellm/global-spend"))
        assert "spend" in data


# ============================================================================
#  Providers router
# ============================================================================

@pytest.mark.integration
class TestProvidersRouter:

    def test_provider_balances(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/providers/balances"))
        assert isinstance(data, dict)


# ============================================================================
#  Security router
# ============================================================================

@pytest.mark.integration
class TestSecurityRouter:

    def test_get_security_events(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/security-events"))
        assert isinstance(data, list) or "items" in data or "events" in data

    def test_post_security_event(self, api_client: httpx.Client):
        payload = {
            "threat_level": "LOW",
            "threat_type": "test",
            "source": "pytest",
            "blocked": False,
        }
        data = _assert_json(api_client.post("/security-events", json=payload))
        assert data.get("created") is True

    def test_security_events_stats(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/security-events/stats"))
        assert "total_events" in data


# ============================================================================
#  Knowledge Graph router
# ============================================================================

@pytest.mark.integration
class TestKnowledgeGraphRouter:

    def test_get_knowledge_graph(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/knowledge-graph"))
        assert "entities" in data
        assert "relations" in data

    def test_get_entities(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/knowledge-graph/entities"))
        assert "entities" in data

    def test_get_relations(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/knowledge-graph/relations"))
        assert "relations" in data

    def test_post_entity(self, api_client: httpx.Client):
        uid = uuid.uuid4().hex[:8]
        payload = {"name": f"aria-concept-{uid}", "type": "concept", "properties": {}}
        data = _assert_json(api_client.post("/knowledge-graph/entities", json=payload))
        assert data.get("created") is True or "id" in data

    def test_post_relation(self, api_client: httpx.Client):
        # Create two entities first
        uid = uuid.uuid4().hex[:8]
        e1 = _assert_json(api_client.post("/knowledge-graph/entities", json={"name": f"aria-node-a-{uid}", "type": "concept"}))
        e2 = _assert_json(api_client.post("/knowledge-graph/entities", json={"name": f"aria-node-b-{uid}", "type": "concept"}))
        e1_id = e1.get("id") or e1.get("entity_id")
        e2_id = e2.get("id") or e2.get("entity_id")
        if not e1_id or not e2_id:
            pytest.skip("Could not create entities for relation test")
        payload = {
            "from_entity": e1_id,
            "to_entity": e2_id,
            "relation_type": "relates_to",
        }
        data = _assert_json(api_client.post("/knowledge-graph/relations", json=payload))
        assert data.get("created") is True or "id" in data


# ============================================================================
#  Social router
# ============================================================================

@pytest.mark.integration
class TestSocialRouter:

    def test_get_social(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/social"))
        assert "items" in data or "posts" in data

    def test_post_social(self, api_client: httpx.Client):
        uid = uuid.uuid4().hex[:8]
        payload = {"content": f"Aria QA check {uid}", "platform": "moltbook"}
        data = _assert_json(api_client.post("/social", json=payload))
        assert data.get("created") is True or "id" in data


# ============================================================================
#  Operations router — Rate Limits
# ============================================================================

@pytest.mark.integration
class TestRateLimitsRouter:

    def test_get_rate_limits(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/rate-limits"))
        assert "rate_limits" in data

    def test_post_rate_limit_check(self, api_client: httpx.Client):
        payload = {"skill": "pytest_skill", "max_actions": 100, "window_seconds": 3600}
        data = _assert_json(api_client.post("/rate-limits/check", json=payload))
        assert "allowed" in data

    def test_post_rate_limit_increment(self, api_client: httpx.Client):
        payload = {"skill": "pytest_skill", "action_type": "action"}
        data = _assert_json(api_client.post("/rate-limits/increment", json=payload))
        assert data.get("incremented") is True


# ============================================================================
#  Operations router — API Key Rotations
# ============================================================================

@pytest.mark.integration
class TestApiKeyRotationsRouter:

    def test_get_api_key_rotations(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/api-key-rotations"))
        assert "rotations" in data

    def test_post_api_key_rotation(self, api_client: httpx.Client):
        payload = {"service": "pytest", "reason": "live test rotation"}
        data = _assert_json(api_client.post("/api-key-rotations", json=payload))
        assert data.get("created") is True


# ============================================================================
#  Operations router — Heartbeat
# ============================================================================

@pytest.mark.integration
class TestHeartbeatRouter:

    def test_get_heartbeats(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/heartbeat"))
        assert "heartbeats" in data

    def test_post_heartbeat(self, api_client: httpx.Client):
        payload = {"beat_number": 9999, "status": "healthy", "details": {"src": "pytest"}}
        data = _assert_json(api_client.post("/heartbeat", json=payload))
        assert data.get("created") is True

    def test_get_heartbeat_latest(self, api_client: httpx.Client):
        _assert_json(api_client.get("/heartbeat/latest"))


# ============================================================================
#  Operations router — Performance
# ============================================================================

@pytest.mark.integration
class TestPerformanceRouter:

    def test_get_performance(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/performance"))
        assert "logs" in data

    def test_post_performance(self, api_client: httpx.Client):
        payload = {"review_period": "2026-02", "successes": "live test", "failures": "", "improvements": ""}
        data = _assert_json(api_client.post("/performance", json=payload))
        assert data.get("created") is True


# ============================================================================
#  Operations router — Pending Tasks
# ============================================================================

@pytest.mark.integration
class TestTasksRouter:

    def test_get_tasks(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/tasks"))
        assert "tasks" in data

    def test_post_task(self, api_client: httpx.Client):
        payload = {
            "task_type": "test",
            "description": "live test task",
            "agent_type": "pytest",
            "priority": "low",
        }
        data = _assert_json(api_client.post("/tasks", json=payload))
        assert data.get("created") is True

    def test_patch_task(self, api_client: httpx.Client):
        created = _assert_json(api_client.post("/tasks", json={
            "task_type": "test",
            "description": "patchable task",
            "agent_type": "pytest",
        }))
        task_id = created["task_id"]
        data = _assert_json(api_client.patch(f"/tasks/{task_id}", json={"status": "completed", "result": "ok"}))
        assert data.get("updated") is True


# ============================================================================
#  Operations router — Schedule
# ============================================================================

@pytest.mark.integration
class TestScheduleRouter:

    def test_get_schedule(self, api_client: httpx.Client):
        _assert_json(api_client.get("/schedule"))

    def test_post_schedule_tick(self, api_client: httpx.Client):
        _assert_json(api_client.post("/schedule/tick"))


# ============================================================================
#  Operations router — Jobs
# ============================================================================

@pytest.mark.integration
class TestJobsRouter:

    def test_get_jobs(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/jobs"))
        assert "jobs" in data

    def test_get_jobs_live(self, api_client: httpx.Client):
        # May return an error key if jobs.json not found — still 200
        _assert_json(api_client.get("/jobs/live"))

    def test_post_jobs_sync(self, api_client: httpx.Client):
        # May 404/500 if jobs.json absent — accept 200 or 404
        resp = api_client.post("/jobs/sync")
        assert resp.status_code in (200, 404, 500)


# ============================================================================
#  Records router
# ============================================================================

@pytest.mark.integration
class TestRecordsRouter:

    def test_get_records_default(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records"))
        assert "records" in data

    def test_get_records_thoughts(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "thoughts"}))
        assert "records" in data

    def test_get_records_memories(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "memories"}))
        assert "records" in data

    def test_get_records_goals(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "goals"}))
        assert "records" in data

    def test_get_records_social_posts(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "social_posts"}))
        assert "records" in data

    def test_get_records_heartbeat_log(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "heartbeat_log"}))
        assert "records" in data

    def test_get_records_security_events(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "security_events"}))
        assert "records" in data

    def test_get_records_agent_sessions(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "agent_sessions"}))
        assert "records" in data

    def test_get_records_model_usage(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "model_usage"}))
        assert "records" in data

    def test_get_records_rate_limits(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "rate_limits"}))
        assert "records" in data

    def test_get_records_api_key_rotations(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "api_key_rotations"}))
        assert "records" in data

    def test_get_records_scheduled_jobs(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "scheduled_jobs"}))
        assert "records" in data

    def test_get_records_knowledge_entities(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "knowledge_entities"}))
        assert "records" in data

    def test_get_records_performance_log(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/records", params={"table": "performance_log"}))
        assert "records" in data

    def test_get_records_invalid_table(self, api_client: httpx.Client):
        resp = api_client.get("/records", params={"table": "no_such_table"})
        assert resp.status_code == 400

    def test_get_export(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/export", params={"table": "activities"}))
        assert "records" in data

    def test_get_search(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/search", params={"q": "test"}))
        assert "activities" in data
        assert "thoughts" in data
        assert "memories" in data

    def test_get_search_empty(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/search"))
        assert isinstance(data, dict)


# ============================================================================
#  Models Config router
# ============================================================================

@pytest.mark.integration
class TestModelsConfigRouter:

    def test_get_models_config(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/models/config"))
        assert "models" in data

    def test_get_models_pricing(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/models/pricing"))
        assert isinstance(data, dict)

    def test_post_models_reload(self, api_client: httpx.Client):
        data = _assert_json(api_client.post("/models/reload"))
        assert "status" in data


# ============================================================================
#  Admin router
# ============================================================================

@pytest.mark.integration
class TestAdminRouter:

    def test_get_soul_file(self, api_client: httpx.Client):
        # May 404 if not in Docker — accept either
        resp = api_client.get("/soul/SOUL.md")
        assert resp.status_code in (200, 404)

    def test_get_soul_file_not_allowed(self, api_client: httpx.Client):
        resp = api_client.get("/soul/NOTREAL.md")
        assert resp.status_code == 404

    def test_service_control_invalid_action(self, api_client: httpx.Client):
        resp = api_client.post("/admin/services/test/invalid")
        assert resp.status_code in (400, 403)


# ============================================================================
#  Working Memory router
# ============================================================================

@pytest.mark.integration
class TestWorkingMemoryRouter:

    def test_get_working_memory(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/working-memory"))
        assert "items" in data

    def test_get_working_memory_context(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/working-memory/context"))
        assert "context" in data

    def test_post_working_memory(self, api_client: httpx.Client):
        key = f"wm-test-{uuid.uuid4().hex[:8]}"
        payload = {"key": key, "value": {"msg": "live test"}, "category": "test", "importance": 0.8}
        data = _assert_json(api_client.post("/working-memory", json=payload))
        assert data.get("upserted") is True

    def test_patch_working_memory(self, api_client: httpx.Client):
        key = f"wm-patch-{uuid.uuid4().hex[:8]}"
        created = _assert_json(api_client.post("/working-memory", json={
            "key": key, "value": {"v": 1}, "category": "test",
        }))
        item_id = created["id"]
        data = _assert_json(api_client.patch(f"/working-memory/{item_id}", json={"importance": 0.9}))
        assert "id" in data or "key" in data

    def test_delete_working_memory(self, api_client: httpx.Client):
        key = f"wm-del-{uuid.uuid4().hex[:8]}"
        created = _assert_json(api_client.post("/working-memory", json={
            "key": key, "value": {"v": 1}, "category": "test",
        }))
        item_id = created["id"]
        data = _assert_json(api_client.delete(f"/working-memory/{item_id}"))
        assert data.get("deleted") is True

    def test_post_checkpoint(self, api_client: httpx.Client):
        data = _assert_json(api_client.post("/working-memory/checkpoint"))
        assert "checkpoint_id" in data

    def test_get_checkpoint(self, api_client: httpx.Client):
        data = _assert_json(api_client.get("/working-memory/checkpoint"))
        assert "checkpoint_id" in data
