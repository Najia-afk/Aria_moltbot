from __future__ import annotations

from aria_models.loader import load_catalog, normalize_temperature


def test_normalize_temperature_for_kimi_forces_one():
    assert normalize_temperature("kimi", 0.3) == 1.0


def test_normalize_temperature_for_non_moonshot_model_preserves_value():
    assert normalize_temperature("qwen3.5_mlx", 0.3) == 0.3


def test_mlx_is_reserved_for_sentiment_routing():
    catalog = load_catalog()
    mlx = catalog["models"]["qwen3.5_mlx"]

    assert catalog["routing"]["primary"] == "litellm/trinity"
    assert catalog["tasks"]["sentiment"] == "qwen3.5_mlx"
    assert catalog["profiles"]["sentiment"]["model"] == "qwen3.5_mlx"
    assert "litellm/qwen3.5_mlx" not in catalog["routing"]["fallbacks"]
    assert set(mlx["profiles"]) == {"sentiment"}
    assert all(
        "qwen3.5_mlx" not in models
        for models in catalog["criteria"]["use_cases"].values()
    )


def test_general_routing_uses_free_models_only():
    catalog = load_catalog()
    models = catalog["models"]

    assert models["trinity"]["litellm"]["model"] == "openrouter/openrouter/free"
    assert models["trinity_backup"]["litellm"]["model"] == "openrouter/qwen/qwen3.8-27b:free"
    assert catalog["tasks"]["primary"] == "trinity"
    assert catalog["tasks"]["conversation_summary"] == "trinity"
    assert "data" in models["trinity"]["focus_for"]
    assert "trader" in models["trinity"]["focus_for"]
    assert "fallback_order" not in models["kimi"]
    assert catalog["tasks"]["moonshot_default"] == "kimi"
    assert all(
        models[model_id.split("/", 1)[1]]["tier"] == "free"
        for model_id in catalog["routing"].get("fallbacks", [])
    )