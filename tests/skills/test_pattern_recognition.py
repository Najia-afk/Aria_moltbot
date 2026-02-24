"""
Tests for the pattern_recognition skill (Layer 3 — domain).

Covers:
- TopicExtractor: keyword, entity, category extraction
- FrequencyTracker: recurring and emerging topic detection
- PatternRecognizer: full analysis pipeline
- PatternRecognitionSkill: initialize, detect_patterns, stats
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.pattern_recognition import (
    TopicExtractor,
    FrequencyTracker,
    PatternRecognizer,
    MemoryItem,
    PatternType,
    PatternRecognitionSkill,
    TopicMention,
)


# ---------------------------------------------------------------------------
# TopicExtractor
# ---------------------------------------------------------------------------

def test_extract_keywords():
    extractor = TopicExtractor()
    mem = MemoryItem(
        id="m1", content="I need to debug the python function",
        category="general", timestamp=datetime.now(timezone.utc),
    )
    mentions = extractor.extract([mem])
    topics = {m.topic for m in mentions}
    assert "coding" in topics


def test_extract_category():
    extractor = TopicExtractor()
    mem = MemoryItem(
        id="m2", content="What is the status?",
        category="goal", timestamp=datetime.now(timezone.utc),
    )
    mentions = extractor.extract([mem])
    topics = {m.topic for m in mentions}
    assert "goals" in topics


def test_extract_entity():
    extractor = TopicExtractor()
    mem = MemoryItem(
        id="m3", content="PostgreSQL migration was successful",
        category="general", timestamp=datetime.now(timezone.utc),
    )
    mentions = extractor.extract([mem])
    topics = {m.topic for m in mentions}
    assert "postgresql" in topics


def test_noise_topics_filtered():
    extractor = TopicExtractor()
    mem = MemoryItem(
        id="m4", content="args kwargs self none true false return result",
        category="general", timestamp=datetime.now(timezone.utc),
    )
    mentions = extractor.extract([mem])
    topics = {m.topic for m in mentions}
    # None of the noise words should appear
    assert not topics.intersection(TopicExtractor.NOISE_TOPICS)


# ---------------------------------------------------------------------------
# FrequencyTracker
# ---------------------------------------------------------------------------

def test_frequency_tracker_recurring():
    tracker = FrequencyTracker(window_days=30)
    now = datetime.now(timezone.utc)
    mentions = [
        TopicMention(topic="security", timestamp=now - timedelta(days=i), memory_id=f"m{i}")
        for i in range(10)
    ]
    tracker.add_mentions(mentions)

    recurring = tracker.find_recurring(["security"], min_frequency=0.1, min_mentions=3)
    assert len(recurring) == 1
    assert recurring[0]["topic"] == "security"


def test_frequency_tracker_emerging():
    tracker = FrequencyTracker(window_days=30)
    now = datetime.now(timezone.utc)

    # Old mentions (sparse)
    old = [TopicMention(topic="ai_ml", timestamp=now - timedelta(days=20), memory_id="o1")]
    # Recent burst
    recent = [
        TopicMention(topic="ai_ml", timestamp=now - timedelta(hours=i), memory_id=f"r{i}")
        for i in range(5)
    ]
    tracker.add_mentions(old + recent)

    emerging = tracker.find_emerging(min_growth_rate=2.0, min_recent_mentions=3)
    assert any(e["topic"] == "ai_ml" for e in emerging)


# ---------------------------------------------------------------------------
# PatternRecognizer (full pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_insufficient_data():
    recognizer = PatternRecognizer(window_days=7)
    mems = [
        MemoryItem(id=f"m{i}", content="short", category="general",
                   timestamp=datetime.now(timezone.utc))
        for i in range(5)
    ]
    result = await recognizer.analyze(mems)
    assert result.patterns_found == []
    assert result.total_memories_analyzed == 5


@pytest.mark.asyncio
async def test_analyze_with_enough_data():
    recognizer = PatternRecognizer(window_days=7)
    now = datetime.now(timezone.utc)
    mems = [
        MemoryItem(
            id=f"m{i}",
            content="We need to fix the security vulnerability in the API",
            category="security" if i % 2 == 0 else "general",
            timestamp=now - timedelta(hours=i),
        )
        for i in range(20)
    ]
    result = await recognizer.analyze(mems, min_confidence=0.1)
    assert result.total_memories_analyzed == 20
    # Should detect some patterns from repeated security mentions
    assert isinstance(result.patterns_found, list)


# ---------------------------------------------------------------------------
# PatternRecognitionSkill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_initialize(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = PatternRecognitionSkill(SkillConfig(name="pattern_recognition"))
        ok = await skill.initialize()
        assert ok is True
        assert skill._status == SkillStatus.AVAILABLE
        assert skill._recognizer is not None


@pytest.mark.asyncio
async def test_skill_health_check():
    skill = PatternRecognitionSkill(SkillConfig(name="pattern_recognition"))
    skill._recognizer = None
    status = await skill.health_check()
    assert status == SkillStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_skill_get_pattern_stats_no_data():
    skill = PatternRecognitionSkill(SkillConfig(name="pattern_recognition"))
    skill._recognizer = PatternRecognizer()
    skill._last_result = None
    result = await skill.get_pattern_stats()
    assert result.success
    assert result.data["has_data"] is False


@pytest.mark.asyncio
async def test_skill_detect_patterns_no_memories(mock_api_client):
    mock_api_client.list_semantic_memories = AsyncMock(return_value=SkillResult.fail("empty"))
    mock_api_client.get_activities = AsyncMock(return_value=SkillResult.fail("empty"))
    mock_api_client.get_thoughts = AsyncMock(return_value=SkillResult.fail("empty"))

    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = PatternRecognitionSkill(SkillConfig(name="pattern_recognition"))
        await skill.initialize()
        result = await skill.detect_patterns(memories=[])
    assert not result.success
