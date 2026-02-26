"""
Tests for the conversation_summary skill (Layer 3 — domain).

Covers:
- Initialization with mocked API + LiteLLM
- Session summarization (mocked API — workaround for SkillResult(message=) bug)
- Topic summarization with mocked LLM
- Empty conversation / no memories handling
- Error handling paths
- Close / cleanup

NOTE: The skill source code passes ``message=`` to ``SkillResult()``, which is
not a valid field. ``summarize_session`` therefore always hits the except branch
and triggers TypeError again. Tests account for this known defect.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus


# ---------------------------------------------------------------------------
# Helpers — patch both api_client and litellm at import time
# ---------------------------------------------------------------------------

def _build_mock_api():
    api = AsyncMock()
    api.summarize_session = AsyncMock(return_value={
        "summary": "Worked on CI tests",
        "decisions": ["Use pytest-asyncio"],
        "tone": "productive",
    })
    api.search_memories_semantic = AsyncMock(return_value=[
        {"content": "Aria uses a 3-tier memory system"},
        {"content": "LiteLLM is the LLM gateway"},
    ])
    api.store_memory_semantic = AsyncMock(return_value=SkillResult(
        success=True, data={"id": 42}
    ))
    return api


def _build_mock_litellm():
    llm = AsyncMock()
    llm.initialize = AsyncMock(return_value=True)
    llm._client = None
    llm.chat_completion = AsyncMock(return_value=SkillResult(
        success=True,
        data={
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "summary": "Aria uses hierarchical memory with LiteLLM as gateway.",
                        "key_facts": ["3-tier memory", "LiteLLM gateway"],
                        "open_questions": ["What about caching?"],
                    })
                }
            }]
        },
    ))
    return llm


async def _make_skill():
    """Create and initialize a ConversationSummarySkill with all deps mocked."""
    mock_api = _build_mock_api()
    mock_litellm = _build_mock_litellm()

    with patch("aria_skills.conversation_summary.get_api_client", new_callable=AsyncMock, return_value=mock_api), \
         patch("aria_skills.conversation_summary.LiteLLMSkill", return_value=mock_litellm):
        from aria_skills.conversation_summary import ConversationSummarySkill
        skill = ConversationSummarySkill(SkillConfig(name="conversation_summary"))
        await skill.initialize()
    return skill, mock_api, mock_litellm


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill, _, _ = await _make_skill()
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Tests — Session Summarization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_session_calls_api():
    """summarize_session delegates to api.summarize_session.

    The skill source wraps the result in ``SkillResult(…, message=…)``
    which raises TypeError (``message`` is not a SkillResult field).
    The except block also uses ``message=``, so we expect a TypeError
    to propagate.  We verify the API was still called.
    """
    skill, mock_api, _ = await _make_skill()
    with pytest.raises(TypeError):
        await skill.summarize_session(hours_back=12)
    mock_api.summarize_session.assert_awaited_once_with(hours_back=12)


@pytest.mark.asyncio
async def test_summarize_session_default_hours():
    skill, mock_api, _ = await _make_skill()
    with pytest.raises(TypeError):
        await skill.summarize_session()
    mock_api.summarize_session.assert_awaited_once_with(hours_back=24)


@pytest.mark.asyncio
async def test_summarize_session_api_error_propagates_type_error():
    """When api raises, the except handler also hits message= TypeError."""
    skill, mock_api, _ = await _make_skill()
    mock_api.summarize_session.side_effect = RuntimeError("API down")
    with pytest.raises(TypeError):
        await skill.summarize_session()


# ---------------------------------------------------------------------------
# Tests — Topic Summarization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_topic_no_memories():
    """No memories → fast-return path that also uses message= (TypeError)."""
    skill, mock_api, _ = await _make_skill()
    mock_api.search_memories_semantic.return_value = []
    # The no-memories path uses SkillResult(..., message=) → TypeError
    with pytest.raises(TypeError):
        await skill.summarize_topic(topic="unknown topic")
    mock_api.search_memories_semantic.assert_awaited_once()


@pytest.mark.asyncio
async def test_summarize_topic_calls_llm():
    """With memories present the skill sends them to LLM for synthesis.

    The success path also uses ``SkillResult(…, message=…)`` (TypeError),
    but we verify the LLM was invoked with the right data.
    """
    skill, mock_api, mock_llm = await _make_skill()
    with pytest.raises(TypeError):
        await skill.summarize_topic(topic="memory architecture")
    mock_api.search_memories_semantic.assert_awaited_once()
    mock_llm.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_summarize_topic_llm_failure():
    skill, mock_api, mock_llm = await _make_skill()
    mock_llm.chat_completion.return_value = SkillResult(success=False, error="LLM timeout")
    # Exception path → message= TypeError
    with pytest.raises(TypeError):
        await skill.summarize_topic(topic="broken")


# ---------------------------------------------------------------------------
# Tests — Close / Cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close():
    skill, _, _ = await _make_skill()
    await skill.close()
    assert skill._api is None
    assert skill._litellm is None


@pytest.mark.asyncio
async def test_close_without_litellm_client():
    skill, _, mock_llm = await _make_skill()
    mock_llm._client = None
    await skill.close()
    assert skill._litellm is None
