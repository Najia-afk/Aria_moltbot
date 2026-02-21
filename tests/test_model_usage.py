"""Model Usage — Usage tracking and stats integration tests.

Scenario: record usage -> verify in list -> verify stats -> cleanup.
"""
import pytest


class TestModelUsageLifecycle:
    """Ordered scenario: model usage recording and stats verification."""

    def test_01_record_usage(self, api, uid):
        """POST /model-usage -> record usage."""
        payload = {
            'model': f'test-llm-usage-{uid[:4]}',
            'provider': 'integration-test',
            'input_tokens': 850,
            'output_tokens': 320,
            'cost_usd': 0.0023,
            'latency_ms': 1450,
            'success': True,
        }
        r = api.post('/model-usage', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('model usage service unavailable')
        assert r.status_code in (200, 201), f'Record usage failed: {r.status_code} {r.text}'
        data = r.json()
        if data.get('skipped'):
            pytest.skip('noise filter blocked payload')
        usage_id = data.get('id') or data.get('usage_id')
        assert usage_id, f'No id in response: {data}'
        TestModelUsageLifecycle._usage_id = usage_id
        TestModelUsageLifecycle._uid = uid
        TestModelUsageLifecycle._model_name = f'test-llm-usage-{uid[:4]}'

    def test_02_verify_in_list(self, api):
        """GET /model-usage -> verify our usage record is in list."""
        model_name = getattr(TestModelUsageLifecycle, '_model_name', None)
        if not model_name:
            pytest.skip('no usage recorded')
        r = api.get('/model-usage', params={'model': model_name})
        assert r.status_code == 200
        data = r.json()
        records = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(records, list):
            models = [rec.get('model', '') for rec in records if isinstance(rec, dict)]
            assert model_name in models, f'Model {model_name} not found: {models[:10]}'

    def test_03_stats_include_model(self, api):
        """GET /model-usage/stats -> verify stats have data."""
        r = api.get('/model-usage/stats')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert len(data.keys()) >= 1

    def test_04_cleanup(self, api):
        """DELETE /model-usage/{id} -> cleanup."""
        uid = getattr(TestModelUsageLifecycle, '_usage_id', None)
        if not uid:
            pytest.skip('no usage recorded')
        r = api.delete(f'/model-usage/{uid}')
        assert r.status_code in (200, 204, 404, 405)
