"""
Unit tests for aria_agents.scoring (previously 0% coverage).

Tests cover:
- compute_pheromone: cold start, weighted formula, time decay
- select_best_agent: picks highest score, cold-start fallback, empty-list error
- PerformanceTracker.record: score updates, record trimming, auto-persist trigger
- PerformanceTracker.get_agent_stats / get_leaderboard
- PerformanceTracker.merge_external_scores: local-wins-over-DB semantics
- PerformanceTracker.save/load round-trip via a tmp_path-backed aria_memories dir
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aria_agents.scoring import (
    COLD_START_SCORE,
    PerformanceTracker,
    compute_pheromone,
    select_best_agent,
)


# ── compute_pheromone ──────────────────────────────────────────────────────


def test_compute_pheromone_empty_records_returns_cold_start():
    assert compute_pheromone([]) == COLD_START_SCORE


def test_compute_pheromone_all_success_fast_cheap_scores_high():
    records = [
        {"success": True, "speed_score": 1.0, "cost_score": 1.0, "created_at": datetime.now(timezone.utc)}
        for _ in range(5)
    ]
    score = compute_pheromone(records)
    assert score == pytest.approx(1.0, abs=1e-6)


def test_compute_pheromone_all_failure_scores_low():
    records = [
        {"success": False, "speed_score": 0.0, "cost_score": 0.0, "created_at": datetime.now(timezone.utc)}
        for _ in range(5)
    ]
    assert compute_pheromone(records) == pytest.approx(0.0, abs=1e-6)


def test_compute_pheromone_weights_success_most_heavily():
    """success=0.6 weight should dominate over speed/cost (0.3 + 0.1)."""
    now = datetime.now(timezone.utc)
    high_success_low_other = compute_pheromone(
        [{"success": True, "speed_score": 0.0, "cost_score": 0.0, "created_at": now}]
    )
    low_success_high_other = compute_pheromone(
        [{"success": False, "speed_score": 1.0, "cost_score": 1.0, "created_at": now}]
    )
    assert high_success_low_other > low_success_high_other


def test_compute_pheromone_accepts_iso_string_timestamps():
    record = {
        "success": True,
        "speed_score": 0.8,
        "cost_score": 0.8,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Should not raise, and should compute a sane score.
    score = compute_pheromone([record])
    assert 0.0 <= score <= 1.0


def test_compute_pheromone_older_records_decay_toward_less_influence():
    now = datetime.now(timezone.utc)
    recent_good = compute_pheromone(
        [{"success": True, "speed_score": 1.0, "cost_score": 1.0, "created_at": now}]
    )
    old_good = compute_pheromone(
        [{"success": True, "speed_score": 1.0, "cost_score": 1.0, "created_at": now - timedelta(days=30)}]
    )
    # A single record's own score isn't affected by its own decay (normalized
    # by weight_sum), but mixing an old bad record with a recent good one
    # should skew toward the recent one more than an equally-weighted average.
    mixed = compute_pheromone(
        [
            {"success": False, "speed_score": 0.0, "cost_score": 0.0, "created_at": now - timedelta(days=30)},
            {"success": True, "speed_score": 1.0, "cost_score": 1.0, "created_at": now},
        ]
    )
    naive_average = 0.5
    assert mixed > naive_average
    assert recent_good == pytest.approx(1.0, abs=1e-6)
    assert old_good == pytest.approx(1.0, abs=1e-6)


# ── select_best_agent ──────────────────────────────────────────────────────


def test_select_best_agent_picks_highest_score():
    scores = {"a": 0.2, "b": 0.9, "c": 0.5}
    assert select_best_agent(["a", "b", "c"], scores) == "b"


def test_select_best_agent_unscored_candidate_uses_cold_start():
    scores = {"a": 0.1}
    # "b" has no score → treated as COLD_START_SCORE (0.5), beats "a" (0.1).
    assert select_best_agent(["a", "b"], scores) == "b"


def test_select_best_agent_empty_candidates_raises():
    with pytest.raises(ValueError):
        select_best_agent([], {})


# ── PerformanceTracker ──────────────────────────────────────────────────────


@pytest.fixture
def tracker():
    return PerformanceTracker()


def test_record_updates_score_and_returns_it(tracker):
    score = tracker.record("agent-a", success=True, duration_ms=1000, token_cost=0.1)
    assert score == tracker.get_score("agent-a")
    assert 0.0 <= score <= 1.0


def test_get_score_unknown_agent_returns_cold_start(tracker):
    assert tracker.get_score("never-seen") == COLD_START_SCORE


def test_record_trims_to_max_records_per_agent(tracker):
    for i in range(tracker._MAX_RECORDS_PER_AGENT + 50):
        tracker.record("agent-a", success=True, duration_ms=100)
    assert len(tracker._records["agent-a"]) == tracker._MAX_RECORDS_PER_AGENT


def test_record_auto_saves_every_10_invocations(tracker, monkeypatch):
    save_calls = []
    monkeypatch.setattr(tracker, "save", lambda: save_calls.append(1) or True)
    for _ in range(10):
        tracker.record("agent-a", success=True, duration_ms=100)
    assert len(save_calls) == 1


def test_get_agent_stats_untested_agent(tracker):
    stats = tracker.get_agent_stats("never-seen")
    assert stats["status"] == "untested"
    assert stats["invocations"] == 0
    assert stats["score"] == COLD_START_SCORE


def test_get_agent_stats_after_records(tracker):
    tracker.record("agent-a", success=True, duration_ms=500)
    tracker.record("agent-a", success=False, duration_ms=1500)
    stats = tracker.get_agent_stats("agent-a")
    assert stats["invocations"] == 2
    assert stats["successes"] == 1
    assert stats["failures"] == 1
    assert stats["success_rate"] == 0.5
    assert stats["status"] == "learning"


def test_get_agent_stats_status_proven_after_10_records(tracker):
    for _ in range(11):
        tracker.record("agent-a", success=True, duration_ms=100)
    assert tracker.get_agent_stats("agent-a")["status"] == "proven"


def test_get_leaderboard_sorted_descending(tracker):
    tracker.record("low", success=False, duration_ms=5000)
    tracker.record("high", success=True, duration_ms=10)
    board = tracker.get_leaderboard()
    assert [row["agent_id"] for row in board][:2] == sorted(
        [row["agent_id"] for row in board][:2],
        key=lambda aid: -tracker.get_score(aid),
    )
    assert board[0]["score"] >= board[-1]["score"]


def test_get_best_agent_delegates_to_select_best_agent(tracker):
    tracker.record("a", success=False, duration_ms=5000)
    tracker.record("b", success=True, duration_ms=10)
    assert tracker.get_best_agent(["a", "b"]) == "b"


def test_merge_external_scores_only_fills_unscored_agents(tracker):
    tracker.record("local-agent", success=True, duration_ms=100)
    local_score_before = tracker.get_score("local-agent")

    updated = tracker.merge_external_scores({"local-agent": 0.01, "db-only-agent": 0.77})

    # local-agent already has a locally-computed score — DB must not override it.
    assert tracker.get_score("local-agent") == local_score_before
    # db-only-agent had no local score — DB value should be adopted.
    assert tracker.get_score("db-only-agent") == 0.77
    assert updated == 1


def test_export_scores_returns_copy_not_reference(tracker):
    tracker.record("a", success=True, duration_ms=100)
    exported = tracker.export_scores()
    exported["a"] = -999
    assert tracker.get_score("a") != -999


def test_save_and_load_round_trip(tracker, tmp_path, monkeypatch):
    import aria_agents.scoring as scoring_mod

    monkeypatch.setattr(scoring_mod, "_MEMORIES_PATH", str(tmp_path))
    # Also sandbox the module's dev-fallback path (Path(__file__).parent.parent)
    # so a missing primary file can never fall through to the real repo's
    # aria_memories/ directory.
    monkeypatch.setattr(scoring_mod, "__file__", str(tmp_path / "_pkg" / "aria_agents" / "scoring.py"))

    tracker.record("agent-a", success=True, duration_ms=200)
    tracker.record("agent-a", success=False, duration_ms=800)
    assert tracker.save() is True

    saved_file = tmp_path / "knowledge" / "pheromone_scores.json"
    assert saved_file.exists()

    fresh = PerformanceTracker()
    assert fresh.load() is True
    assert fresh.get_score("agent-a") == pytest.approx(tracker.get_score("agent-a"))
    assert len(fresh._records["agent-a"]) == 2


def test_load_with_no_saved_file_returns_true_and_stays_empty(tmp_path, monkeypatch):
    import aria_agents.scoring as scoring_mod

    monkeypatch.setattr(scoring_mod, "_MEMORIES_PATH", str(tmp_path))
    monkeypatch.setattr(scoring_mod, "__file__", str(tmp_path / "_pkg" / "aria_agents" / "scoring.py"))
    fresh = PerformanceTracker()
    assert fresh.load() is True
    assert fresh.get_all_scores() == {}


def test_load_is_idempotent_once_loaded(tmp_path, monkeypatch):
    import aria_agents.scoring as scoring_mod

    monkeypatch.setattr(scoring_mod, "_MEMORIES_PATH", str(tmp_path))
    monkeypatch.setattr(scoring_mod, "__file__", str(tmp_path / "_pkg" / "aria_agents" / "scoring.py"))
    tracker = PerformanceTracker()
    assert tracker.load() is True
    tracker._scores["manually-set"] = 0.42
    # Second load() call should be a no-op since _loaded is already True.
    assert tracker.load() is True
    assert tracker.get_score("manually-set") == 0.42
