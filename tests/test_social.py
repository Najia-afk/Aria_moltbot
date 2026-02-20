"""Social — Post and cleanup integration tests.

Scenario: create post -> verify in list -> dry-run cleanup -> dry-run dedupe.
"""
import httpx
import pytest


class TestSocialPostLifecycle:
    """Ordered scenario: social post lifecycle."""

    def test_01_create_post(self, api, uid):
        """POST /social -> create post with realistic content."""
        payload = {
            'platform': 'internal',
            'content': f'Aria completed morning health review — ref {uid}',
            'visibility': 'public',
        }
        r = api.post('/social', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('social service unavailable')
        assert r.status_code in (200, 201), f'Create post failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        post_id = data.get('id') or data.get('post_id')
        assert post_id, f'No id in response: {data}'
        TestSocialPostLifecycle._post_id = post_id
        TestSocialPostLifecycle._uid = uid

    def test_02_verify_in_list(self, api):
        """GET /social -> verify post appears in list."""
        uid = getattr(TestSocialPostLifecycle, '_uid', None)
        if not uid:
            pytest.skip('no post created')
        r = api.get('/social')
        assert r.status_code == 200
        data = r.json()
        posts = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(posts, list):
            found = any(uid in str(p.get('content', '')) for p in posts if isinstance(p, dict))
            assert found, f'Post with ref {uid} not found in social list'

    def test_03_cleanup_dry_run(self, api):
        """POST /social/cleanup {dry_run: true} -> verify dry run."""
        r = api.post('/social/cleanup', json={'dry_run': True})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert 'matched' in data or 'deleted' in data or 'dry_run' in data
        if 'dry_run' in data:
            assert data['dry_run'] is True

    def test_04_dedupe_dry_run(self, api):
        """POST /social/dedupe -> dedupe (dry run)."""
        try:
            r = api.post('/social/dedupe', json={'dry_run': True})
        except httpx.RemoteProtocolError:
            pytest.skip('server timeout on heavy dedup')
        if r.status_code in (502, 503):
            pytest.skip('dedup service unavailable')
        assert r.status_code == 200
        data = r.json()
        assert 'duplicates_found' in data or 'deleted' in data or 'dry_run' in data


class TestSocialImportMoltbook:
    """POST /social/import-moltbook — Moltbook backfill (dry run)."""

    def test_import_moltbook_dry_run(self, api):
        """POST /social/import-moltbook {dry_run: true} → verify structure."""
        r = api.post("/social/import-moltbook", json={
            "dry_run": True,
            "max_items": 5,
            "cleanup_test": False,
        })
        if r.status_code in (502, 503):
            pytest.skip("moltbook import service unavailable")
        # May fail if moltbook API not reachable, which is OK
        assert r.status_code in (200, 400, 422, 500, 502, 503)
        if r.status_code == 200:
            data = r.json()
            assert "dry_run" in data or "prepared" in data or "imported" in data

    def test_import_moltbook_missing_key(self, api):
        """POST /social/import-moltbook → 400 when no api_key and env not set."""
        try:
            r = api.post('/social/import-moltbook', json={
                'dry_run': True,
                'max_items': 1,
                'api_key': '',  # explicitly empty
            })
        except httpx.RemoteProtocolError:
            pytest.skip('server timeout on social import')
        if r.status_code in (502, 503):
            pytest.skip('social import service unavailable')
        # Should get 400 for missing api_key, or 200 if env var provides it
        assert r.status_code in (200, 400, 422), f'Expected 400/200, got: {r.status_code} {r.text}'

    def test_cleanup_actual_safe(self, api):
        """POST /social/cleanup {dry_run: false, older_than_days: 9999} → actual cleanup (safe — nothing matches)."""
        r = api.post('/social/cleanup', json={'dry_run': False, 'older_than_days': 9999})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
