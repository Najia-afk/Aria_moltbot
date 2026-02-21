"""Engine Sessions — Session management integration tests.

Tests: list with filters, stats, real session detail, messages with params, delete, end session.
"""
import pytest

pytestmark = pytest.mark.engine


class TestEngineSessions:
    """Read-only engine session endpoints."""

    def test_list_engine_sessions(self, api):
        """GET /engine/sessions → basic list."""
        r = api.get("/engine/sessions")
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data or isinstance(data, list)
        if "sessions" in data:
            assert "total" in data
            assert "has_more" in data

    def test_list_with_type_filter(self, api):
        """GET /engine/sessions?session_type=chat → filtered list."""
        r = api.get("/engine/sessions", params={"session_type": "chat", "limit": 5})
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 200

    def test_list_with_sort(self, api):
        """GET /engine/sessions?sort=created_at&order=asc → sorted list."""
        r = api.get("/engine/sessions", params={"sort": "created_at", "order": "asc", "limit": 5})
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 200

    def test_engine_sessions_stats(self, api):
        """GET /engine/sessions/stats → aggregate stats."""
        r = api.get("/engine/sessions/stats")
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 200
        data = r.json()
        assert "total_sessions" in data
        assert "total_messages" in data
        assert "active_agents" in data

    def test_get_real_session_detail(self, api):
        """GET /engine/sessions/{id} → real session with recent_messages."""
        r = api.get("/engine/sessions", params={"limit": 1})
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 200
        data = r.json()
        sessions = data.get("sessions", [])
        if not sessions:
            pytest.skip("No engine sessions available")
        sid = sessions[0].get("session_id", sessions[0].get("id"))
        r2 = api.get(f"/engine/sessions/{sid}")
        assert r2.status_code == 200
        detail = r2.json()
        assert "session_id" in detail or "id" in detail
        assert "recent_messages" in detail or "messages" in detail

    def test_get_session_messages_with_params(self, api):
        """GET /engine/sessions/{id}/messages?limit=5 → with pagination."""
        r = api.get("/engine/sessions", params={"limit": 1})
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        data = r.json()
        sessions = data.get("sessions", [])
        if not sessions:
            pytest.skip("No engine sessions available")
        sid = sessions[0].get("session_id", sessions[0].get("id"))
        r2 = api.get(f"/engine/sessions/{sid}/messages", params={"limit": 5, "offset": 0})
        assert r2.status_code == 200
        messages = r2.json()
        assert isinstance(messages, list)
        assert len(messages) <= 5

    def test_get_nonexistent_engine_session(self, api):
        """GET /engine/sessions/{nonexistent} → 404."""
        r = api.get("/engine/sessions/00000000-0000-0000-0000-000000000000")
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 404

    def test_end_nonexistent_session(self, api):
        """POST /engine/sessions/{nonexistent}/end → 404."""
        r = api.post("/engine/sessions/00000000-0000-0000-0000-000000000000/end")
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 404

    def test_delete_nonexistent_session(self, api):
        """DELETE /engine/sessions/{nonexistent} → 404."""
        r = api.delete("/engine/sessions/00000000-0000-0000-0000-000000000000")
        if r.status_code == 503:
            pytest.skip("Engine service unavailable")
        assert r.status_code == 404
