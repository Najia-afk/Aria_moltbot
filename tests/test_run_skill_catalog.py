"""Tests for TICKET-13: run_skill Service Catalog & Skill Listing."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aria_mind.skills.run_skill import SKILL_REGISTRY, _merge_registries


class TestSkillRegistry:
    """Test SKILL_REGISTRY dict basics."""

    def test_registry_is_dict(self):
        assert isinstance(SKILL_REGISTRY, dict)

    def test_registry_has_entries(self):
        assert len(SKILL_REGISTRY) > 0

    def test_registry_entries_have_correct_structure(self):
        for name, entry in SKILL_REGISTRY.items():
            assert isinstance(name, str), f"Key {name!r} should be str"
            assert len(entry) == 3, f"{name}: expected 3-tuple (mod, cls, config_fn)"
            mod, cls_name, config_fn = entry
            assert isinstance(mod, str), f"{name}: module should be str"
            assert isinstance(cls_name, str), f"{name}: class name should be str"
            assert callable(config_fn), f"{name}: config_factory should be callable"

    def test_api_client_is_first_key(self):
        """api_client should be listed first (ordering matters per comment)."""
        first_key = next(iter(SKILL_REGISTRY))
        assert first_key == "api_client"

    def test_database_is_in_registry(self):
        """database should be present in SKILL_REGISTRY."""
        assert "database" in SKILL_REGISTRY


class TestMergeRegistries:
    """Test that _merge_registries integrates decorator-registered skills."""

    def test_merge_does_not_crash(self):
        """_merge_registries should not raise even if SkillRegistry is empty."""
        _merge_registries()

    def test_merge_adds_new_skills(self):
        """Skills in SkillRegistry._skill_classes but not SKILL_REGISTRY get added."""
        from aria_skills.registry import SkillRegistry
        from aria_skills.base import BaseSkill, SkillConfig, SkillStatus

        # Create a dummy skill class
        class _TestDummySkill(BaseSkill):
            @property
            def name(self):
                return "_test_dummy_catalog"

            async def initialize(self):
                return True

            async def health_check(self):
                return SkillStatus.AVAILABLE

        # Manually register it
        SkillRegistry._skill_classes["_test_dummy_catalog"] = _TestDummySkill

        try:
            _merge_registries()
            assert "_test_dummy_catalog" in SKILL_REGISTRY
            mod, cls_name, cfg = SKILL_REGISTRY["_test_dummy_catalog"]
            assert cls_name == "_TestDummySkill"
        finally:
            # Clean up
            SkillRegistry._skill_classes.pop("_test_dummy_catalog", None)
            SKILL_REGISTRY.pop("_test_dummy_catalog", None)


class TestCanonicalNameNormalization:
    """Test canonical name → python name normalization in run_skill()."""

    @pytest.mark.asyncio
    async def test_canonical_name_resolves(self):
        from aria_mind.skills.run_skill import run_skill

        # "aria-api-client" should normalize to "api_client" which exists
        # We don't actually call the skill, but verify normalization by checking
        # that it doesn't return "Unknown skill: aria-api-client"
        result = await run_skill("aria-api-client", "nonexistent_method", {})
        # Should NOT say unknown skill for api_client
        if "error" in result:
            assert "Unknown skill" not in result["error"], (
                "aria-api-client should normalize to api_client"
            )

    @pytest.mark.asyncio
    async def test_unknown_canonical_name(self):
        from aria_mind.skills.run_skill import run_skill

        result = await run_skill("aria-no-such-skill-xyz", "foo", {})
        assert "error" in result
        assert "Unknown skill" in result["error"]


class TestListSkillsCLI:
    """Test --list-skills CLI flag."""

    def test_list_skills_output(self):
        result = subprocess.run(
            [sys.executable, "aria_mind/skills/run_skill.py", "--list-skills"],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
            timeout=30,
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        # Header + separator + at least one skill
        assert len(lines) >= 3, f"Expected header + separator + skills, got:\n{result.stdout}"
        assert "Name" in lines[0]
        assert "Canonical" in lines[0]
        assert "---" in lines[1]
        # Check a known skill appears
        assert any("api_client" in line for line in lines)

    def test_list_skills_shows_canonical(self):
        result = subprocess.run(
            [sys.executable, "aria_mind/skills/run_skill.py", "--list-skills"],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
            timeout=30,
        )
        assert "aria-api-client" in result.stdout


class TestExportCatalogCLI:
    """Test --export-catalog CLI flag."""

    def test_export_catalog_creates_json(self):
        catalog_path = Path(__file__).resolve().parent.parent / "aria_memories" / "exports" / "skill_catalog.json"
        # Remove if exists from prior runs
        catalog_path.unlink(missing_ok=True)

        result = subprocess.run(
            [sys.executable, "aria_mind/skills/run_skill.py", "--export-catalog"],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
            timeout=60,
        )
        assert result.returncode == 0
        assert "Catalog written" in result.stdout
        assert catalog_path.exists(), "skill_catalog.json should be created"

        catalog = json.loads(catalog_path.read_text())
        assert "generated_at" in catalog
        assert "skills" in catalog
        assert isinstance(catalog["skills"], list)
        assert len(catalog["skills"]) > 0

    def test_catalog_entries_have_name(self):
        catalog_path = Path(__file__).resolve().parent.parent / "aria_memories" / "exports" / "skill_catalog.json"
        if not catalog_path.exists():
            pytest.skip("Run --export-catalog test first")
        catalog = json.loads(catalog_path.read_text())
        for entry in catalog["skills"]:
            assert "name" in entry


class TestPositionalArgsStillWork:
    """Ensure existing positional interface is not broken."""

    def test_no_args_shows_usage(self):
        result = subprocess.run(
            [sys.executable, "aria_mind/skills/run_skill.py"],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
            timeout=30,
        )
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert "error" in output
        assert "Usage" in output["error"]
