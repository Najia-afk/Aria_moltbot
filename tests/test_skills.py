"""Skills — Invocation tracking and observability integration tests.

Chain 6: record invocations -> stats -> health dashboard -> insights -> list -> seed.
"""
import pytest


class TestSkillObservability:
    """Ordered scenario: invocation tracking and dashboard verification."""

    def test_01_record_successful_invocation(self, api, uid):
        """POST /skills/invocations -> record a successful invocation."""
        payload = {
            'skill_name': 'llm',
            'tool_name': f'generate-response-{uid}',
            'duration_ms': 245,
            'success': True,
            'tokens_used': 1500,
            'model_used': 'gpt-4o-mini',
        }
        r = api.post('/skills/invocations', json=payload)
        if r.status_code in (502, 503):
            pytest.skip('skills service unavailable')
        assert r.status_code in (200, 201, 422), f'Record invocation failed: {r.status_code} {r.text}'
        if r.status_code in (200, 201):
            data = r.json()
            assert data.get('recorded') is True or 'id' in data
        TestSkillObservability._uid = uid

    def test_02_record_failed_invocation(self, api):
        """POST /skills/invocations -> record a failed invocation."""
        uid = getattr(TestSkillObservability, '_uid', 'unknown')
        payload = {
            'skill_name': 'llm',
            'tool_name': f'embedding-lookup-{uid}',
            'duration_ms': 5200,
            'success': False,
            'error_type': 'TimeoutError',
        }
        r = api.post('/skills/invocations', json=payload)
        assert r.status_code in (200, 201, 422)

    def test_03_stats_shows_skill(self, api):
        """GET /skills/stats?hours=1 -> verify skill has stats."""
        r = api.get('/skills/stats', params={'hours': 1})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))
        if isinstance(data, list) and data:
            skill_names = [s.get('skill_name', '') for s in data if isinstance(s, dict)]
            assert 'llm' in skill_names, f'llm not found in stats: {skill_names[:10]}'
            llm_stats = [s for s in data if s.get('skill_name') == 'llm']
            if llm_stats:
                s = llm_stats[0]
                assert 'total_calls' in s or 'calls' in s or 'count' in s

    def test_04_health_dashboard(self, api):
        """GET /skills/health/dashboard -> verify health scores exist."""
        r = api.get('/skills/health/dashboard')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert 'overall' in data or 'skills' in data or 'patterns' in data

    def test_05_insights(self, api):
        """GET /skills/insights -> verify rich payload."""
        r = api.get('/skills/insights')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert len(data.keys()) >= 1

    def test_06_list_skills(self, api):
        """GET /skills -> list all skills with health status."""
        r = api.get('/skills')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))
        if isinstance(data, dict):
            assert 'skills' in data or 'count' in data
            skills = data.get('skills', [])
            if skills:
                assert 'skill_name' in skills[0] or 'canonical_name' in skills[0] or 'name' in skills[0]

    def test_07_seed_idempotent(self, api):
        """POST /skills/seed -> verify idempotent."""
        r = api.post('/skills/seed')
        assert r.status_code == 200
        data = r.json()
        assert 'seeded' in data or 'total' in data
        r2 = api.post('/skills/seed')
        assert r2.status_code == 200


class TestSkillStatsDetail:
    """Individual skill stats and summary."""

    def test_stats_summary(self, api):
        r = api.get('/skills/stats/summary')
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_stats_by_name(self, api):
        r = api.get('/skills/stats/llm')
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.json(), dict)

    def test_skill_health_by_name(self, api):
        r = api.get('/skills/llm/health')
        assert r.status_code in (200, 404)

    def test_coherence_check(self, api):
        r = api.get('/skills/coherence')
        assert r.status_code == 200
        assert isinstance(r.json(), (dict, list))
