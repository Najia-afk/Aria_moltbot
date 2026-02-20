"""Agent Sessions — Session lifecycle integration tests.

Scenario: create -> list -> patch -> stats -> hourly -> delete -> verify gone.
"""
import pytest


class TestSessionLifecycle:
    """Ordered scenario: full session lifecycle."""

    def test_01_create_session(self, api, uid):
        """POST /sessions -> create with agent_id, session_type."""
        payload = {
            'agent_id': f'coordinator-{uid}',
            'session_type': 'roundtable',
            'status': 'active',
            'messages_count': 0,
            'tokens_used': 0,
            'metadata': {'initiated_by': 'integration-suite', 'ref': uid},
        }
        r = api.post('/sessions', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('sessions service unavailable')
        assert r.status_code in (200, 201), f'Create session failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        session_id = data.get('id') or data.get('session_id')
        assert session_id, f'No session_id in response: {data}'
        TestSessionLifecycle._session_id = session_id
        TestSessionLifecycle._uid = uid

    def test_02_verify_in_list(self, api):
        """GET /sessions -> verify session appears."""
        uid = getattr(TestSessionLifecycle, '_uid', None)
        if not uid:
            pytest.skip('no session created')
        r = api.get('/sessions', params={'agent_id': f'coordinator-{uid}'})
        assert r.status_code == 200
        data = r.json()
        sessions = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(sessions, list):
            agent_ids = [s.get('agent_id', '') for s in sessions if isinstance(s, dict)]
            assert f'coordinator-{uid}' in agent_ids, f'Session not found. Agent IDs: {agent_ids[:10]}'

    def test_03_update_session(self, api):
        """PATCH /sessions/{id} -> update status."""
        sid = getattr(TestSessionLifecycle, '_session_id', None)
        if not sid:
            pytest.skip('no session created')
        r = api.patch(f'/sessions/{sid}', json={'status': 'completed', 'messages_count': 15, 'tokens_used': 3200})
        assert r.status_code == 200
        data = r.json()
        assert data.get('updated') is True or 'updated' in data

    def test_04_stats(self, api):
        """GET /sessions/stats -> verify stats."""
        r = api.get('/sessions/stats')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert len(data.keys()) >= 1

    def test_05_hourly(self, api):
        """GET /sessions/hourly -> verify time series data."""
        r = api.get('/sessions/hourly')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert 'items' in data or 'hours' in data or 'timezone' in data

    def test_06_delete_session(self, api):
        """DELETE /sessions/{id} -> cleanup."""
        sid = getattr(TestSessionLifecycle, '_session_id', None)
        if not sid:
            pytest.skip('no session created')
        r = api.delete(f'/sessions/{sid}')
        assert r.status_code in (200, 204)

    def test_07_verify_deleted(self, api):
        """GET /sessions -> verify session is gone after delete."""
        sid = getattr(TestSessionLifecycle, '_session_id', None)
        uid = getattr(TestSessionLifecycle, '_uid', None)
        if not sid or not uid:
            pytest.skip('no session created')
        r = api.get('/sessions', params={'agent_id': f'coordinator-{uid}'})
        assert r.status_code == 200
        data = r.json()
        sessions = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(sessions, list):
            session_ids = [str(s.get('id', '')) for s in sessions if isinstance(s, dict)]
            assert str(sid) not in session_ids, f'Session {sid} still appears after delete'
