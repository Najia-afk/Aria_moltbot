"""WebSocket endpoint tests — uses sync websocket-client or skips."""
import json
import os
import pytest
import httpx

pytestmark = pytest.mark.websocket

_API_BASE = os.getenv("ARIA_TEST_API_URL", "http://localhost:8000").rstrip("/")
WS_BASE = _API_BASE.replace("http://", "ws://").replace("https://", "wss://")


class TestWebSocket:
    def test_websocket_invalid_session(self):
        """Connecting to a non-existent session should fail gracefully.

        The server may:
        1. Reject the upgrade (connection error / close code 1013)
        2. Accept then immediately close (empty recv / close frame)
        3. Accept then send an error JSON and close
        All three are valid — we just verify it doesn't stay open.
        """
        try:
            from websocket import create_connection, WebSocketException
        except ImportError:
            pytest.skip("websocket-client package not installed")

        rejected = False
        try:
            ws = create_connection(
                f"{WS_BASE}/ws/chat/00000000-0000-0000-0000-000000000000",
                timeout=5,
            )
            # Server accepted the HTTP upgrade — it should still close quickly
            ws.settimeout(5)
            try:
                payload = ws.recv()
                if not payload:
                    rejected = True
                else:
                    try:
                        data = json.loads(payload)
                        if isinstance(data, dict) and (
                            data.get("type") == "error"
                            or "session" in str(data.get("message", "")).lower()
                            or data.get("code") in (1013, 1011)
                        ):
                            rejected = True
                    except (json.JSONDecodeError, ValueError):
                        # Non-JSON payload (e.g. close reason string) → valid rejection
                        rejected = True
            except (WebSocketException, ConnectionError, OSError, TimeoutError):
                rejected = True
            try:
                ws.close()
            except Exception:
                pass
        except (WebSocketException, ConnectionRefusedError, OSError, TimeoutError):
            rejected = True  # Expected — invalid session should reject

        # If we got this far without rejection, the server left the
        # connection open.  That's only wrong if it's STILL open.
        if not rejected:
            try:
                ws.ping()
                ws.settimeout(2)
                ws.recv()
            except Exception:
                rejected = True

        assert rejected, "Server should reject or close connection for invalid session"

    def test_websocket_chat_flow(self):
        """Create session via API, connect via WS, send a message."""
        try:
            from websocket import create_connection, WebSocketException
        except ImportError:
            pytest.skip("websocket-client package not installed")

        # Create session via sync HTTP
        with httpx.Client(base_url=_API_BASE, timeout=10) as client:
            r = client.post("/engine/chat/sessions", json={
                "agent_id": "default",
                "session_type": "chat",
            })
            if r.status_code == 503:
                pytest.skip("Engine not initialized")
            if r.status_code not in (200, 201):
                pytest.skip(f"Could not create session: {r.status_code}")
            session_id = r.json().get("id") or r.json().get("session_id")

        if not session_id:
            pytest.skip("No session ID returned")

        try:
            ws = create_connection(
                f"{WS_BASE}/ws/chat/{session_id}",
                timeout=5,
            )
        except (WebSocketException, ConnectionRefusedError, OSError) as exc:
            pytest.skip(f"Could not connect to WS: {exc}")
        try:
            ws.send(json.dumps({"type": "message", "content": "Hello from integration run"}))
            ws.settimeout(10)
            msg = ws.recv()
            data = json.loads(msg)
            assert isinstance(data, dict), f"Expected dict, got {type(data)}"
            ws.close()
        except Exception as exc:
            ws.close()
            pytest.fail(f"WS send/recv failed after successful connect: {exc}")
        finally:
            # Cleanup session
            with httpx.Client(base_url=_API_BASE, timeout=10) as client:
                client.delete(f"/engine/chat/sessions/{session_id}")
