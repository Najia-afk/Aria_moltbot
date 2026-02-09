"""Tests for TICKET-20: Model Naming Decoupling from LiteLLM.

Validates:
- models.yaml is valid JSON and structurally sound
- generate_litellm_config.py produces valid YAML output
- loader.py TTL cache + reload_models() works correctly
- validate_models() validates structure
- focus.py loads model hints from models.yaml (or uses fallback)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure repo root is on sys.path for script import
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

MODELS_YAML = REPO_ROOT / "aria_models" / "models.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# 1. models.yaml validity
# ─────────────────────────────────────────────────────────────────────────────


class TestModelsYamlValidity:
    """Ensure models.yaml is valid JSON and has correct structure."""

    def test_file_exists(self):
        assert MODELS_YAML.exists(), f"models.yaml not found at {MODELS_YAML}"

    def test_valid_json(self):
        content = MODELS_YAML.read_text(encoding="utf-8")
        catalog = json.loads(content)
        assert isinstance(catalog, dict)

    def test_has_schema_version(self):
        catalog = json.loads(MODELS_YAML.read_text(encoding="utf-8"))
        assert "schema_version" in catalog

    def test_has_models_section(self):
        catalog = json.loads(MODELS_YAML.read_text(encoding="utf-8"))
        assert "models" in catalog
        assert isinstance(catalog["models"], dict)
        assert len(catalog["models"]) > 0, "models section is empty"

    def test_each_model_has_required_fields(self):
        catalog = json.loads(MODELS_YAML.read_text(encoding="utf-8"))
        for model_id, entry in catalog["models"].items():
            assert "provider" in entry, f"{model_id}: missing provider"
            assert "contextWindow" in entry, f"{model_id}: missing contextWindow"

    def test_litellm_models_have_litellm_block(self):
        catalog = json.loads(MODELS_YAML.read_text(encoding="utf-8"))
        for model_id, entry in catalog["models"].items():
            if entry.get("provider") == "litellm":
                assert "litellm" in entry, f"{model_id}: litellm provider but no litellm block"
                assert "model" in entry["litellm"], f"{model_id}: litellm block missing 'model'"

    def test_has_criteria_focus_defaults(self):
        catalog = json.loads(MODELS_YAML.read_text(encoding="utf-8"))
        criteria = catalog.get("criteria", {})
        focus_defaults = criteria.get("focus_defaults", {})
        assert len(focus_defaults) > 0, "No focus_defaults in criteria"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Generator script produces valid YAML
# ─────────────────────────────────────────────────────────────────────────────


class TestGeneratorScript:
    """Test that generate_litellm_config.py produces valid output."""

    def test_generate_model_list(self):
        from scripts.generate_litellm_config import generate_model_list, _load_models_yaml
        catalog = _load_models_yaml(MODELS_YAML)
        entries = generate_model_list(catalog)
        assert len(entries) > 0, "No model entries generated"

    def test_every_entry_has_required_keys(self):
        from scripts.generate_litellm_config import generate_model_list, _load_models_yaml
        catalog = _load_models_yaml(MODELS_YAML)
        entries = generate_model_list(catalog)
        for entry in entries:
            assert "model_name" in entry
            assert "litellm_params" in entry
            assert "model" in entry["litellm_params"]
            assert "model_info" in entry
            assert "max_tokens" in entry["model_info"]

    def test_generate_full_config_string(self):
        from scripts.generate_litellm_config import (
            generate_config, _load_models_yaml, _load_existing_config,
        )
        catalog = _load_models_yaml(MODELS_YAML)
        existing = _load_existing_config(
            REPO_ROOT / "stacks" / "brain" / "litellm-config.yaml"
        )
        output = generate_config(catalog, existing, MODELS_YAML)
        assert "model_list:" in output
        assert "AUTO-GENERATED" in output
        assert "SHA-256:" in output

    def test_output_parseable_as_yaml(self):
        """If PyYAML is available, verify generated output parses."""
        yaml = pytest.importorskip("yaml")
        from scripts.generate_litellm_config import (
            generate_config, _load_models_yaml, _load_existing_config,
        )
        catalog = _load_models_yaml(MODELS_YAML)
        existing = _load_existing_config(
            REPO_ROOT / "stacks" / "brain" / "litellm-config.yaml"
        )
        output = generate_config(catalog, existing, MODELS_YAML)
        parsed = yaml.safe_load(output)
        assert isinstance(parsed, dict)
        assert "model_list" in parsed

    def test_aliases_generate_separate_entries(self):
        from scripts.generate_litellm_config import generate_model_list, _load_models_yaml
        catalog = _load_models_yaml(MODELS_YAML)
        entries = generate_model_list(catalog)
        names = [e["model_name"] for e in entries]
        # kimi has aliases kimi-k2.5, kimi-local
        assert "kimi" in names
        assert "kimi-k2.5" in names or "kimi-local" in names


# ─────────────────────────────────────────────────────────────────────────────
# 3. Loader TTL cache and reload
# ─────────────────────────────────────────────────────────────────────────────


class TestLoaderCache:
    """Test TTL cache and reload_models()."""

    def test_load_catalog_returns_dict(self):
        from aria_models.loader import load_catalog, reload_models
        reload_models()  # ensure clean state
        catalog = load_catalog()
        assert isinstance(catalog, dict)
        assert "models" in catalog

    def test_reload_models_clears_cache(self):
        import aria_models.loader as loader
        # Prime the cache
        loader.load_catalog()
        assert len(loader._cache) > 0
        # Reload should clear
        result = loader.reload_models()
        assert isinstance(result, dict)
        # Cache should have been rebuilt (1 entry)
        assert len(loader._cache) > 0

    def test_cache_reuses_within_ttl(self):
        import aria_models.loader as loader
        loader.reload_models()
        cat1 = loader.load_catalog()
        cat2 = loader.load_catalog()
        # Same object from cache
        assert cat1 is cat2

    def test_cache_expires_after_ttl(self):
        import aria_models.loader as loader
        loader.reload_models()
        cat1 = loader.load_catalog()
        # Simulate expired cache
        loader._cache_timestamp = time.monotonic() - loader._CACHE_TTL_SECONDS - 1
        cat2 = loader.load_catalog()
        # Fresh load — different object
        assert cat2 is not cat1
        assert cat2 == cat1  # same content


# ─────────────────────────────────────────────────────────────────────────────
# 4. validate_models()
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateModels:
    """Test validate_models() catches structural issues."""

    def test_valid_models_yaml(self):
        from aria_models.loader import validate_models
        errors = validate_models()
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_missing_file(self, tmp_path):
        from aria_models.loader import validate_models
        errors = validate_models(path=tmp_path / "nonexistent.yaml")
        assert any("not found" in e for e in errors)

    def test_invalid_json(self, tmp_path):
        from aria_models.loader import validate_models
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{invalid json", encoding="utf-8")
        errors = validate_models(path=bad_file)
        assert any("parse" in e.lower() or "failed" in e.lower() for e in errors)

    def test_missing_models_key(self, tmp_path):
        from aria_models.loader import validate_models
        no_models = tmp_path / "no_models.yaml"
        no_models.write_text('{"schema_version": 2}', encoding="utf-8")
        errors = validate_models(path=no_models)
        assert any("models" in e for e in errors)

    def test_missing_required_field(self, tmp_path):
        from aria_models.loader import validate_models
        bad = tmp_path / "bad_fields.yaml"
        bad.write_text(json.dumps({
            "schema_version": 2,
            "models": {
                "test-model": {
                    "provider": "litellm"
                    # missing contextWindow
                }
            }
        }), encoding="utf-8")
        errors = validate_models(path=bad)
        assert any("contextWindow" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Focus.py loads model hints
# ─────────────────────────────────────────────────────────────────────────────


class TestFocusModelHints:
    """Test focus.py model hint loading from models.yaml."""

    def test_focus_loads_from_catalog(self):
        from aria_mind.soul.focus import _get_model_hint, _HAS_CATALOG
        hint = _get_model_hint("orchestrator")
        assert hint is not None
        assert isinstance(hint, str)
        assert len(hint) > 0

    def test_focus_fallback_when_catalog_unavailable(self):
        from aria_mind.soul.focus import _FALLBACK_MODEL_HINTS
        # Fallback dict should have entries for all focus types
        expected_types = [
            "orchestrator", "devsecops", "data",
            "trader", "creative", "social", "journalist",
        ]
        for ft in expected_types:
            assert ft in _FALLBACK_MODEL_HINTS, f"Missing fallback for {ft}"

    def test_focus_model_hints_match_models_yaml(self):
        """Focus defaults from models.yaml should reference valid model IDs."""
        catalog = json.loads(MODELS_YAML.read_text(encoding="utf-8"))
        focus_defaults = catalog.get("criteria", {}).get("focus_defaults", {})
        model_ids = set(catalog.get("models", {}).keys())
        for focus_type, model_id in focus_defaults.items():
            assert model_id in model_ids, (
                f"Focus default '{focus_type}' references '{model_id}' "
                f"which is not in models.yaml"
            )

    def test_focus_manager_reports_catalog(self):
        from aria_mind.soul.focus import get_focus_manager
        mgr = get_focus_manager()
        status = mgr.status()
        assert "catalog_available" in status

    def test_all_focuses_have_model_hints(self):
        from aria_mind.soul.focus import FOCUSES
        for ft, focus in FOCUSES.items():
            assert focus.model_hint, f"Focus {ft.value} has empty model_hint"
