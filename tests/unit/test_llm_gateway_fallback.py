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
