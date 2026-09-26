"""Regression tests for the skill health-score formula (src/api/routers/skills.py).

tests/unit/conftest.py stubs the ``db`` package so this can import the
router module's pure scoring functions without a live DB/Docker.
"""
from routers.skills import _health_score, _health_status


def test_no_invocations_is_healthy():
    assert _health_score(0, 0, 0) == 100.0


def test_perfect_record_is_healthy():
    assert _health_score(100, 0, 500) == 100.0


def test_high_volume_with_real_errors_cannot_read_as_perfect():
    """A skill with a genuine 10% error rate must never show 100/100 just
    because it has high volume — the activity bonus must not fully buy
    back the error penalty."""
    score = _health_score(total=100, failures=10, avg_duration_ms=500)
    assert score < 100.0
    assert score <= 90.0  # ceiling is 100 - error_penalty(10)


def test_low_volume_with_no_errors_still_gets_high_score():
    score = _health_score(total=2, failures=0, avg_duration_ms=500)
    assert score == 100.0


def test_majority_failures_is_unhealthy_even_with_high_volume():
    # error_penalty alone caps at 50 pts (pre-existing design), so a fast
    # but majority-failing skill floors at "degraded" (score 50); adding a
    # real latency penalty on top is what actually pushes it to "unhealthy".
    score = _health_score(total=200, failures=120, avg_duration_ms=500)
    assert _health_status(score) != "healthy"
    assert score <= 50.0

    slow_and_failing = _health_score(total=200, failures=120, avg_duration_ms=32000)
    assert _health_status(slow_and_failing) == "unhealthy"
