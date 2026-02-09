"""Tests for TICKET-30: Model Configuration Consolidation."""
import json

import pytest

pytestmark = pytest.mark.unit

from aria_models.loader import (
    build_litellm_config_yaml,
    list_all_model_ids,
    load_catalog,
    validate_catalog,
)


class TestValidateCatalog:
    """validate_catalog() uses validation.required_fields from models.yaml."""

    def test_validate_catalog_returns_empty(self):
        """Catalog passes its own validation rules."""
        errors = validate_catalog()
        assert errors == [], f"Validation errors: {errors}"

    def test_models_yaml_has_validation(self):
        """models.yaml has a top-level 'validation' section with required_fields."""
        catalog = load_catalog()
        assert "validation" in catalog
        assert "required_fields" in catalog["validation"]
        assert "schema_version" in catalog["validation"]
        assert catalog["validation"]["schema_version"] >= 3


class TestListAllModelIds:
    """list_all_model_ids() returns sorted list of all model IDs."""

    def test_returns_sorted_list(self):
        ids = list_all_model_ids()
        assert ids == sorted(ids), "list_all_model_ids must return sorted IDs"

    def test_has_13_plus_ids(self):
        ids = list_all_model_ids()
        assert len(ids) >= 13, f"Expected 13+ IDs, got {len(ids)}: {ids}"

    def test_all_strings(self):
        ids = list_all_model_ids()
        assert all(isinstance(i, str) for i in ids)


class TestBuildLitellmConfigYaml:
    """build_litellm_config_yaml() generates valid config."""

    def test_generates_string(self):
        result = build_litellm_config_yaml()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_has_auto_generated_header(self):
        result = build_litellm_config_yaml()
        assert result.startswith("# AUTO-GENERATED")

    def test_has_model_list_key(self):
        """Output contains model_list (parseable as YAML or JSON)."""
        result = build_litellm_config_yaml()
        # Strip the comment header lines, then parse
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(result)
        except ImportError:
            # Fallback: strip comment lines, parse as JSON
            lines = [l for l in result.splitlines() if not l.startswith("#")]
            data = json.loads("\n".join(lines))

        assert "model_list" in data
        assert isinstance(data["model_list"], list)
        assert len(data["model_list"]) > 0

    def test_has_litellm_settings(self):
        result = build_litellm_config_yaml()
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(result)
        except ImportError:
            lines = [l for l in result.splitlines() if not l.startswith("#")]
            data = json.loads("\n".join(lines))

        assert "litellm_settings" in data
        assert data["litellm_settings"]["drop_params"] is True


class TestModelsYamlHasLitellmBlocks:
    """Every model entry in models.yaml must have a litellm section."""

    def test_all_models_have_litellm(self):
        catalog = load_catalog()
        models = catalog.get("models", {})
        missing = [mid for mid, entry in models.items() if "litellm" not in entry]
        assert missing == [], f"Models missing litellm block: {missing}"

    def test_litellm_blocks_have_model_key(self):
        catalog = load_catalog()
        models = catalog.get("models", {})
        for mid, entry in models.items():
            litellm = entry.get("litellm", {})
            assert "model" in litellm, f"Model '{mid}': litellm block missing 'model' key"


class TestFocusPyReadsModelsYaml:
    """focus.py reads model hints from models.yaml, not hardcoded values."""

    def test_get_focus_default_returns_valid(self):
        """get_focus_default returns a model ID that exists in the catalog."""
        from aria_models.loader import get_focus_default as loader_get_focus

        catalog = load_catalog()
        model_ids = list(catalog.get("models", {}).keys())

        for focus_type in ["orchestrator", "devsecops", "data", "trader", "creative", "social", "journalist"]:
            result = loader_get_focus(focus_type)
            assert result is not None, f"No focus default for '{focus_type}'"
            assert result in model_ids, f"Focus '{focus_type}' -> '{result}' not in catalog"

    def test_focus_manager_reports_catalog_available(self):
        """FocusManager.status() should show catalog_available=True."""
        from aria_mind.soul.focus import get_focus_manager

        mgr = get_focus_manager()
        status = mgr.status()
        assert status["catalog_available"] is True
        assert status["model_hint"] is not None
