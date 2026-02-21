"""Proposals — Self-improvement proposal review workflow integration tests.

Chain 8: create -> list by status -> read detail -> approve -> verify -> implement -> verify.
"""
import pytest


class TestProposalWorkflow:
    """Ordered scenario: full proposal review lifecycle."""

    def test_01_create_proposal(self, api, uid):
        """POST /proposals -> create with realistic title/description/category."""
        payload = {
            'title': f'Optimize database connection pooling — ref {uid}',
            'description': 'Reduce idle connections and implement PgBouncer for connection pooling. '
                           'Expected to decrease p99 latency by 25% during peak hours.',
            'category': 'performance',
            'risk_level': 'medium',
            'rationale': 'Current pool exhaustion during traffic spikes causes 503 errors.',
        }
        r = api.post('/proposals', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('proposals service unavailable')
        assert r.status_code in (200, 201), f'Create failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        prop_id = data.get('id') or data.get('proposal_id')
        assert prop_id, f'No id in response: {data}'
        TestProposalWorkflow._prop_id = prop_id
        TestProposalWorkflow._uid = uid

    def test_02_list_proposals_by_status(self, api):
        """GET /proposals?status=proposed -> verify our proposal in list."""
        r = api.get('/proposals', params={'status': 'proposed'})
        assert r.status_code == 200
        data = r.json()
        proposals = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(proposals, list):
            prop_ids = [p.get('id') or p.get('proposal_id') for p in proposals if isinstance(p, dict)]
            pid = getattr(TestProposalWorkflow, '_prop_id', None)
            if pid:
                assert str(pid) in [str(x) for x in prop_ids], f'Proposal {pid} not found in list'

    def test_03_read_proposal_detail(self, api):
        """GET /proposals/{id} -> verify full detail matches."""
        pid = getattr(TestProposalWorkflow, '_prop_id', None)
        if not pid:
            pytest.skip('no proposal created')
        r = api.get(f'/proposals/{pid}')
        assert r.status_code == 200
        data = r.json()
        assert 'title' in data
        uid = getattr(TestProposalWorkflow, '_uid', '')
        assert uid in data['title']
        assert 'description' in data
        assert 'connection pooling' in data['description'].lower() or 'PgBouncer' in data['description']

    def test_04_approve_proposal(self, api):
        """PATCH /proposals/{id} -> approve it."""
        pid = getattr(TestProposalWorkflow, '_prop_id', None)
        if not pid:
            pytest.skip('no proposal created')
        r = api.patch(f'/proposals/{pid}', json={'status': 'approved', 'reviewed_by': 'integration-suite'})
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            data = r.json()
            assert data.get('updated') is True or data.get('status') == 'approved'

    def test_05_verify_approved(self, api):
        """GET /proposals/{id} -> verify status is approved."""
        pid = getattr(TestProposalWorkflow, '_prop_id', None)
        if not pid:
            pytest.skip('no proposal created')
        r = api.get(f'/proposals/{pid}')
        assert r.status_code == 200
        data = r.json()
        assert data.get('status') == 'approved', f'Expected approved, got: {data.get("status")}'

    def test_06_mark_implemented(self, api):
        """PATCH /proposals/{id} -> mark implemented."""
        pid = getattr(TestProposalWorkflow, '_prop_id', None)
        if not pid:
            pytest.skip('no proposal created')
        r = api.patch(f'/proposals/{pid}', json={'status': 'implemented'})
        assert r.status_code in (200, 422)

    def test_07_verify_implemented(self, api):
        """GET /proposals/{id} -> verify status is implemented."""
        pid = getattr(TestProposalWorkflow, '_prop_id', None)
        if not pid:
            pytest.skip('no proposal created')
        r = api.get(f'/proposals/{pid}')
        assert r.status_code == 200
        data = r.json()
        assert data.get('status') == 'implemented', f'Expected implemented, got: {data.get("status")}'

    def test_08_cleanup(self, api):
        """DELETE /proposals/{id} -> cleanup."""
        pid = getattr(TestProposalWorkflow, '_prop_id', None)
        if not pid:
            pytest.skip('no proposal created')
        r = api.delete(f'/proposals/{pid}')
        assert r.status_code in (200, 204, 404, 405)


class TestProposalEdgeCases:
    def test_nonexistent_proposal_returns_404(self, api):
        r = api.get('/proposals/00000000-0000-0000-0000-000000000000')
        assert r.status_code == 404
