"""Tests for TICKET-15: Social platform protocol and decoupling."""
import asyncio
import pytest
from aria_skills.base import SkillConfig, SkillResult


# ── Protocol existence & runtime_checkable ────────────────────────

def test_social_platform_protocol_exists():
    """SocialPlatform protocol can be imported."""
    from aria_skills.social.platform import SocialPlatform
    assert SocialPlatform is not None


def test_social_platform_is_runtime_checkable():
    """SocialPlatform is decorated with @runtime_checkable."""
    from aria_skills.social.platform import SocialPlatform
    # runtime_checkable protocols have __protocol_attrs__
    assert hasattr(SocialPlatform, '__protocol_attrs__') or hasattr(SocialPlatform, '_is_runtime_protocol')


# ── MoltbookSkill protocol compliance ────────────────────────────

def test_moltbook_has_platform_name():
    """MoltbookSkill has platform_name class attribute."""
    from aria_skills.moltbook import MoltbookSkill
    assert hasattr(MoltbookSkill, 'platform_name')
    assert MoltbookSkill.platform_name == "moltbook"


def test_moltbook_has_post_method():
    """MoltbookSkill has post() protocol alias method."""
    from aria_skills.moltbook import MoltbookSkill
    assert hasattr(MoltbookSkill, 'post')
    assert callable(getattr(MoltbookSkill, 'post'))


def test_moltbook_has_get_posts_method():
    """MoltbookSkill has get_posts() protocol alias method."""
    from aria_skills.moltbook import MoltbookSkill
    assert hasattr(MoltbookSkill, 'get_posts')
    assert callable(getattr(MoltbookSkill, 'get_posts'))


def test_moltbook_has_delete_post_method():
    """MoltbookSkill has delete_post() method (pre-existing)."""
    from aria_skills.moltbook import MoltbookSkill
    assert hasattr(MoltbookSkill, 'delete_post')
    assert callable(getattr(MoltbookSkill, 'delete_post'))


def test_moltbook_has_health_check_method():
    """MoltbookSkill has health_check() method."""
    from aria_skills.moltbook import MoltbookSkill
    assert hasattr(MoltbookSkill, 'health_check')
    assert callable(getattr(MoltbookSkill, 'health_check'))


# ── SocialSkill platform registration and routing ────────────────

def test_social_skill_has_platforms_registry():
    """SocialSkill initializes with _platforms dict."""
    from aria_skills.social import SocialSkill
    config = SkillConfig(name="social")
    skill = SocialSkill(config)
    assert hasattr(skill, '_platforms')
    assert isinstance(skill._platforms, dict)


def test_social_skill_register_platform():
    """SocialSkill.register_platform() adds platform to registry."""
    from aria_skills.social import SocialSkill
    from aria_skills.social.telegram import TelegramPlatform

    config = SkillConfig(name="social")
    skill = SocialSkill(config)
    tg = TelegramPlatform()
    skill.register_platform("telegram", tg)
    assert "telegram" in skill._platforms
    assert skill._platforms["telegram"] is tg


@pytest.mark.asyncio
async def test_social_skill_routes_to_platform():
    """SocialSkill.create_post() routes to registered platform."""
    from aria_skills.social import SocialSkill
    from aria_skills.social.telegram import TelegramPlatform

    config = SkillConfig(name="social")
    skill = SocialSkill(config)
    tg = TelegramPlatform()
    skill.register_platform("telegram", tg)

    result = await skill.create_post(content="test", platform="telegram")
    # Telegram stub should return fail
    assert not result.success
    assert "TICKET-22" in result.error


@pytest.mark.asyncio
async def test_social_skill_fallback_without_platform():
    """SocialSkill.create_post() falls back to API when platform not registered."""
    from aria_skills.social import SocialSkill

    config = SkillConfig(name="social")
    skill = SocialSkill(config)
    # Don't initialize (no httpx client) — should still construct the post
    # and fallback to in-memory cache
    skill._client = None

    # Call with unregistered platform — should go to fallback path
    result = await skill.create_post(content="hello", platform="unknown_platform")
    # Fallback will try API (which is None), then cache locally
    assert result.success
    assert result.data["content"] == "hello"


# ── TelegramPlatform stub ────────────────────────────────────────

def test_telegram_platform_name():
    """TelegramPlatform has correct platform_name."""
    from aria_skills.social.telegram import TelegramPlatform
    tg = TelegramPlatform()
    assert tg.platform_name == "telegram"


@pytest.mark.asyncio
async def test_telegram_post_returns_fail():
    """TelegramPlatform.post() returns fail with TICKET-22 reference."""
    from aria_skills.social.telegram import TelegramPlatform
    tg = TelegramPlatform()
    result = await tg.post("test")
    assert not result.success
    assert "TICKET-22" in result.error


@pytest.mark.asyncio
async def test_telegram_get_posts_returns_fail():
    """TelegramPlatform.get_posts() returns fail."""
    from aria_skills.social.telegram import TelegramPlatform
    tg = TelegramPlatform()
    result = await tg.get_posts()
    assert not result.success
    assert "TICKET-22" in result.error


@pytest.mark.asyncio
async def test_telegram_delete_post_returns_fail():
    """TelegramPlatform.delete_post() returns fail."""
    from aria_skills.social.telegram import TelegramPlatform
    tg = TelegramPlatform()
    result = await tg.delete_post("123")
    assert not result.success
    assert "TICKET-22" in result.error


@pytest.mark.asyncio
async def test_telegram_health_check_returns_false():
    """TelegramPlatform.health_check() returns False."""
    from aria_skills.social.telegram import TelegramPlatform
    tg = TelegramPlatform()
    result = await tg.health_check()
    assert result is False


# ── Protocol isinstance checks ───────────────────────────────────

def test_telegram_isinstance_social_platform():
    """TelegramPlatform satisfies SocialPlatform protocol at runtime."""
    from aria_skills.social.platform import SocialPlatform
    from aria_skills.social.telegram import TelegramPlatform
    tg = TelegramPlatform()
    assert isinstance(tg, SocialPlatform)


# ── api_client default platform ──────────────────────────────────

def test_api_client_default_platform_not_moltbook():
    """api_client.create_social_post default platform is no longer 'moltbook'."""
    import inspect
    from aria_skills.api_client import AriaAPIClient
    sig = inspect.signature(AriaAPIClient.create_social_post)
    default = sig.parameters["platform"].default
    assert default != "moltbook", "Default platform should not be hardcoded to 'moltbook'"
    assert default == "unknown"
