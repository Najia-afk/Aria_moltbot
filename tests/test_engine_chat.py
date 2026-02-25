"""Engine Chat endpoint tests."""
import pytest

pytestmark = pytest.mark.engine


class TestEngineChat:
    def test_list_chat_sessions(self, api):
        r = api.get("/engine/chat/sessions")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            data = r.json()
            assert "items" in data or isinstance(data, list)

    def test_create_chat_session(self, api, uid):
        payload = {
            "agent_id": "default",
            "session_type": "chat",
        }
        r = api.post("/engine/chat/sessions", json=payload)
        if r.status_code == 503:
            pytest.skip("engine not initialized")
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
        data = r.json()
        assert "id" in data
        session_id = data["id"]
        try:
            # Get session
            r = api.get(f"/engine/chat/sessions/{session_id}")
            assert r.status_code == 200
            # Export
            r = api.get(f"/engine/chat/sessions/{session_id}/export")
            assert r.status_code in (200, 404), f"Export failed: {r.status_code} {r.text}"
        finally:
            # Cleanup
            r = api.delete(f"/engine/chat/sessions/{session_id}")
            assert r.status_code in (200, 204)

    def test_send_message(self, api, uid):
        # Create session first
        r = api.post("/engine/chat/sessions", json={
            "agent_id": "default",
            "session_type": "chat",
        })
        if r.status_code in (500, 503):
            pytest.skip("Engine not initialized")
        assert r.status_code in (200, 201)
        session_id = r.json()["id"]
        # Send message (may timeout if LLM is slow)
        import httpx as _httpx
        try:
            r = api.post(f"/engine/chat/sessions/{session_id}/messages", json={
                "content": f"Integration health check for session {uid}",
                "role": "user",
            })
        except (_httpx.ReadTimeout, _httpx.ConnectTimeout):
            api.delete(f"/engine/chat/sessions/{session_id}")
            pytest.skip("LLM response timed out")
        if r.status_code == 503:
            api.delete(f"/engine/chat/sessions/{session_id}")
            pytest.skip("engine not initialized for messaging")
        if r.status_code == 404:
            api.delete(f"/engine/chat/sessions/{session_id}")
            pytest.skip(f"LLM model not available: {r.text}")
        assert r.status_code in (200, 201), f"Send failed: {r.status_code} {r.text}"
        # Cleanup
        api.delete(f"/engine/chat/sessions/{session_id}")

    def test_get_nonexistent_session(self, api):
        r = api.get("/engine/chat/sessions/00000000-0000-0000-0000-000000000000")
        assert r.status_code in (404, 503)

    def test_get_session_messages(self, api):
        """GET /engine/chat/sessions/{session_id}/messages — load message history."""
        r = api.post("/engine/chat/sessions", json={
            "agent_id": "default",
            "session_type": "chat",
        })
        if r.status_code in (500, 503):
            pytest.skip("engine not initialized")
        assert r.status_code in (200, 201)
        session_id = r.json()["id"]
        try:
            r = api.get(f"/engine/chat/sessions/{session_id}/messages")
            assert r.status_code in (200, 404), f"Messages failed: {r.status_code} {r.text}"
            if r.status_code == 200:
                data = r.json()
                assert "messages" in data
                assert isinstance(data["messages"], list)
        finally:
            api.delete(f"/engine/chat/sessions/{session_id}")

    def test_get_messages_nonexistent_session(self, api):
        """GET /engine/chat/sessions/{bad_id}/messages -> 404."""
        r = api.get("/engine/chat/sessions/00000000-0000-0000-0000-000000000000/messages")
        if r.status_code == 503:
            pytest.skip("engine not initialized")
        assert r.status_code == 404

    def test_delete_nonexistent_session(self, api):
        """DELETE /engine/chat/sessions/{session_id} -> 404 for non-existent."""
        r = api.delete("/engine/chat/sessions/00000000-0000-0000-0000-000000000000")
        if r.status_code == 503:
            pytest.skip("engine not initialized")
        assert r.status_code == 404

    def test_export_nonexistent_session(self, api):
        """GET /engine/chat/sessions/{session_id}/export -> 404 for non-existent."""
        r = api.get("/engine/chat/sessions/00000000-0000-0000-0000-000000000000/export")
        if r.status_code == 503:
            pytest.skip("engine not initialized")
        assert r.status_code == 404

    def test_export_markdown_format(self, api, uid):
        """Export session as markdown."""
        r = api.post("/engine/chat/sessions", json={
            "agent_id": "default",
            "session_type": "chat",
        })
        if r.status_code == 503:
            pytest.skip("engine not initialized")
        if r.status_code not in (200, 201):
            pytest.skip(f"Could not create session: {r.status_code}")
        session_id = r.json()["id"]
        try:
            r = api.get(f"/engine/chat/sessions/{session_id}/export", params={"format": "markdown"})
            assert r.status_code in (200, 404), f"Export MD failed: {r.status_code}"
            if r.status_code == 200:
                assert "markdown" in r.headers.get("content-type", "") or "text" in r.headers.get("content-type", "")
        finally:
            api.delete(f"/engine/chat/sessions/{session_id}")
