"""Tests for @logged_method activity logging decorator (TICKET-11)."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aria_skills.base import SkillConfig, SkillResult, BaseSkill, logged_method


class DummySkill(BaseSkill):
    """Test skill for decorator testing."""
    
    @property
    def name(self) -> str:
        return "test_skill"
    
    async def initialize(self) -> bool:
        return True
    
    async def health_check(self):
        from aria_skills.base import SkillStatus
        return SkillStatus.AVAILABLE
    
    @logged_method()
    async def do_something(self, value: str) -> SkillResult:
        return SkillResult.ok({"value": value})
    
    @logged_method("custom.action")
    async def do_custom(self) -> SkillResult:
        return SkillResult.ok("custom")
    
    @logged_method()
    async def do_fail(self) -> SkillResult:
        raise ValueError("test error")


class ApiClientDummy(BaseSkill):
    """Dummy api_client to test recursion guard."""
    
    @property
    def name(self) -> str:
        return "api_client"
    
    async def initialize(self) -> bool:
        return True
    
    async def health_check(self):
        from aria_skills.base import SkillStatus
        return SkillStatus.AVAILABLE
    
    @logged_method()
    async def create_activity(self, **kwargs) -> SkillResult:
        return SkillResult.ok("logged")


@pytest.fixture
def skill():
    config = SkillConfig(name="test_skill")
    return DummySkill(config)


@pytest.fixture
def api_skill():
    config = SkillConfig(name="api_client")
    return ApiClientDummy(config)


class TestLoggedMethod:
    
    @pytest.mark.asyncio
    async def test_success_returns_result(self, skill):
        result = await skill.do_something("hello")
        assert result.success
        assert result.data == {"value": "hello"}
    
    @pytest.mark.asyncio
    async def test_custom_action_name(self, skill):
        result = await skill.do_custom()
        assert result.success
    
    @pytest.mark.asyncio 
    async def test_failure_reraises(self, skill):
        with pytest.raises(ValueError, match="test error"):
            await skill.do_fail()
    
    @pytest.mark.asyncio
    async def test_recursion_guard(self, api_skill):
        """api_client methods should NOT trigger a logging POST."""
        import aria_skills.base as base_mod
        with patch.object(base_mod, '_post_activity', new_callable=AsyncMock) as mock_post:
            result = await api_skill.create_activity()
            assert result.success
            mock_post.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_logging_failure_doesnt_break_skill(self, skill):
        """If logging POST fails, the skill should still return normally."""
        import aria_skills.base as base_mod
        async def broken_post(*args, **kwargs):
            raise ConnectionError("API down")
        with patch.object(base_mod, '_post_activity', side_effect=broken_post):
            result = await skill.do_something("test")
            assert result.success
