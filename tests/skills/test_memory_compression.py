"""
Tests for the memory_compression skill (Layer 3 — domain).

Covers:
- ImportanceScorer scoring logic
- MemoryCompressor rule-based summarization
- CompressionManager tiered processing
- MemoryCompressionSkill lifecycle
- compress_memories tool
- get_compression_stats tool
- Edge cases (few memories, no API)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.memory_compression import (
    ImportanceScorer,
    MemoryEntry,
    MemoryCompressor,
    CompressionManager,
    MemoryCompressionSkill,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _make_entry(content="Test memory", category="general", hours_ago=0, importance=0.5):
    return MemoryEntry(
        id=f"mem-{hours_ago}",
        content=content,
        category=category,
        timestamp=_now() - timedelta(hours=hours_ago),
        importance_score=importance,
    )


def _make_entries(n=30, category="general"):
    return [_make_entry(f"Memory entry {i}", category, hours_ago=i, importance=0.5) for i in range(n)]


# ---------------------------------------------------------------------------
# Tests — ImportanceScorer
# ---------------------------------------------------------------------------

class TestImportanceScorer:
    def test_recent_high_importance(self):
        scorer = ImportanceScorer()
        entry = _make_entry(content="Important decision", category="decision", hours_ago=0, importance=0.9)
        score = scorer.score(entry)
        assert 0.5 < score <= 1.0

    def test_old_low_importance(self):
        scorer = ImportanceScorer()
        entry = _make_entry(content="Old note", category="general", hours_ago=100, importance=0.2)
        score = scorer.score(entry)
        assert 0.0 < score < 0.5

    def test_category_weighting(self):
        scorer = ImportanceScorer()
        cmd = _make_entry(content="x", category="user_command", hours_ago=1, importance=0.5)
        sys_ = _make_entry(content="x", category="system", hours_ago=1, importance=0.5)
        assert scorer.score(cmd) > scorer.score(sys_)

    def test_score_bounds(self):
        scorer = ImportanceScorer()
        for cat in ["user_command", "goal", "system", "general", "unknown_cat"]:
            entry = _make_entry(category=cat, hours_ago=0)
            score = scorer.score(entry)
            assert 0.0 <= score <= 1.0

    def test_short_content_penalty(self):
        scorer = ImportanceScorer()
        short = _make_entry(content="Hi", category="general")
        normal = _make_entry(content="A moderately sized memory entry about something important", category="general")
        assert scorer.score(normal) >= scorer.score(short)


# ---------------------------------------------------------------------------
# Tests — MemoryCompressor (rule-based)
# ---------------------------------------------------------------------------

class TestMemoryCompressor:
    def test_rule_based_summary(self):
        compressor = MemoryCompressor(api_client=None)
        result = compressor._rule_based_summary(
            ["Deployed v2.0 to production. Updated docs.", "Fixed login bug. Added tests."],
            ["episodic", "episodic"],
        )
        assert "text" in result
        assert "entities" in result
        assert "facts" in result
        assert "2 episodic events" in result["text"]

    def test_rule_based_summary_extracts_entities(self):
        compressor = MemoryCompressor(api_client=None)
        result = compressor._rule_based_summary(
            ["Aria deployed FastAPI service to Docker. Bob reviewed."],
            ["general"],
        )
        # Title-case words should be extracted
        assert any(e in result["entities"] for e in ["Aria", "FastAPI", "Docker", "Bob"])

    @pytest.mark.asyncio
    async def test_compress_tier_empty(self):
        compressor = MemoryCompressor(api_client=None)
        result = await compressor.compress_tier([], "recent", 10)
        assert result == []

    @pytest.mark.asyncio
    async def test_compress_tier_produces_summaries(self):
        compressor = MemoryCompressor(api_client=None)
        entries = _make_entries(10)
        result = await compressor.compress_tier(entries, "recent", 5)
        assert len(result) >= 1
        assert result[0].tier == "recent"
        assert result[0].original_count > 0


# ---------------------------------------------------------------------------
# Tests — CompressionManager
# ---------------------------------------------------------------------------

class TestCompressionManager:
    @pytest.mark.asyncio
    async def test_process_few_memories(self):
        compressor = MemoryCompressor(api_client=None)
        manager = CompressionManager(compressor)
        entries = _make_entries(5)
        result = await manager.process_all(entries)
        assert result.success
        assert result.compression_ratio == 1.0  # No compression needed

    @pytest.mark.asyncio
    async def test_process_many_memories(self):
        compressor = MemoryCompressor(raw_limit=5, recent_limit=10, api_client=None)
        manager = CompressionManager(compressor)
        entries = _make_entries(30)
        result = await manager.process_all(entries)
        assert result.success
        assert result.memories_processed == 30
        assert result.compressed_count > 0

    @pytest.mark.asyncio
    async def test_get_active_context(self):
        compressor = MemoryCompressor(raw_limit=5, recent_limit=10, api_client=None)
        manager = CompressionManager(compressor)
        entries = _make_entries(25)
        await manager.process_all(entries)
        ctx = manager.get_active_context(entries[:5])
        assert "context" in ctx
        assert "tokens_estimate" in ctx
        assert "tiers" in ctx


# ---------------------------------------------------------------------------
# Tests — MemoryCompressionSkill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_initialize():
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=AsyncMock()):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression"))
        ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_skill_initialize_no_api():
    with patch("aria_skills.api_client.get_api_client", side_effect=Exception("no api")):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression"))
        ok = await skill.initialize()
    assert ok is True  # Works standalone without API


@pytest.mark.asyncio
async def test_compress_memories_too_few():
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=AsyncMock()):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression"))
        await skill.initialize()
    result = await skill.compress_memories(memories=[{"content": "x"}])
    assert result.success
    assert result.data["compressed"] is False


@pytest.mark.asyncio
async def test_compress_memories_batch():
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=AsyncMock()):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression", config={
            "raw_limit": 3, "recent_limit": 5,
        }))
        await skill.initialize()

    memories = [
        {"id": str(i), "content": f"Memory about topic {i}", "category": "episodic",
         "timestamp": (_now() - timedelta(hours=i)).isoformat(), "importance": 0.5}
        for i in range(15)
    ]
    result = await skill.compress_memories(memories=memories, store_semantic=False)
    assert result.success
    assert result.data["compressed"] is True
    assert result.data["memories_processed"] == 15


@pytest.mark.asyncio
async def test_get_compression_stats_no_data():
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=AsyncMock()):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression"))
        await skill.initialize()
    result = await skill.get_compression_stats()
    assert result.success
    assert result.data["has_data"] is False


@pytest.mark.asyncio
async def test_get_compression_stats_after_run():
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=AsyncMock()):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression", config={
            "raw_limit": 3, "recent_limit": 5,
        }))
        await skill.initialize()

    memories = [
        {"id": str(i), "content": f"Entry {i}", "category": "general",
         "timestamp": (_now() - timedelta(hours=i)).isoformat()}
        for i in range(15)
    ]
    await skill.compress_memories(memories=memories, store_semantic=False)
    result = await skill.get_compression_stats()
    assert result.success
    assert result.data["has_data"] is True
    assert result.data["memories_processed"] == 15


@pytest.mark.asyncio
async def test_skill_close():
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=AsyncMock()):
        skill = MemoryCompressionSkill(SkillConfig(name="memory_compression"))
        await skill.initialize()
    await skill.close()
    assert skill._compressor is None
    assert skill._status == SkillStatus.UNAVAILABLE
