"""Tests for Aria structured logging and observability (TICKET-17)."""
import logging


def test_configure_logging_with_structlog():
    """configure_logging() should not crash when structlog is available."""
    from aria_mind.logging_config import configure_logging
    configure_logging()


def test_configure_logging_without_structlog(monkeypatch):
    """configure_logging() should fall back gracefully without structlog."""
    import aria_mind.logging_config as lc
    monkeypatch.setattr(lc, "HAS_STRUCTLOG", False)
    lc.configure_logging()


def test_correlation_id_var():
    """correlation_id_var should store and retrieve values."""
    from aria_mind.logging_config import correlation_id_var
    token = correlation_id_var.set("test-123")
    assert correlation_id_var.get() == "test-123"
    correlation_id_var.reset(token)


def test_new_correlation_id_length():
    """new_correlation_id() should return an 8-character string."""
    from aria_mind.logging_config import new_correlation_id
    cid = new_correlation_id()
    assert isinstance(cid, str)
    assert len(cid) == 8


def test_log_usage_structured(tmp_path):
    """BaseSkill._log_usage() should accept structured kwargs."""
    from aria_skills.base import BaseSkill, SkillConfig, SkillStatus

    class DummySkill(BaseSkill):
        @property
        def name(self) -> str:
            return "dummy"

        async def initialize(self) -> bool:
            return True

        async def health_check(self) -> SkillStatus:
            return SkillStatus.AVAILABLE

    skill = DummySkill(SkillConfig(name="dummy"))

    # Should not raise — success case
    skill._log_usage("test_op", True, extra_key="val")
    assert skill._use_count == 1
    assert skill._error_count == 0

    # Should not raise — failure case
    skill._log_usage("test_op", False, reason="timeout")
    assert skill._use_count == 2
    assert skill._error_count == 1
