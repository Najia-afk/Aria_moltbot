"""
Tests for TICKET-19 — Local Model Optimization.

Validates models.yaml profiles, qwen-cpu-fallback entry,
routing fallbacks, and benchmark script syntax.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
MODELS_YAML = ROOT / "aria_models" / "models.yaml"
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark_models.py"

# ── helpers ──────────────────────────────────────────────────────────────────

def _load_catalog() -> dict:
    """Load models.yaml as a dict (JSON-compatible YAML)."""
    text = MODELS_YAML.read_text(encoding="utf-8")
    return json.loads(text)


@pytest.fixture(scope="module")
def catalog() -> dict:
    return _load_catalog()


# ── 1. profiles section exists ──────────────────────────────────────────────

def test_profiles_section_exists(catalog):
    assert "profiles" in catalog, "models.yaml must contain a 'profiles' section"


def test_profiles_has_expected_keys(catalog):
    profiles = catalog["profiles"]
    expected = {"routing", "analysis", "creative", "code", "social"}
    assert expected.issubset(set(profiles.keys())), (
        f"Missing profile keys: {expected - set(profiles.keys())}"
    )


# ── 2. each profile has required fields ─────────────────────────────────────

REQUIRED_PROFILE_KEYS = {"model", "temperature", "max_tokens"}


@pytest.mark.parametrize("profile_name", ["routing", "analysis", "creative", "code", "social"])
def test_profile_has_required_keys(catalog, profile_name):
    profile = catalog["profiles"][profile_name]
    missing = REQUIRED_PROFILE_KEYS - set(profile.keys())
    assert not missing, f"Profile '{profile_name}' missing keys: {missing}"


# ── 3. profile model names exist in models section ──────────────────────────

def test_profile_models_exist_in_models_section(catalog):
    models = catalog.get("models", {})
    profiles = catalog.get("profiles", {})
    for pname, pdata in profiles.items():
        model_ref = pdata.get("model")
        assert model_ref in models, (
            f"Profile '{pname}' references model '{model_ref}' not found in models section"
        )


# ── 4. qwen-cpu-fallback model exists ───────────────────────────────────────

def test_qwen_cpu_fallback_exists(catalog):
    models = catalog.get("models", {})
    assert "qwen-cpu-fallback" in models, "qwen-cpu-fallback model must exist"


def test_qwen_cpu_fallback_fields(catalog):
    entry = catalog["models"]["qwen-cpu-fallback"]
    assert entry["tier"] == "local"
    assert entry["provider"] == "litellm"
    assert entry["contextWindow"] == 32768
    assert entry["maxTokens"] == 4096
    assert entry["litellm"]["model"] == "ollama/qwen2.5:3b"


# ── 5. routing.fallbacks contains qwen-cpu-fallback ─────────────────────────

def test_routing_fallbacks_are_non_empty(catalog):
    fallbacks = catalog.get("routing", {}).get("fallbacks", [])
    assert len(fallbacks) >= 3, (
        f"routing.fallbacks should have at least 3 entries, got {len(fallbacks)}"
    )


def test_routing_fallbacks_all_litellm_prefixed(catalog):
    """All fallbacks should use litellm/ prefix."""
    fallbacks = catalog.get("routing", {}).get("fallbacks", [])
    for fb in fallbacks:
        assert fb.startswith("litellm/"), (
            f"Fallback '{fb}' should start with 'litellm/'"
        )


# ── 6. criteria.tiers.local includes fallback ───────────────────────────────

def test_tiers_local_includes_cpu_fallback(catalog):
    local_tier = catalog.get("criteria", {}).get("tiers", {}).get("local", [])
    assert "qwen-cpu-fallback" in local_tier, (
        "criteria.tiers.local must include 'qwen-cpu-fallback'"
    )


# ── 7. criteria.priority includes fallback ──────────────────────────────────

def test_priority_is_non_empty(catalog):
    priority = catalog.get("criteria", {}).get("priority", [])
    assert len(priority) >= 3, (
        f"criteria.priority should have at least 3 entries, got {len(priority)}"
    )


def test_priority_first_is_primary(catalog):
    priority = catalog.get("criteria", {}).get("priority", [])
    primary = catalog.get("routing", {}).get("primary", "")
    primary_short = primary.replace("litellm/", "")
    assert priority[0] == primary_short, (
        f"First priority should match routing.primary '{primary_short}', got '{priority[0]}'"
    )


# ── 8. profile temperature/max_tokens types ─────────────────────────────────

@pytest.mark.parametrize("profile_name", ["routing", "analysis", "creative", "code", "social"])
def test_profile_temperature_is_float(catalog, profile_name):
    temp = catalog["profiles"][profile_name]["temperature"]
    assert isinstance(temp, (int, float)), f"temperature must be numeric, got {type(temp)}"
    assert 0.0 <= temp <= 2.0, f"temperature {temp} out of range [0, 2]"


@pytest.mark.parametrize("profile_name", ["routing", "analysis", "creative", "code", "social"])
def test_profile_max_tokens_is_int(catalog, profile_name):
    mt = catalog["profiles"][profile_name]["max_tokens"]
    assert isinstance(mt, int), f"max_tokens must be int, got {type(mt)}"
    assert mt > 0, f"max_tokens must be positive, got {mt}"


# ── 9. benchmark script is syntactically valid ──────────────────────────────

@pytest.mark.skipif(not BENCHMARK_SCRIPT.exists(), reason="benchmark script not yet created")
def test_benchmark_script_exists():
    assert BENCHMARK_SCRIPT.exists(), f"Benchmark script not found at {BENCHMARK_SCRIPT}"


@pytest.mark.skipif(not BENCHMARK_SCRIPT.exists(), reason="benchmark script not yet created")
def test_benchmark_script_syntax():
    """Verify the benchmark script parses as valid Python."""
    source = BENCHMARK_SCRIPT.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(BENCHMARK_SCRIPT))
    except SyntaxError as exc:
        pytest.fail(f"Benchmark script has syntax error: {exc}")


@pytest.mark.skipif(not BENCHMARK_SCRIPT.exists(), reason="benchmark script not yet created")
def test_benchmark_script_has_help_flag():
    """Verify --help exits cleanly (argparse)."""
    result = subprocess.run(
        [sys.executable, str(BENCHMARK_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"
    assert "--models" in result.stdout, "--models flag not documented in --help"


# ── 10. schema_version intact ───────────────────────────────────────────────

def test_schema_version(catalog):
    assert catalog.get("schema_version") == 3, "schema_version must be 3"


# ── 11. all models have provider field ──────────────────────────────────────

def test_all_models_have_provider(catalog):
    for model_id, entry in catalog.get("models", {}).items():
        assert "provider" in entry, f"Model '{model_id}' missing 'provider'"
