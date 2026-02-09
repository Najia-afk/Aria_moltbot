# tests/test_model_loader.py
"""Comprehensive tests for aria_models/loader.py — model catalog & helpers."""
import pytest

pytestmark = pytest.mark.unit

from aria_models.loader import (
    load_catalog,
    get_model_entry,
    list_all_model_ids,
    list_models_with_reasoning,
    build_litellm_config_entries,
    normalize_model_id,
    validate_models,
    reload_models,
)


# ── load_catalog ──────────────────────────────────────────────────────


class TestLoadCatalog:
    """Tests for load_catalog()."""

    def test_load_catalog_returns_dict(self):
        catalog = load_catalog()
        assert isinstance(catalog, dict)

    def test_load_catalog_has_models_key(self):
        catalog = load_catalog()
        assert "models" in catalog

    def test_load_catalog_has_schema_version(self):
        catalog = load_catalog()
        assert "schema_version" in catalog


# ── model count ───────────────────────────────────────────────────────


class TestModelCount:

    def test_model_count_at_least_13(self):
        """Catalog should contain 13+ model entries."""
        catalog = load_catalog()
        models = catalog.get("models", {})
        assert len(models) >= 13, f"Expected ≥13 models, got {len(models)}"


# ── required fields ───────────────────────────────────────────────────


class TestRequiredFields:

    def test_each_model_has_provider(self):
        catalog = load_catalog()
        for mid, entry in catalog["models"].items():
            assert "provider" in entry, f"Model '{mid}' missing 'provider'"

    def test_each_model_has_context_window(self):
        catalog = load_catalog()
        for mid, entry in catalog["models"].items():
            assert "contextWindow" in entry, f"Model '{mid}' missing 'contextWindow'"


# ── get_model_entry ───────────────────────────────────────────────────


class TestGetModelEntry:

    def test_known_model_returns_dict(self):
        """A known model ID should return a dict entry."""
        ids = list_all_model_ids()
        assert len(ids) > 0
        # Use the first non-alias ID from the catalog directly
        catalog = load_catalog()
        first_id = next(iter(catalog["models"]))
        entry = get_model_entry(first_id)
        assert isinstance(entry, dict)
        assert "provider" in entry

    def test_unknown_model_returns_none(self):
        entry = get_model_entry("nonexistent-model-xyz-999")
        assert entry is None

    def test_get_model_entry_with_slash(self):
        """normalize_model_id strips provider prefix before lookup."""
        catalog = load_catalog()
        first_id = next(iter(catalog["models"]))
        entry = get_model_entry(f"fake-provider/{first_id}")
        assert entry is not None


# ── list_all_model_ids ────────────────────────────────────────────────


class TestListAllModelIds:

    def test_returns_sorted_list(self):
        ids = list_all_model_ids()
        assert isinstance(ids, list)
        assert ids == sorted(ids)

    def test_all_entries_are_strings(self):
        ids = list_all_model_ids()
        assert all(isinstance(i, str) for i in ids)

    def test_non_empty(self):
        ids = list_all_model_ids()
        assert len(ids) > 0


# ── list_models_with_reasoning ────────────────────────────────────────


class TestListModelsWithReasoning:

    def test_returns_list_of_strings(self):
        reasoning = list_models_with_reasoning()
        assert isinstance(reasoning, list)
        assert all(isinstance(r, str) for r in reasoning)


# ── build_litellm_config_entries ──────────────────────────────────────


class TestBuildLitellmConfigEntries:

    def test_returns_non_empty_list(self):
        entries = build_litellm_config_entries()
        assert isinstance(entries, list)
        assert len(entries) > 0

    def test_entries_have_required_keys(self):
        entries = build_litellm_config_entries()
        for entry in entries:
            assert "model_name" in entry
            assert "litellm_params" in entry
            assert "model" in entry["litellm_params"]


# ── normalize_model_id ────────────────────────────────────────────────


class TestNormalizeModelId:

    def test_passthrough(self):
        assert normalize_model_id("qwen3-30b-a3b") == "qwen3-30b-a3b"

    def test_strips_provider_prefix(self):
        assert normalize_model_id("openai/gpt-4o") == "gpt-4o"

    def test_empty_string(self):
        assert normalize_model_id("") == ""


# ── validate_models ───────────────────────────────────────────────────


class TestValidateModels:

    def test_default_catalog_valid(self):
        errors = validate_models()
        assert errors == [], f"Validation errors: {errors}"


# ── reload_models ─────────────────────────────────────────────────────


class TestReloadModels:

    def test_reload_returns_catalog(self):
        catalog = reload_models()
        assert isinstance(catalog, dict)
        assert "models" in catalog
