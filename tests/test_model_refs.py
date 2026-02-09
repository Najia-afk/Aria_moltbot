"""Tests for stale model reference cleanup (TICKET-10)."""
import pytest
from pathlib import Path


def test_cognition_no_stale_model_skills():
    """Ensure cognition.py doesn't reference removed skill names."""
    src = Path("aria_mind/cognition.py").read_text(encoding="utf-8")
    assert 'get("ollama")' not in src, "cognition.py still references ollama skill"
    assert 'get("moonshot")' not in src, "cognition.py still references moonshot skill"


def test_startup_no_moonshot():
    """Ensure startup.py doesn't hardcode moonshot in skill list."""
    src = Path("aria_mind/startup.py").read_text(encoding="utf-8")
    assert '"moonshot"' not in src, "startup.py still hardcodes moonshot"


def test_models_yaml_exists():
    """Ensure canonical models.yaml exists."""
    assert Path("aria_models/models.yaml").exists(), "models.yaml missing"
