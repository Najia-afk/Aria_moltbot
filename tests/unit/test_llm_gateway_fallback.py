"""Tests for LLMGateway's fallback-chain retry behavior.

Regression coverage for a real bug: the per-candidate retry loop in
complete()/stream() used to only advance to the next fallback candidate
for "retriable" errors (timeout/rate-limit/network-ish messages). A
non-retriable error on the primary model -- e.g. an unresolvable model
name, an expired/invalid API key, or exhausted provider credits -- would
abort the whole request immediately even though untried fallback
candidates (trinity, trinity_backup) were still available. That defeats
the entire purpose of having a fallback chain, and is exactly the
scenario where a paid model (kimi) becoming unavailable should
transparently degrade to a free one instead of failing outright.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from aria_engine.config import EngineConfig
from aria_engine.llm_gateway import LLMGateway


def _fake_response(content: str = "ok") -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=None, reasoning_content=None)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    return SimpleNamespace(choices=[choice], usage=usage, _hidden_params={})


@pytest.mark.asyncio
async def test_complete_falls_through_on_non_retriable_error():
    gateway = LLMGateway(EngineConfig())

    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            # Not a timeout/rate-limit/network error -- e.g. an unresolvable
            # model name or an auth/billing failure from the provider.
            raise Exception("BadRequestError: model 'ghost-model' does not exist")
        return _fake_response("fallback worked")

    with patch("aria_engine.llm_gateway.acompletion", side_effect=fake_acompletion):
        response = await gateway.complete(
            messages=[{"role": "user", "content": "hi"}],
            model="ghost-model-not-in-catalog",
        )

    assert response.content == "fallback worked"
    assert len(calls) >= 2, "should have tried at least one fallback candidate"


@pytest.mark.asyncio
async def test_complete_raises_after_all_candidates_fail():
    gateway = LLMGateway(EngineConfig())

    async def always_fails(**kwargs):
        raise Exception("BadRequestError: nope")

    from aria_engine.exceptions import LLMError

    with patch("aria_engine.llm_gateway.acompletion", side_effect=always_fails):
        with pytest.raises(LLMError):
            await gateway.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="ghost-model-not-in-catalog",
            )


@pytest.mark.asyncio
async def test_complete_stops_retrying_on_openrouter_daily_free_quota(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_SPEND_CAP_USD", "3.0")
    gateway = LLMGateway(EngineConfig())
    calls = []

    async def quota_exhausted(**kwargs):
        calls.append(kwargs["model"])
        raise Exception(
            "RateLimitError: free-models-per-day-high-balance; "
            "limit_source=openrouter_free_tier_daily"
        )

    from aria_engine.exceptions import LLMError

    with patch("aria_engine.llm_gateway.acompletion", side_effect=quota_exhausted):
        with pytest.raises(LLMError, match="free-models-per-day"):
            await gateway.complete(
                messages=[{"role": "user", "content": "hi"}],
                model="trinity",
            )

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_stream_stops_retrying_on_openrouter_daily_free_quota(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_SPEND_CAP_USD", "3.0")
    gateway = LLMGateway(EngineConfig())
    calls = []

    async def quota_exhausted(**kwargs):
        calls.append(kwargs["model"])
        raise Exception(
            "RateLimitError: free-models-per-day-high-balance; "
            "limit_source=openrouter_free_tier_daily"
        )

    from aria_engine.exceptions import LLMError

    with patch("aria_engine.llm_gateway.acompletion", side_effect=quota_exhausted):
        with pytest.raises(LLMError, match="free-models-per-day"):
            async for _ in gateway.stream(
                messages=[{"role": "user", "content": "hi"}],
                model="trinity",
            ):
                pass

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_catalog_quota_policy_uses_six_hour_cooldown():
    gateway = LLMGateway(EngineConfig())
    calls = []

    async def quota_exhausted(**kwargs):
        calls.append(kwargs["model"])
        raise Exception(
            "RateLimitError: free-models-per-day-high-balance; "
            "limit_source=openrouter_free_tier_daily"
        )

    from aria_engine.exceptions import LLMError

    with patch("aria_engine.llm_gateway.acompletion", side_effect=quota_exhausted):
        with pytest.raises(LLMError, match="free-models-per-day"):
            await gateway.complete(
                messages=[{"role": "user", "content": "first"}],
                model="trinity",
            )

        with pytest.raises(LLMError, match="quota cooldown"):
            await gateway.complete(
                messages=[{"role": "user", "content": "second"}],
                model="trinity",
            )

    assert len(calls) == 1
    assert gateway._quota_cooldown_remaining("trinity") >= (6 * 60 * 60) - 2


# ---------------------------------------------------------------------------
# Daily spend cap for the paid (kimi) fallback candidate.
#
# kimi (Moonshot, paid) was added as a last-resort auto-fallback after
# trinity/trinity_backup both proved to be free OpenRouter models sharing one
# account-wide daily quota. This cap is the safety rail so a sustained
# failure loop can't run up unbounded real cost retrying a paid model.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_budget_filter_keeps_paid_fallback_under_cap(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_SPEND_CAP_USD", "3.0")
    gateway = LLMGateway(EngineConfig())
    gateway._get_today_spend_usd = AsyncMock(return_value=0.50)

    candidates = ["litellm/trinity", "litellm/trinity_backup", "litellm/kimi"]
    result = await gateway._filter_candidates_by_budget(candidates)

    assert result == candidates


@pytest.mark.asyncio
async def test_budget_filter_drops_paid_fallback_over_cap(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_SPEND_CAP_USD", "3.0")
    gateway = LLMGateway(EngineConfig())
    gateway._get_today_spend_usd = AsyncMock(return_value=5.00)

    candidates = ["litellm/trinity", "litellm/trinity_backup", "litellm/kimi"]
    result = await gateway._filter_candidates_by_budget(candidates)

    assert result == ["litellm/trinity", "litellm/trinity_backup"]


@pytest.mark.asyncio
async def test_budget_filter_never_drops_explicit_paid_primary(monkeypatch):
    """An explicitly requested paid primary model is always honored —
    only the automatic fallback tail is subject to the spend cap."""
    monkeypatch.setenv("LLM_DAILY_SPEND_CAP_USD", "3.0")
    gateway = LLMGateway(EngineConfig())
    gateway._get_today_spend_usd = AsyncMock(return_value=5.00)

    candidates = ["litellm/kimi", "litellm/trinity"]
    result = await gateway._filter_candidates_by_budget(candidates)

    assert result == candidates


@pytest.mark.asyncio
async def test_budget_filter_disabled_via_zero_cap(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_SPEND_CAP_USD", "0")
    gateway = LLMGateway(EngineConfig())
    gateway._get_today_spend_usd = AsyncMock(return_value=999.0)

    candidates = ["litellm/trinity", "litellm/kimi"]
    result = await gateway._filter_candidates_by_budget(candidates)

    assert result == candidates

