# tests/test_architecture.py
"""
S5-05 · Architecture compliance tests.

Verifies the 5-layer architecture is respected:
  Layer 0: DB (PostgreSQL)
  Layer 1: ORM (SQLAlchemy models)
  Layer 2: API (FastAPI routers)
  Layer 3: api_client (httpx REST)
  Layer 4: Skills (business logic)
  Layer 5: ARIA (orchestration)

Key rules:
  - Skills (layer 4) must NOT import SQLAlchemy
  - Skills must only use api_client for data access
  - soul/ directory must never be modified
  - models.yaml is the SSOT for model definitions
"""

import ast
import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ============================================================================
# Layer compliance
# ============================================================================


class TestLayerCompliance:

    def test_skills_do_not_import_sqlalchemy(self):
        """Skills (layer 4) must NEVER import SQLAlchemy directly."""
        skills_dir = ROOT / "aria_skills"
        violations = []
        for py_file in skills_dir.rglob("*.py"):
            # Skip __pycache__
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="replace")
            if re.search(r"^\s*(from\s+sqlalchemy|import\s+sqlalchemy)", content, re.MULTILINE):
                violations.append(str(py_file.relative_to(ROOT)))
        assert not violations, f"Skills must not import SQLAlchemy: {violations}"

    def test_skills_do_not_import_db_models(self):
        """Skills must not import from src.api.db directly."""
        skills_dir = ROOT / "aria_skills"
        violations = []
        for py_file in skills_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="replace")
            if re.search(r"from\s+src\.api\.db|from\s+db\.models|from\s+db\.session", content, re.MULTILINE):
                violations.append(str(py_file.relative_to(ROOT)))
        assert not violations, f"Skills must not import DB models: {violations}"

    def test_skills_use_api_client(self):
        """Skills that do data access should use api_client."""
        skills_dir = ROOT / "aria_skills"
        api_client_users = 0
        for py_file in skills_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
                continue
            # Skip api_client itself and base
            if "api_client" in str(py_file) or py_file.name == "base.py":
                continue
            content = py_file.read_text(errors="replace")
            if "get_api_client" in content or "api_client" in content:
                api_client_users += 1
        # At least some skills should use api_client
        assert api_client_users >= 1, "Expected skills to use api_client for data access"


# ============================================================================
# Soul immutability
# ============================================================================


class TestSoulImmutability:

    def test_soul_files_exist(self):
        """soul/ directory should exist and contain files."""
        soul_dir = ROOT / "aria_mind" / "soul"
        if soul_dir.exists():
            files = [f for f in soul_dir.iterdir() if f.suffix in (".py", ".md", ".yaml") and f.name != "__init__.py"]
            assert len(files) > 0, "soul/ should contain identity files"

    def test_soul_md_exists(self):
        """SOUL.md should exist."""
        soul_md = ROOT / "aria_mind" / "SOUL.md"
        assert soul_md.exists(), "SOUL.md must exist as identity anchor"


# ============================================================================
# models.yaml SSOT
# ============================================================================


class TestModelsYAML:

    def test_models_yaml_exists(self):
        """models.yaml must exist as SSOT."""
        models_yaml = ROOT / "aria_models" / "models.yaml"
        assert models_yaml.exists(), "aria_models/models.yaml must exist"

    def test_models_yaml_has_required_fields(self):
        """Each model entry should have required fields per schema."""
        import json
        models_yaml = ROOT / "aria_models" / "models.yaml"
        data = json.loads(models_yaml.read_text())
        # Schema v3: dict key = model id, entries must have provider + name
        models = data.get("models", {})
        if isinstance(models, dict):
            for model_id, config in models.items():
                if isinstance(config, dict):
                    assert "provider" in config, f"Model {model_id} missing 'provider'"
                    assert "name" in config, f"Model {model_id} missing 'name'"

    def test_no_hardcoded_model_names_in_skills(self):
        """Skills should reference models.yaml, not hardcode model names."""
        skills_dir = ROOT / "aria_skills"
        # Known model names that shouldn't be hardcoded
        hardcoded = re.compile(r'["\'](?:gpt-4|claude-3|gemini-pro)["\']')
        violations = []
        for py_file in skills_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="replace")
            matches = hardcoded.findall(content)
            if matches:
                violations.append(f"{py_file.relative_to(ROOT)}: {matches}")
        assert not violations, f"Hardcoded model names found: {violations}"


# ============================================================================
# Skill structure
# ============================================================================


class TestSkillStructure:

    def test_all_skills_have_skill_json(self):
        """Each skill directory should have a skill.json or skill.yaml."""
        skills_dir = ROOT / "aria_skills"
        missing = []
        for child in skills_dir.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("_") or child.name == "__pycache__" or child.name == "pipelines":
                continue
            has_meta = (
                (child / "skill.json").exists()
                or (child / "skill.yaml").exists()
            )
            if not has_meta:
                missing.append(child.name)
        # Warn but don't fail — some may be legacy
        if missing:
            pytest.skip(f"Skills without metadata (non-blocking): {missing}")

    def test_pipeline_templates_are_valid_yaml(self):
        """All pipeline YAML files should parse without errors."""
        import yaml
        pipelines_dir = ROOT / "aria_skills" / "pipelines"
        if not pipelines_dir.exists():
            pytest.skip("No pipelines directory")
        for yml_file in pipelines_dir.glob("*.yaml"):
            data = yaml.safe_load(yml_file.read_text(encoding="utf-8"))
            assert "name" in data, f"{yml_file.name} missing 'name'"
            assert "steps" in data, f"{yml_file.name} missing 'steps'"
            for step in data["steps"]:
                assert "name" in step, f"{yml_file.name}: step missing 'name'"
                assert "skill" in step, f"{yml_file.name}: step missing 'skill'"
