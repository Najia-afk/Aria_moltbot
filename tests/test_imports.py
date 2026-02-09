#!/usr/bin/env python3
"""Test that all core modules can be imported."""
import pytest

pytestmark = pytest.mark.unit


def test_import_security():
    """Test aria_mind.security imports."""
    from aria_mind.security import AriaSecurityGateway, PromptGuard, InputSanitizer, RateLimiter
    assert AriaSecurityGateway is not None
    assert PromptGuard is not None
    assert InputSanitizer is not None
    assert RateLimiter is not None


def test_import_soul():
    """Test aria_mind.soul imports."""
    from aria_mind.soul import Soul, FocusManager
    assert Soul is not None
    assert FocusManager is not None


def test_import_cognition():
    """Test aria_mind.cognition imports."""
    from aria_mind.cognition import Cognition
    assert Cognition is not None


def test_import_memory():
    """Test aria_mind.memory imports."""
    from aria_mind.memory import MemoryManager
    assert MemoryManager is not None


def test_import_heartbeat():
    """Test aria_mind.heartbeat imports."""
    from aria_mind.heartbeat import Heartbeat
    assert Heartbeat is not None


def test_import_aria_agents():
    """Test aria_agents imports."""
    from aria_agents.coordinator import AgentCoordinator
    from aria_agents.base import BaseAgent, AgentRole
    assert AgentCoordinator is not None
    assert BaseAgent is not None
    assert AgentRole is not None


def test_import_aria_skills():
    """Test aria_skills imports."""
    from aria_skills import SkillRegistry
    from aria_skills.database import DatabaseSkill
    assert SkillRegistry is not None
    assert DatabaseSkill is not None


def test_import_aria_models():
    """Test aria_models imports."""
    from aria_models.loader import get_route_skill, normalize_model_id
    assert get_route_skill is not None
    assert normalize_model_id is not None
