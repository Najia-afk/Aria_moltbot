"""
Tests for the sentiment_analysis skill (Layer 3 — domain).

Covers:
- SentimentLexicon scoring
- Sentiment derived metrics (frustration, satisfaction, confusion)
- SentimentAnalysisSkill: initialize, health_check
- analyze_message with mocked internals
- analyze_conversation with mocked internals
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.sentiment_analysis import (
    SentimentLexicon,
    Sentiment,
    SentimentAnalysisSkill,
    Trajectory,
)


# ---------------------------------------------------------------------------
# SentimentLexicon tests
# ---------------------------------------------------------------------------

def test_lexicon_positive():
    v, a, d = SentimentLexicon.score("This is great and amazing work!")
    assert v > 0  # Positive valence


def test_lexicon_negative():
    v, a, d = SentimentLexicon.score("This is terrible and broken")
    assert v < 0  # Negative valence


def test_lexicon_neutral():
    v, a, d = SentimentLexicon.score("The system processed the request")
    assert abs(v) < 0.5  # Relatively neutral


def test_lexicon_excited():
    v, a, d = SentimentLexicon.score("Wow incredible!! This is insane!!")
    assert a > 0  # High arousal


def test_lexicon_dominant():
    v, a, d = SentimentLexicon.score("You must fix this now, create a build")
    assert d > 0  # Some dominance signal


# ---------------------------------------------------------------------------
# Sentiment derived metrics
# ---------------------------------------------------------------------------

def test_frustration():
    s = Sentiment(valence=-0.8, arousal=0.9, dominance=0.5)
    assert s.frustration > 0.5


def test_frustration_zero_when_positive():
    s = Sentiment(valence=0.5, arousal=0.9, dominance=0.5)
    assert s.frustration == 0.0


def test_satisfaction():
    s = Sentiment(valence=0.8, arousal=0.3, dominance=0.9)
    assert s.satisfaction > 0.5


def test_satisfaction_zero_when_negative():
    s = Sentiment(valence=-0.5, arousal=0.3, dominance=0.9)
    assert s.satisfaction == 0.0


def test_confusion():
    s = Sentiment(valence=0.0, arousal=0.2, dominance=0.1)
    assert s.confusion > 0


def test_sentiment_to_dict():
    s = Sentiment(valence=0.5, arousal=0.3, dominance=0.7, primary_emotion="happy")
    d = s.to_dict()
    assert d["valence"] == 0.5
    assert d["primary_emotion"] == "happy"


# ---------------------------------------------------------------------------
# SentimentAnalysisSkill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_initialize(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SentimentAnalysisSkill(SkillConfig(
            name="sentiment_analysis",
            config={"use_llm": False, "use_embedding": False},
        ))
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_skill_health_check_not_initialized():
    skill = SentimentAnalysisSkill(SkillConfig(name="sentiment_analysis"))
    skill._analyzer = None
    status = await skill.health_check()
    assert status == SkillStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_analyze_message(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SentimentAnalysisSkill(SkillConfig(
            name="sentiment_analysis",
            config={"use_llm": False, "use_embedding": False},
        ))
        await skill.initialize()
        result = await skill.analyze_message(text="I love this project!")
    assert result.success
    assert "sentiment" in result.data
    assert result.data["sentiment"]["valence"] > 0


@pytest.mark.asyncio
async def test_analyze_message_empty():
    skill = SentimentAnalysisSkill(SkillConfig(
        name="sentiment_analysis",
        config={"use_llm": False, "use_embedding": False},
    ))
    skill._analyzer = MagicMock()
    skill._status = SkillStatus.AVAILABLE
    result = await skill.analyze_message(text="")
    assert not result.success


@pytest.mark.asyncio
async def test_analyze_message_negative(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SentimentAnalysisSkill(SkillConfig(
            name="sentiment_analysis",
            config={"use_llm": False, "use_embedding": False},
        ))
        await skill.initialize()
        result = await skill.analyze_message(text="This is terrible, I hate it", store=False)
    assert result.success
    assert result.data["sentiment"]["valence"] < 0


@pytest.mark.asyncio
async def test_analyze_conversation(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SentimentAnalysisSkill(SkillConfig(
            name="sentiment_analysis",
            config={"use_llm": False, "use_embedding": False},
        ))
        await skill.initialize()
        messages = [
            {"role": "user", "content": "This is frustrating!"},
            {"role": "assistant", "content": "I understand, let me help."},
            {"role": "user", "content": "Thanks, that fixed it perfectly!"},
        ]
        result = await skill.analyze_conversation(messages=messages, store=False)
    assert result.success
    assert "trajectory" in result.data
