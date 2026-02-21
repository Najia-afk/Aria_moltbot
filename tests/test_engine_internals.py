"""
Unit tests for engine internal modules that have no direct API endpoints.

Covers pure functions (no DB, no mocks) in:
- routing.py  → scoring functions
- auto_session.py  → title generation
- session_protection.py  → sliding window, sanitization, exceptions
"""
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make aria_engine importable + fake the 'db' module path for engine imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "api"))  # so 'from db.models import ...' works


# ── routing.py ────────────────────────────────────────────────────────────────

class TestRoutingScoring:
    """Test pure scoring functions from aria_engine/routing.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from aria_engine.routing import (
            compute_specialty_match,
            compute_load_score,
            compute_pheromone_score,
            COLD_START_SCORE,
        )
        self.compute_specialty_match = compute_specialty_match
        self.compute_load_score = compute_load_score
        self.compute_pheromone_score = compute_pheromone_score
        self.COLD_START_SCORE = COLD_START_SCORE

    # ── compute_specialty_match ───────────────────────────────────

    def test_specialty_none_focus_returns_generalist(self):
        score = self.compute_specialty_match("deploy my app", None)
        assert score == 0.3  # generalist default

    def test_specialty_unknown_focus_returns_generalist(self):
        score = self.compute_specialty_match("hello world", "unknown_focus")
        assert score == 0.3

    def test_specialty_matching_social_keywords(self):
        score = self.compute_specialty_match(
            "tweet this post on twitter for community engagement", "social"
        )
        assert score >= 0.6  # at least 1 keyword match

    def test_specialty_no_keywords_match(self):
        score = self.compute_specialty_match("hello world", "devops")
        assert score == 0.1  # zero match

    def test_specialty_strong_match(self):
        score = self.compute_specialty_match(
            "deploy docker kubernetes pipeline CI/CD", "devops"
        )
        assert score >= 0.8  # multiple keyword hits

    # ── compute_load_score ────────────────────────────────────────

    def test_load_disabled_returns_zero(self):
        assert self.compute_load_score("disabled", 0) == 0.0

    def test_load_error_returns_low(self):
        assert self.compute_load_score("error", 0) == 0.1

    def test_load_busy_returns_medium(self):
        assert self.compute_load_score("busy", 0) == 0.3

    def test_load_idle_no_failures_returns_one(self):
        assert self.compute_load_score("idle", 0) == 1.0

    def test_load_idle_with_failures_decreases(self):
        score = self.compute_load_score("idle", 3)
        assert 0.2 <= score < 1.0

    def test_load_idle_many_failures_capped(self):
        score = self.compute_load_score("idle", 100)
        assert score >= 0.2  # capped floor

    # ── compute_pheromone_score ───────────────────────────────────

    def test_pheromone_empty_records(self):
        assert self.compute_pheromone_score([]) == self.COLD_START_SCORE

    def test_pheromone_recent_success(self):
        records = [
            {
                "created_at": datetime.now(timezone.utc),
                "success": True,
                "speed_score": 0.8,
                "cost_score": 0.7,
            }
        ]
        score = self.compute_pheromone_score(records)
        assert score > self.COLD_START_SCORE  # should beat cold start

    def test_pheromone_old_records_decay(self):
        recent = [
            {
                "created_at": datetime.now(timezone.utc),
                "success": True,
                "speed_score": 0.8,
                "cost_score": 0.7,
            }
        ]
        old = [
            {
                "created_at": datetime.now(timezone.utc) - timedelta(days=365),
                "success": True,
                "speed_score": 0.8,
                "cost_score": 0.7,
            }
        ]
        score_recent = self.compute_pheromone_score(recent)
        score_old = self.compute_pheromone_score(old)
        # With DECAY_FACTOR=0.95 per day, 365 days means ~0 weight
        assert score_recent >= score_old

    def test_pheromone_failures_lower_score(self):
        success = [
            {"created_at": datetime.now(timezone.utc), "success": True}
        ]
        failure = [
            {"created_at": datetime.now(timezone.utc), "success": False}
        ]
        assert self.compute_pheromone_score(success) > self.compute_pheromone_score(failure)

    def test_pheromone_bounded_zero_to_one(self):
        records = [
            {
                "created_at": datetime.now(timezone.utc) - timedelta(days=i),
                "success": i % 2 == 0,
                "speed_score": 0.5,
                "cost_score": 0.5,
            }
            for i in range(20)
        ]
        score = self.compute_pheromone_score(records)
        assert 0.0 <= score <= 1.0


# ── auto_session.py ───────────────────────────────────────────────────────────

class TestAutoSession:
    """Test generate_auto_title() from aria_engine/auto_session.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from aria_engine.auto_session import generate_auto_title, AUTO_TITLE_MAX_LENGTH
        self.generate_auto_title = generate_auto_title
        self.max_length = AUTO_TITLE_MAX_LENGTH

    def test_simple_message(self):
        title = self.generate_auto_title("How do I deploy Docker?")
        assert title == "How do I deploy Docker?"

    def test_multiline_takes_first_line(self):
        title = self.generate_auto_title("First line\nSecond line\nThird")
        assert "First line" in title
        assert "Second line" not in title

    def test_long_message_truncated(self):
        msg = "A" * 200
        title = self.generate_auto_title(msg)
        assert len(title) <= self.max_length

    def test_empty_returns_fallback(self):
        title = self.generate_auto_title("")
        assert title.startswith("Session ")

    def test_whitespace_only_returns_fallback(self):
        title = self.generate_auto_title("   \n\t  ")
        assert title.startswith("Session ")

    def test_strips_whitespace(self):
        title = self.generate_auto_title("  Hello world  ")
        assert title == "Hello world"


# ── session_protection.py ─────────────────────────────────────────────────────

class TestSessionProtection:
    """Test pure utilities from aria_engine/session_protection.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from aria_engine.session_protection import (
            SlidingWindow,
            RateLimitError,
            ValidationError,
            SessionFullError,
            ALLOWED_ROLES,
            MAX_MESSAGE_LENGTH,
            MIN_MESSAGE_LENGTH,
        )
        self.SlidingWindow = SlidingWindow
        self.RateLimitError = RateLimitError
        self.ValidationError = ValidationError
        self.SessionFullError = SessionFullError
        self.ALLOWED_ROLES = ALLOWED_ROLES
        self.MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH
        self.MIN_MESSAGE_LENGTH = MIN_MESSAGE_LENGTH

    # ── SlidingWindow ─────────────────────────────────────────────

    def test_sliding_window_empty(self):
        sw = self.SlidingWindow()
        assert sw.count_in_window(60) == 0

    def test_sliding_window_add_and_count(self):
        sw = self.SlidingWindow()
        sw.add()
        sw.add()
        sw.add()
        assert sw.count_in_window(60) == 3

    def test_sliding_window_expired_entries(self):
        sw = self.SlidingWindow()
        # Manually inject an old timestamp
        sw.timestamps.append(time.monotonic() - 120)  # 2 minutes ago
        sw.add()  # now
        assert sw.count_in_window(60) == 1  # only recent one counts

    # ── Exception classes ─────────────────────────────────────────

    def test_rate_limit_error(self):
        err = self.RateLimitError("too fast", retry_after=30)
        assert str(err) == "too fast"
        assert err.retry_after == 30

    def test_validation_error(self):
        err = self.ValidationError("bad input")
        assert str(err) == "bad input"

    def test_session_full_error(self):
        err = self.SessionFullError("session full")
        assert str(err) == "session full"

    # ── Constants ─────────────────────────────────────────────────

    def test_allowed_roles(self):
        assert "user" in self.ALLOWED_ROLES
        assert "assistant" in self.ALLOWED_ROLES
        assert "system" in self.ALLOWED_ROLES
        assert "tool" in self.ALLOWED_ROLES

    def test_message_length_constants(self):
        assert self.MIN_MESSAGE_LENGTH == 1
        assert self.MAX_MESSAGE_LENGTH == 100_000

    # ── sanitize_content ──────────────────────────────────────────

    def test_sanitize_strips_control_chars(self):
        from aria_engine.session_protection import SessionProtection
        # Create minimal instance — sanitize_content is pure
        mock_engine = MagicMock()
        sp = SessionProtection(mock_engine)
        cleaned = sp.sanitize_content("Hello\x00World\x07!")
        assert "\x00" not in cleaned
        assert "\x07" not in cleaned
        assert "Hello" in cleaned
        assert "World" in cleaned

    def test_sanitize_preserves_newlines(self):
        from aria_engine.session_protection import SessionProtection
        mock_engine = MagicMock()
        sp = SessionProtection(mock_engine)
        cleaned = sp.sanitize_content("Line1\nLine2\tTabbed")
        assert "\n" in cleaned
        assert "\t" in cleaned

    def test_sanitize_strips_whitespace(self):
        from aria_engine.session_protection import SessionProtection
        mock_engine = MagicMock()
        sp = SessionProtection(mock_engine)
        cleaned = sp.sanitize_content("  hello  ")
        assert cleaned == "hello"
