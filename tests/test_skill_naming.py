# tests/test_skill_naming.py
"""
TICKET-14: Skill Naming Unification tests.

Validates:
- BaseSkill.canonical_name property
- SkillRegistry.get() dual-name lookup
- Canonical name normalization
- All 27 skill.json name fields match the canonical formula
"""
import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Concrete stub for testing abstract BaseSkill
# ---------------------------------------------------------------------------
class _StubSkill(BaseSkill):
    """Minimal concrete skill for testing canonical_name."""

    def __init__(self, python_name: str):
        self._python_name = python_name
        config = SkillConfig(name=python_name)
        super().__init__(config)

    @property
    def name(self) -> str:
        return self._python_name

    async def initialize(self) -> bool:
        return True

    async def health_check(self) -> SkillStatus:
        return SkillStatus.HEALTHY

    async def execute(self, function_name: str, **kwargs) -> SkillResult:
        return SkillResult.ok({})


# ===========================================================================
# 1. BaseSkill.canonical_name
# ===========================================================================
class TestCanonicalName:
    """BaseSkill.canonical_name returns correct kebab-case with aria- prefix."""

    @pytest.mark.parametrize(
        "python_name, expected_canonical",
        [
            ("api_client", "aria-api-client"),
            ("ci_cd", "aria-ci-cd"),
            ("data_pipeline", "aria-data-pipeline"),
            ("fact_check", "aria-fact-check"),
            ("hourly_goals", "aria-hourly-goals"),
            ("input_guard", "aria-input-guard"),
            ("knowledge_graph", "aria-knowledge-graph"),
            ("market_data", "aria-market-data"),
            ("model_switcher", "aria-model-switcher"),
            ("pytest_runner", "aria-pytest-runner"),
            ("security_scan", "aria-security-scan"),
            ("session_manager", "aria-session-manager"),
            # Single-word names (no underscore) stay simple
            ("brainstorm", "aria-brainstorm"),
            ("community", "aria-community"),
            ("database", "aria-database"),
            ("experiment", "aria-experiment"),
            ("goals", "aria-goals"),
            ("health", "aria-health"),
            ("litellm", "aria-litellm"),
            ("llm", "aria-llm"),
            ("memeothy", "aria-memeothy"),
            ("moltbook", "aria-moltbook"),
            ("performance", "aria-performance"),
            ("portfolio", "aria-portfolio"),
            ("research", "aria-research"),
            ("schedule", "aria-schedule"),
            ("social", "aria-social"),
        ],
    )
    def test_canonical_name_formula(self, python_name: str, expected_canonical: str):
        skill = _StubSkill(python_name)
        assert skill.canonical_name == expected_canonical


# ===========================================================================
# 2. SkillRegistry.get() — dual-name lookup
# ===========================================================================
class TestRegistryDualLookup:
    """SkillRegistry.get() resolves both python names and canonical names."""

    @pytest.fixture()
    def registry(self):
        """Fresh registry with a stub skill loaded."""
        reg = SkillRegistry()
        stub = _StubSkill("api_client")
        reg._skills["api_client"] = stub
        reg._skills[stub.canonical_name] = stub  # canonical alias
        return reg

    def test_get_by_python_name(self, registry: SkillRegistry):
        assert registry.get("api_client") is not None
        assert registry.get("api_client").name == "api_client"

    def test_get_by_canonical_name(self, registry: SkillRegistry):
        assert registry.get("aria-api-client") is not None
        assert registry.get("aria-api-client").name == "api_client"

    def test_get_unknown_returns_none(self, registry: SkillRegistry):
        assert registry.get("nonexistent") is None

    def test_canonical_fallback_normalization(self, registry: SkillRegistry):
        """Even if canonical key isn't pre-stored, fallback normalization works."""
        reg = SkillRegistry()
        stub = _StubSkill("market_data")
        reg._skills["market_data"] = stub  # only python name stored
        # get() should still resolve via normalization
        assert reg.get("aria-market-data") is not None
        assert reg.get("aria-market-data").name == "market_data"


# ===========================================================================
# 3. Normalization: canonical → python
# ===========================================================================
class TestNormalization:
    """Verify canonical-to-python name normalization."""

    @pytest.mark.parametrize(
        "canonical, expected_python",
        [
            ("aria-api-client", "api_client"),
            ("aria-ci-cd", "ci_cd"),
            ("aria-data-pipeline", "data_pipeline"),
            ("aria-fact-check", "fact_check"),
            ("aria-hourly-goals", "hourly_goals"),
            ("aria-input-guard", "input_guard"),
            ("aria-knowledge-graph", "knowledge_graph"),
            ("aria-market-data", "market_data"),
            ("aria-model-switcher", "model_switcher"),
            ("aria-pytest-runner", "pytest_runner"),
            ("aria-security-scan", "security_scan"),
            ("aria-session-manager", "session_manager"),
        ],
    )
    def test_normalize_canonical_to_python(self, canonical: str, expected_python: str):
        """Strip 'aria-' prefix and replace hyphens with underscores."""
        assert canonical.startswith("aria-")
        python_name = canonical[5:].replace("-", "_")
        assert python_name == expected_python


# ===========================================================================
# 4. All 27 skill.json name fields match canonical formula
# ===========================================================================
# All skill folders under aria_skills/ that contain a skill.json
SKILL_FOLDERS = [
    "api_client",
    "brainstorm",
    "ci_cd",
    "community",
    "database",
    "data_pipeline",
    "experiment",
    "fact_check",
    "goals",
    "health",
    "hourly_goals",
    "input_guard",
    "knowledge_graph",
    "litellm",
    "llm",
    "market_data",
    "memeothy",
    "model_switcher",
    "moltbook",
    "performance",
    "portfolio",
    "pytest_runner",
    "research",
    "schedule",
    "security_scan",
    "session_manager",
    "social",
]


class TestSkillJsonNaming:
    """Every skill.json 'name' field matches the canonical formula."""

    @pytest.mark.parametrize("folder", SKILL_FOLDERS)
    def test_skill_json_name_matches_canonical(self, folder: str):
        skills_dir = Path(__file__).resolve().parent.parent / "aria_skills" / folder
        manifest = skills_dir / "skill.json"
        assert manifest.exists(), f"Missing skill.json in {folder}"

        data = json.loads(manifest.read_text(encoding="utf-8"))
        expected = f"aria-{folder.replace('_', '-')}"
        assert data["name"] == expected, (
            f"skill.json name mismatch in {folder}: "
            f"got '{data['name']}', expected '{expected}'"
        )


# ===========================================================================
# 5. run_skill.py normalization
# ===========================================================================
class TestRunSkillNormalization:
    """Test that canonical names get normalized in run_skill context."""

    @pytest.mark.parametrize(
        "incoming, expected",
        [
            ("aria-api-client", "api_client"),
            ("aria-security-scan", "security_scan"),
            ("aria-pytest-runner", "pytest_runner"),
            ("database", "database"),  # non-canonical passes through
        ],
    )
    def test_run_skill_name_normalization(self, incoming: str, expected: str):
        """Simulate the normalization logic in run_skill.py."""
        skill_name = incoming
        if skill_name.startswith("aria-"):
            skill_name = skill_name[5:].replace("-", "_")
        assert skill_name == expected
