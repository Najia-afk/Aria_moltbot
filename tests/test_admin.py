"""Admin endpoint tests — service control, soul files, file browser, maintenance."""
import os
import pytest

ADMIN_TOKEN = os.getenv("ARIA_ADMIN_TOKEN", "")


class TestAdmin:
    def test_table_stats(self, api):
        r = api.get("/table-stats")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_maintenance(self, api):
        r = api.post("/maintenance", json={"action": "vacuum"})
        assert r.status_code in (200, 422)

    def test_service_control_without_token(self, api):
        r = api.post("/admin/services/litellm/restart")
        assert r.status_code in (403, 422, 503)

    def test_service_control_with_token(self, api):
        if not ADMIN_TOKEN:
            pytest.skip("ARIA_ADMIN_TOKEN not set")
        headers = {"X-Admin-Token": ADMIN_TOKEN}
        r = api.post("/admin/services/litellm/restart", headers=headers)
        # 403 = service control disabled, 200 = success, 503 = service issue
        assert r.status_code in (200, 403, 503)

    def test_service_control_invalid_token(self, api):
        """POST /admin/services with malformed token → 401 or 403."""
        headers = {"X-Admin-Token": "invalid-token-abc-123"}
        r = api.post("/admin/services/litellm/restart", headers=headers)
        # 403 = service control disabled (checked first), 401 = bad token
        assert r.status_code in (401, 403, 503)


class TestSoulFiles:
    def test_read_soul_file(self, api):
        r = api.get("/soul/SOUL.md")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert "content" in data or isinstance(data, str)

    def test_read_nonexistent_soul_file(self, api):
        r = api.get("/soul/NONEXISTENT.md")
        assert r.status_code == 404


class TestFileBrowser:
    def test_list_mind_files(self, api):
        r = api.get("/admin/files/mind")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_list_memories_files(self, api):
        r = api.get("/admin/files/memories")
        assert r.status_code == 200

    def test_list_agents_files(self, api):
        r = api.get("/admin/files/agents")
        assert r.status_code == 200

    def test_list_souvenirs_files(self, api):
        r = api.get("/admin/files/souvenirs")
        assert r.status_code == 200

    def test_read_mind_file(self, api):
        r = api.get("/admin/files/mind/SOUL.md")
        assert r.status_code in (200, 404)

    def test_read_memories_file(self, api):
        """GET /admin/files/memories/{path} → read a file."""
        # List memories files first, then read one if available
        r = api.get("/admin/files/memories")
        assert r.status_code == 200
        data = r.json()
        files = data if isinstance(data, list) else data.get("files", data.get("items", []))
        if isinstance(files, list) and files:
            # Try to read the first file-like item
            first = files[0] if isinstance(files[0], str) else files[0].get("name", files[0].get("path", ""))
            if first and "/" not in str(first):
                r2 = api.get(f"/admin/files/memories/{first}")
                assert r2.status_code in (200, 404)

    def test_read_agents_file(self, api):
        """GET /admin/files/agents/{path} → read a file."""
        r = api.get("/admin/files/agents")
        assert r.status_code == 200
        data = r.json()
        files = data if isinstance(data, list) else data.get("files", data.get("items", []))
        if isinstance(files, list) and files:
            first = files[0] if isinstance(files[0], str) else files[0].get("name", files[0].get("path", ""))
            if first and "/" not in str(first):
                r2 = api.get(f"/admin/files/agents/{first}")
                assert r2.status_code in (200, 404)

    def test_read_souvenirs_file(self, api):
        """GET /admin/files/souvenirs/{path} → read a file."""
        r = api.get("/admin/files/souvenirs")
        assert r.status_code == 200
        data = r.json()
        files = data if isinstance(data, list) else data.get("files", data.get("items", []))
        if isinstance(files, list) and files:
            first = files[0] if isinstance(files[0], str) else files[0].get("name", files[0].get("path", ""))
            if first and "/" not in str(first):
                r2 = api.get(f"/admin/files/souvenirs/{first}")
                assert r2.status_code in (200, 404)

    def test_read_nonexistent_file(self, api):
        r = api.get("/admin/files/mind/NONEXISTENT_FILE.md")
        assert r.status_code == 404
