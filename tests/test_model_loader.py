"""Tests for model centralization (aria_models.loader)."""
from aria_models.loader import list_all_model_ids, list_models_with_reasoning, build_litellm_config_entries


def test_list_all_model_ids():
    """list_all_model_ids returns a non-empty list of strings."""
    ids = list_all_model_ids()
    assert isinstance(ids, list)
    assert len(ids) > 0
    assert all(isinstance(i, str) for i in ids)


def test_list_models_with_reasoning():
    """list_models_with_reasoning returns a (possibly empty) list of strings."""
    reasoning = list_models_with_reasoning()
    assert isinstance(reasoning, list)
    assert all(isinstance(r, str) for r in reasoning)


def test_build_litellm_config_entries():
    """build_litellm_config_entries returns dicts with required keys."""
    entries = build_litellm_config_entries()
    assert isinstance(entries, list)
    assert len(entries) > 0
    for entry in entries:
        assert "model_name" in entry
        assert "litellm_params" in entry
        assert "model" in entry["litellm_params"]
