"""Security Events — Security event lifecycle integration tests.

Scenario: create event -> verify in list -> check stats -> cleanup.
"""
import pytest


class TestSecurityEventLifecycle:
    """Ordered scenario: security event creation and stats verification."""

    def test_01_create_event(self, api, uid):
        """POST /security-events -> create event."""
        payload = {
            'threat_level': 'low',
            'threat_type': 'rate_limit_exceeded',
            'threat_patterns': ['excessive_requests'],
            'input_preview': f'GET /goals repeated 500 times — ref {uid}',
            'source': 'integration-suite',
            'blocked': False,
            'details': {'ip': '192.168.1.100', 'user_agent': 'python-httpx/0.27'},
        }
        r = api.post('/security-events', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('security events service unavailable')
        assert r.status_code in (200, 201), f'Create event failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        event_id = data.get('id') or data.get('event_id')
        assert event_id, f'No id in response: {data}'
        TestSecurityEventLifecycle._event_id = event_id
        TestSecurityEventLifecycle._uid = uid

    def test_02_verify_in_list(self, api):
        """GET /security-events -> verify event is in list."""
        uid = getattr(TestSecurityEventLifecycle, '_uid', None)
        if not uid:
            pytest.skip('no event created')
        r = api.get('/security-events')
        assert r.status_code == 200
        data = r.json()
        events = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(events, list):
            found = any(
                isinstance(e, dict) and uid in str(e.get('input_preview', '') or e.get('details', {}))
                for e in events
            )
            assert found, f'Security event with ref {uid} not found'

    def test_03_stats(self, api):
        """GET /security-events/stats -> verify counts and by_level breakdown."""
        r = api.get('/security-events/stats')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert 'total_events' in data or 'by_level' in data or 'blocked_count' in data
        if 'total_events' in data:
            assert data['total_events'] > 0
        if 'by_level' in data:
            assert isinstance(data['by_level'], (dict, list))

    def test_04_cleanup(self, api):
        """DELETE /security-events/{id} -> cleanup."""
        eid = getattr(TestSecurityEventLifecycle, '_event_id', None)
        if not eid:
            pytest.skip('no event created')
        r = api.delete(f'/security-events/{eid}')
        assert r.status_code in (200, 204, 404, 405)
