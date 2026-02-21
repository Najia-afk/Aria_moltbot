"""Thoughts — Create and verify integration tests.

Scenario: create -> verify in list -> verify pagination -> cleanup.
"""
import pytest


class TestThoughtLifecycle:
    """Ordered scenario: thought creation and retrieval."""

    def test_01_create_thought(self, api, uid):
        """POST /thoughts -> create with realistic content."""
        payload = {
            'content': f'Observed high latency on /goals endpoint during peak hours — ref {uid}',
            'category': 'observation',
            'metadata': {'source': 'monitoring', 'severity': 'medium'},
        }
        r = api.post('/thoughts', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('thoughts service unavailable')
        assert r.status_code in (200, 201), f'Create thought failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        thought_id = data.get('id') or data.get('thought_id')
        assert thought_id, f'No id in response: {data}'
        TestThoughtLifecycle._thought_id = thought_id
        TestThoughtLifecycle._uid = uid

    def test_02_verify_in_list(self, api):
        """GET /thoughts -> verify thought appears with created_at."""
        uid = getattr(TestThoughtLifecycle, '_uid', None)
        if not uid:
            pytest.skip('no thought created')
        r = api.get('/thoughts')
        assert r.status_code == 200
        data = r.json()
        thoughts = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(thoughts, list):
            found = any(isinstance(t, dict) and uid in str(t.get('content', '')) for t in thoughts)
            assert found, f'Thought with ref {uid} not found'
            our = [t for t in thoughts if isinstance(t, dict) and uid in str(t.get('content', ''))]
            if our:
                assert 'created_at' in our[0] or 'created' in our[0] or 'timestamp' in our[0], f'Missing timestamp: {list(our[0].keys())}'

    def test_03_pagination(self, api):
        """GET /thoughts?limit=5 -> verify pagination works."""
        r = api.get('/thoughts', params={'limit': 5, 'page': 1})
        assert r.status_code == 200
        data = r.json()
        thoughts = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(thoughts, list):
            assert len(thoughts) <= 5

    def test_04_cleanup(self, api):
        """DELETE /thoughts/{id} -> cleanup."""
        tid = getattr(TestThoughtLifecycle, '_thought_id', None)
        if not tid:
            pytest.skip('no thought created')
        r = api.delete(f'/thoughts/{tid}')
        assert r.status_code in (200, 204, 404, 405)
