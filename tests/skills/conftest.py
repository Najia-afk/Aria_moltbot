"""
Skill-specific test fixtures (S-150).

These fixtures supplement the project-wide ``mock_api_client`` fixture
with helpers that wire up a skill instance ready for testing.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from aria_skills.base import SkillConfig


@pytest.fixture
def skill_config():
    """Factory fixture — returns a ``SkillConfig`` with sensible defaults.

    Usage::

        def test_my_skill(skill_config):
            cfg = skill_config("my_skill", config={"key": "value"})
    """
    def _factory(name: str = "test_skill", *, enabled: bool = True, config: dict | None = None):
        return SkillConfig(
            name=name,
            enabled=enabled,
            config=config or {},
        )
    return _factory


@pytest.fixture
def patch_get_api_client(mock_api_client):
    """Patch ``get_api_client`` so any skill that calls it receives the mock.

    Usage::

        async def test_goal_create(patch_get_api_client, mock_api_client):
            # GoalSchedulerSkill.initialize() will get mock_api_client
            skill = GoalSchedulerSkill(SkillConfig(name="goals"))
            await skill.initialize()
            ...
    """
    with patch(
        "aria_skills.api_client.get_api_client",
        new_callable=AsyncMock,
        return_value=mock_api_client,
    ) as patched:
        yield patched
