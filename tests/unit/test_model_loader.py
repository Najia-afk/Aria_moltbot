from __future__ import annotations

from aria_models.loader import _materialize_views, get_model_entry, normalize_temperature
from scripts.generate_litellm_config import generate_model_list


def test_normalize_temperature_for_kimi_forces_one():
    catalog = {
        "models": {
            "kimi": {"provider_label": "moonshot"},
        },
    }

    assert normalize_temperature("kimi", 0.3, catalog=catalog) == 1.0


def test_disabled_catalog_model_is_not_resolved():
    assert get_model_entry("kimi") is None


def test_normalize_temperature_for_non_moonshot_model_preserves_value():
    assert normalize_temperature("qwen3.5_mlx", 0.3) == 0.3


def test_disabled_models_are_excluded_from_all_derived_routes():
    catalog = {
        "models": {
            "nas": {
                "enabled": True,
                "tier": "local",
                "tasks": ["primary"],
                "fallback_order": 1,
                "priority": 1,
                "alias": "NAS",
                "tags": {"default": 1},
                "focus_for": ["orchestrator"],
                "profiles": {"routing": {"temperature": 0.2}},
            },
            "cloud": {
                "enabled": False,
                "tier": "paid",
                "tasks": ["primary", "summarization"],
                "fallback_order": 2,
                "priority": 2,
                "alias": "Cloud",
                "tags": {"default": 2},
                "focus_for": ["orchestrator"],
                "profiles": {"routing": {"temperature": 0.8}},
            },
        },
        "routing": {},
    }

    result = _materialize_views(catalog)

    assert result["tasks"] == {"primary": "nas", "primary_full": "litellm/nas"}
    assert result["routing"]["fallbacks"] == ["litellm/nas"]
    assert result["criteria"]["priority"] == ["nas"]
    assert result["criteria"]["tiers"] == {"local": ["nas"]}
    assert result["agent_aliases"] == {"litellm/nas": "NAS"}
    assert result["profiles"]["routing"]["model"] == "nas"
    assert get_model_entry("cloud", result) is None


def test_disabled_models_are_excluded_from_litellm_generation():
    catalog = {
        "models": {
            "nas": {
                "enabled": True,
                "litellm": {"model": "ollama_chat/aria-primary"},
            },
            "cloud": {
                "enabled": False,
                "litellm": {"model": "provider/cloud-model"},
            },
        },
    }

    assert [entry["model_name"] for entry in generate_model_list(catalog)] == ["nas"]