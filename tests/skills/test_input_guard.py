"""
Tests for the input_guard skill (Layer 0 — security).

Covers:
- Malicious input detection (SQL injection, XSS, path traversal)
- Clean input passthrough
- Severity classification
- HTML sanitization
- Path safety checks
- Output filtering
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from aria_skills.base import SkillConfig, SkillResult, SkillStatus


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes for aria_mind.security types
# ---------------------------------------------------------------------------

class _FakeThreatLevel:
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def __init__(self, value: str):
        self.value = value


class _FakeCheckResult:
    def __init__(
        self,
        allowed: bool = True,
        threat_level: str = "NONE",
        detections: list | None = None,
        sanitized_input: str = "",
        rejection_message: str = "",
    ):
        self.allowed = allowed
        self.threat_level = _FakeThreatLevel(threat_level)
        self.detections = detections or []
        self.sanitized_input = sanitized_input
        self.rejection_message = rejection_message


class _FakeGateway:
    """Mimics AriaSecurityGateway with controllable responses."""

    def __init__(self, **_kw):
        self.prompt_guard = MagicMock()
        self.prompt_guard.block_threshold = None
        self._next_result = _FakeCheckResult()

    def check_input(self, text, **kw):
        return self._next_result

    def get_security_summary(self, hours=24):
        return {"total_events": 0, "blocked": 0}


class _FakeInputSanitizer:
    @staticmethod
    def sanitize_html(text):
        return text.replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def check_sql_injection(text):
        if "DROP TABLE" in text.upper() or "' OR '1'='1" in text:
            return (False, "SQL injection pattern detected")
        return (True, "")

    @staticmethod
    def check_path_traversal(path):
        if ".." in path:
            return (False, "Path traversal detected")
        return (True, "")

    @staticmethod
    def sanitize_for_logging(text, max_len=500):
        return text[:max_len]


class _FakeOutputFilter:
    @staticmethod
    def filter_output(text, strict=False):
        return text.replace("sk-secret123", "***REDACTED***")

    @staticmethod
    def contains_sensitive(text):
        return "sk-secret123" in text


class _FakeSafeQueryBuilder:
    def __init__(self, allowed_tables=None):
        self.allowed_tables = allowed_tables or set()

    def select(self, table, columns, where=None, order_by=None, limit=None):
        if table not in self.allowed_tables:
            raise ValueError(f"Table {table} not allowed")
        return f"SELECT {','.join(columns)} FROM {table}", {}

    def insert(self, table, data):
        if table not in self.allowed_tables:
            raise ValueError(f"Table {table} not allowed")
        cols = ",".join(data.keys())
        return f"INSERT INTO {table} ({cols}) VALUES (...)", data

    def update(self, table, data, where):
        if table not in self.allowed_tables:
            raise ValueError(f"Table {table} not allowed")
        return f"UPDATE {table} SET ... WHERE ...", {**data, **where}


class _FakeRateLimitConfig:
    def __init__(self, requests_per_minute=60, requests_per_hour=600):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour


# Map threat-level strings to fake enum values for threshold_map
_FAKE_THREAT_LEVEL_ENUM = type("ThreatLevel", (), {
    "LOW": _FakeThreatLevel("LOW"),
    "MEDIUM": _FakeThreatLevel("MEDIUM"),
    "HIGH": _FakeThreatLevel("HIGH"),
    "CRITICAL": _FakeThreatLevel("CRITICAL"),
})


# ---------------------------------------------------------------------------
# Fixture: build an InputGuardSkill with mocked security module
# ---------------------------------------------------------------------------

@pytest.fixture
def input_guard_skill():
    """Return an initialized InputGuardSkill backed by fake security stubs."""
    security_module = {
        "aria_mind.security": MagicMock(
            AriaSecurityGateway=_FakeGateway,
            PromptGuard=MagicMock(),
            InputSanitizer=_FakeInputSanitizer,
            OutputFilter=_FakeOutputFilter,
            RateLimitConfig=_FakeRateLimitConfig,
            ThreatLevel=_FAKE_THREAT_LEVEL_ENUM,
            SafeQueryBuilder=_FakeSafeQueryBuilder,
        ),
    }

    with patch.dict("sys.modules", security_module):
        # Force re-evaluation of HAS_SECURITY at import time
        import importlib
        import aria_skills.input_guard as ig_mod
        importlib.reload(ig_mod)
        from aria_skills.input_guard import InputGuardSkill

        cfg = SkillConfig(name="input_guard", config={
            "block_threshold": "high",
            "enable_logging": False,  # disable HTTP logging in tests
            "rate_limit_rpm": 60,
        })
        skill = InputGuardSkill(cfg)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_sets_available(input_guard_skill):
    """Skill initializes successfully when security module is present."""
    ok = await input_guard_skill.initialize()
    assert ok is True
    status = await input_guard_skill.health_check()
    assert status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_analyze_clean_input(input_guard_skill):
    """Clean text should be allowed with no detections."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.analyze_input("Hello, how are you?")
    assert result.success is True
    assert result.data["allowed"] is True
    assert result.data["threat_level"] == "NONE"
    assert result.data["detections"] == []


@pytest.mark.asyncio
async def test_analyze_sql_injection(input_guard_skill):
    """SQL injection pattern should be detected and blocked."""
    await input_guard_skill.initialize()
    # Configure the fake gateway to report SQL injection
    input_guard_skill._gateway._next_result = _FakeCheckResult(
        allowed=False,
        threat_level="HIGH",
        detections=["sql_injection_union", "sql_keyword_DROP"],
        sanitized_input="",
        rejection_message="Blocked: SQL injection detected",
    )
    result = await input_guard_skill.analyze_input("'; DROP TABLE users; --")
    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["threat_level"] == "HIGH"
    assert len(result.data["detections"]) > 0


@pytest.mark.asyncio
async def test_analyze_xss_attack(input_guard_skill):
    """XSS pattern should be detected."""
    await input_guard_skill.initialize()
    input_guard_skill._gateway._next_result = _FakeCheckResult(
        allowed=False,
        threat_level="MEDIUM",
        detections=["xss_script_tag"],
        sanitized_input="",
        rejection_message="Blocked: XSS detected",
    )
    result = await input_guard_skill.analyze_input('<script>alert("xss")</script>')
    assert result.success is True
    assert result.data["allowed"] is False
    assert "xss" in result.data["detections"][0].lower()


@pytest.mark.asyncio
async def test_analyze_path_traversal(input_guard_skill):
    """Path traversal patterns should be detected."""
    await input_guard_skill.initialize()
    input_guard_skill._gateway._next_result = _FakeCheckResult(
        allowed=False,
        threat_level="HIGH",
        detections=["path_traversal_dotdot"],
        sanitized_input="",
        rejection_message="Blocked: path traversal",
    )
    result = await input_guard_skill.analyze_input("../../etc/passwd")
    assert result.success is True
    assert result.data["allowed"] is False
    assert any("path" in d.lower() for d in result.data["detections"])


@pytest.mark.asyncio
async def test_severity_classification(input_guard_skill):
    """Different threat levels should be reflected in the result."""
    await input_guard_skill.initialize()
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        input_guard_skill._gateway._next_result = _FakeCheckResult(
            allowed=(level == "LOW"),
            threat_level=level,
            detections=[f"test_{level.lower()}"],
        )
        result = await input_guard_skill.analyze_input("test")
        assert result.data["threat_level"] == level


@pytest.mark.asyncio
async def test_sanitize_for_html(input_guard_skill):
    """HTML entities should be escaped."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.sanitize_for_html('<img src=x onerror=alert(1)>')
    assert result.success is True
    assert "<" not in result.data["sanitized"]
    assert "&lt;" in result.data["sanitized"]


@pytest.mark.asyncio
async def test_check_sql_safety_clean(input_guard_skill):
    """Clean text passes SQL safety check."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.check_sql_safety("SELECT * FROM goals WHERE status='active'")
    assert result.success is True
    # Note: our fake just checks for 'DROP TABLE' and OR '1'='1'
    assert result.data["is_safe"] is True


@pytest.mark.asyncio
async def test_check_sql_safety_malicious(input_guard_skill):
    """SQL injection text fails safety check."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.check_sql_safety("' OR '1'='1")
    assert result.success is True
    assert result.data["is_safe"] is False


@pytest.mark.asyncio
async def test_check_path_safety(input_guard_skill):
    """Path traversal is flagged."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.check_path_safety("../../etc/shadow")
    assert result.success is True
    assert result.data["is_safe"] is False


@pytest.mark.asyncio
async def test_check_path_safety_clean(input_guard_skill):
    """Normal path passes."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.check_path_safety("/var/log/aria.log")
    assert result.success is True
    assert result.data["is_safe"] is True


@pytest.mark.asyncio
async def test_filter_output_redacts_secrets(input_guard_skill):
    """Sensitive tokens should be redacted from output."""
    await input_guard_skill.initialize()
    result = await input_guard_skill.filter_output("My key is sk-secret123 please keep it safe")
    assert result.success is True
    assert "sk-secret123" not in result.data["filtered"]
    assert result.data["contained_sensitive"] is True


@pytest.mark.asyncio
async def test_unavailable_skill_returns_fail(input_guard_skill):
    """Methods should fail gracefully when skill is not initialized."""
    # Don't call initialize — skill stays UNAVAILABLE
    result = await input_guard_skill.analyze_input("test")
    assert result.success is False
    assert "not available" in result.error.lower()
