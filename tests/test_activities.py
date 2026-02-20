"""Activities — Activity log lifecycle integration tests.

Scenario: log activity -> verify in list -> timeline -> visualization -> cron-summary.
"""
import pytest


class TestActivityLifecycle:
    """Ordered scenario: full activity lifecycle."""

    def test_01_log_activity(self, api, uid):
        """POST /activities -> log an activity."""
        payload = {
            'action': 'deploy',
            'skill': 'ci_cd',
            'details': {'environment': 'staging', 'version': '2.4.1', 'ref': uid},
            'success': True,
        }
        r = api.post('/activities', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('activities service unavailable')
        assert r.status_code in (200, 201), f'Create activity failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        activity_id = data.get('id') or data.get('activity_id')
        assert activity_id, f'No id in response: {data}'
        TestActivityLifecycle._activity_id = activity_id
        TestActivityLifecycle._uid = uid

    def test_02_verify_in_list(self, api):
        """GET /activities -> verify activity is in the list."""
        uid = getattr(TestActivityLifecycle, '_uid', None)
        if not uid:
            pytest.skip('no activity created')
        r = api.get('/activities', params={'action': 'deploy'})
        assert r.status_code == 200
        data = r.json()
        activities = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(activities, list):
            found = any(isinstance(a, dict) and uid in str(a.get('details', {})) for a in activities)
            assert found, f'Activity with ref {uid} not found in list'

    def test_03_timeline(self, api):
        """GET /activities/timeline -> verify daily counts."""
        r = api.get('/activities/timeline')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))
        if isinstance(data, list) and data:
            assert 'day' in data[0] or 'date' in data[0] or 'count' in data[0]

    def test_04_visualization(self, api):
        """GET /activities/visualization -> verify rich payload."""
        r = api.get('/activities/visualization')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert len(data.keys()) >= 1

    def test_05_cron_summary(self, api):
        """GET /activities/cron-summary -> verify structure."""
        r = api.get('/activities/cron-summary')
        assert r.status_code == 200
        assert isinstance(r.json(), (dict, list))

    def test_06_cleanup(self, api):
        """DELETE /activities/{id} -> cleanup."""
        aid = getattr(TestActivityLifecycle, '_activity_id', None)
        if not aid:
            pytest.skip('no activity created')
        r = api.delete(f'/activities/{aid}')
        assert r.status_code in (200, 204, 404, 405)
