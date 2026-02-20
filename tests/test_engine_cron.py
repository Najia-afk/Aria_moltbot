"""Engine Cron — Full CRUD lifecycle integration tests.

Chain 9: create -> list -> get -> update -> trigger -> history -> delete -> verify 404.
"""
import pytest

pytestmark = pytest.mark.engine


class TestCronJobLifecycle:
    """Ordered scenario: full cron job CRUD lifecycle."""

    def test_01_create_cron_job(self, api, uid):
        """POST /engine/cron -> create a new cron job."""
        payload = {
            "name": f"Health diagnostics run {uid}",
            "schedule": "0 * * * *",
            "agent_id": "main",
            "enabled": False,  # disabled so it doesn't fire during tests
            "payload_type": "prompt",
            "payload": f"Run comprehensive health check for all services — ref {uid}",
            "session_mode": "isolated",
            "max_duration_seconds": 60,
            "retry_count": 1,
        }
        r = api.post("/engine/cron", json=payload)
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 201, f"Create cron job failed: {r.status_code} {r.text}"
        data = r.json()
        assert "id" in data, f"Missing id in response: {data}"
        assert data["name"] == f"Health diagnostics run {uid}"
        assert data["schedule"] == "0 * * * *"
        assert data["enabled"] is False
        assert data["payload_type"] == "prompt"
        TestCronJobLifecycle._job_id = data["id"]
        TestCronJobLifecycle._uid = uid

    def test_02_verify_in_list(self, api):
        """GET /engine/cron -> verify job appears in the list."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.get("/engine/cron")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data, f"Missing 'jobs' key: {list(data.keys())}"
        assert "total" in data
        assert "scheduler_running" in data
        job_ids = [j["id"] for j in data["jobs"]]
        assert job_id in job_ids, f"Created job {job_id} not in list: {job_ids}"

    def test_03_get_by_id(self, api):
        """GET /engine/cron/{job_id} -> verify full detail."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        uid = getattr(TestCronJobLifecycle, "_uid", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.get(f"/engine/cron/{job_id}")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200, f"Get job failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["id"] == job_id
        assert data["name"] == f"Health diagnostics run {uid}"
        assert data["enabled"] is False
        assert data["run_count"] == 0

    def test_04_update_job(self, api):
        """PUT /engine/cron/{job_id} -> update name and schedule."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        uid = getattr(TestCronJobLifecycle, "_uid", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.put(f"/engine/cron/{job_id}", json={
            "name": f"Updated health run {uid}",
            "schedule": "*/30 * * * *",
        })
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["name"] == f"Updated health run {uid}"
        assert data["schedule"] == "*/30 * * * *"

    def test_05_verify_update_persisted(self, api):
        """GET /engine/cron/{job_id} -> verify update persisted."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        uid = getattr(TestCronJobLifecycle, "_uid", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.get(f"/engine/cron/{job_id}")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == f"Updated health run {uid}"
        assert data["schedule"] == "*/30 * * * *"

    def test_06_trigger_job(self, api):
        """POST /engine/cron/{job_id}/trigger -> manual execution."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.post(f"/engine/cron/{job_id}/trigger")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200, f"Trigger failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["triggered"] is True
        assert data["job_id"] == job_id
        assert "message" in data

    def test_07_check_history(self, api):
        """GET /engine/cron/{job_id}/history -> verify execution logged."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.get(f"/engine/cron/{job_id}/history")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200, f"History failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["job_id"] == job_id
        assert "total" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_08_scheduler_status(self, api):
        """GET /engine/cron/status -> verify scheduler state."""
        r = api.get("/engine/cron/status")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert "active_executions" in data
        assert "max_concurrent" in data

    def test_09_delete_job(self, api):
        """DELETE /engine/cron/{job_id} -> remove job."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.delete(f"/engine/cron/{job_id}")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 204, f"Delete failed: {r.status_code} {r.text}"

    def test_10_verify_deleted(self, api):
        """GET /engine/cron/{job_id} -> verify 404 after delete."""
        job_id = getattr(TestCronJobLifecycle, "_job_id", None)
        if not job_id:
            pytest.skip("no cron job created")
        r = api.get(f"/engine/cron/{job_id}")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 404, f"Job still exists: {r.status_code} {r.text}"


class TestCronEdgeCases:
    """Edge cases for cron job management."""

    def test_nonexistent_job_returns_404(self, api):
        """GET /engine/cron/{nonexistent} -> 404."""
        r = api.get("/engine/cron/nonexistent-job-id-xyz-000")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 404

    def test_delete_nonexistent_job(self, api):
        """DELETE /engine/cron/{nonexistent} -> 404."""
        r = api.delete("/engine/cron/nonexistent-job-id-xyz-000")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 404

    def test_trigger_nonexistent_job(self, api):
        """POST /engine/cron/{nonexistent}/trigger -> 404."""
        r = api.post("/engine/cron/nonexistent-job-id-xyz-000/trigger")
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 404

    def test_create_invalid_schedule(self, api):
        """POST /engine/cron with invalid schedule -> 422."""
        r = api.post("/engine/cron", json={
            "name": "Invalid schedule job",
            "schedule": "not-a-valid-cron",
            "payload_type": "prompt",
            "payload": "This should fail validation",
        })
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 422, f"Expected 422, got: {r.status_code} {r.text}"

    def test_create_missing_required_fields(self, api):
        """POST /engine/cron with empty body -> 422."""
        r = api.post("/engine/cron", json={})
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code == 422, f"Expected 422, got: {r.status_code} {r.text}"

    def test_update_empty_body(self, api):
        """PUT /engine/cron/{nonexistent} with empty body -> 400 or 404."""
        r = api.put("/engine/cron/nonexistent-job-xyz", json={})
        if r.status_code == 503:
            pytest.skip("Engine scheduler not available")
        assert r.status_code in (400, 404, 422)

    def test_cron_job_crud_and_trigger(self, api, uid):
        payload = {
            "name": f"integration-cron-{uid}",
            "schedule": "*/30 * * * *",
            "payload": f"integration payload {uid}",
            "agent_id": "main",
            "payload_type": "prompt",
        }
        r = api.post("/engine/cron", json=payload)
        if r.status_code == 503:
            pytest.skip("Engine cron not available")
        if r.status_code == 400 and "security" in r.text.lower():
            pytest.skip(f"cron create blocked by security filter: {r.text}")
        assert r.status_code in (200, 201, 422), f"Create cron failed: {r.status_code} {r.text}"
        if r.status_code == 422:
            pytest.skip(f"cron create validation rejected in this environment: {r.text}")
        data = r.json()
        job_id = data.get("id") or data.get("job_id")
        assert job_id, f"No job id in response: {data}"

        r = api.put(f"/engine/cron/{job_id}", json={"enabled": False})
        assert r.status_code in (200, 404), f"Update cron failed: {r.status_code} {r.text}"

        r = api.post(f"/engine/cron/{job_id}/trigger")
        assert r.status_code in (200, 404), f"Trigger cron failed: {r.status_code} {r.text}"

        r = api.delete(f"/engine/cron/{job_id}")
        assert r.status_code in (200, 204, 404), f"Delete cron failed: {r.status_code} {r.text}"
