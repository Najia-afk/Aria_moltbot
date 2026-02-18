# tests/test_advanced_memory.py
"""
Tests for advanced memory subsystems.

Covers:
- Memory compression (ImportanceScorer, MemoryCompressor, CompressionManager)
- Sentiment analysis (SentimentLexicon, SentimentAnalyzer, ConversationAnalyzer, ResponseTuner)
- Pattern recognition (TopicExtractor, FrequencyTracker, PatternRecognizer)
- Unified search (RRFMerger, SearchResult)

All tests run offline (no DB, no LLM calls).
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import pytest


# ═══════════════════════════════════════════════════════════════════
# Memory Compression Tests
# ═══════════════════════════════════════════════════════════════════

class TestImportanceScorer:
    def test_score_range(self):
        from aria_skills.memory_compression import ImportanceScorer, MemoryEntry
        scorer = ImportanceScorer()
        mem = MemoryEntry(
            id="1", content="Hello world",
            category="general",
            timestamp=datetime.now(timezone.utc),
        )
        score = scorer.score(mem)
        assert 0.0 <= score <= 1.0

    def test_recent_memory_higher(self):
        from aria_skills.memory_compression import ImportanceScorer, MemoryEntry
        scorer = ImportanceScorer()
        now = datetime.now(timezone.utc)
        recent = MemoryEntry(id="1", content="Recent", category="general", timestamp=now)
        old = MemoryEntry(id="2", content="Old", category="general",
                          timestamp=now - timedelta(hours=24))
        assert scorer.score(recent, now) > scorer.score(old, now)

    def test_category_importance(self):
        from aria_skills.memory_compression import ImportanceScorer, MemoryEntry
        scorer = ImportanceScorer()
        now = datetime.now(timezone.utc)
        goal = MemoryEntry(id="1", content="Goal", category="goal", timestamp=now)
        system = MemoryEntry(id="2", content="Sys", category="system", timestamp=now)
        assert scorer.score(goal, now) > scorer.score(system, now)


class TestMemoryCompressor:
    @pytest.mark.asyncio
    async def test_rule_based_summary(self):
        from aria_skills.memory_compression import MemoryCompressor
        comp = MemoryCompressor()
        result = comp._rule_based_summary(
            ["Alice went home.", "Bob built a house."], ["general"])
        assert "text" in result
        assert "entities" in result
        assert len(result["text"]) > 0


class TestCompressionManager:
    @pytest.mark.asyncio
    async def test_small_set_passthrough(self):
        from aria_skills.memory_compression import (
            MemoryEntry, MemoryCompressor, CompressionManager)
        comp = MemoryCompressor()
        mgr = CompressionManager(comp)
        mems = [
            MemoryEntry(id=str(i), content=f"Mem {i}",
                        category="general",
                        timestamp=datetime.now(timezone.utc))
            for i in range(5)
        ]
        result = await mgr.process_all(mems)
        assert result.success
        assert result.compression_ratio == 1.0  # too small, no compression

    @pytest.mark.asyncio
    async def test_large_set_compresses(self):
        from aria_skills.memory_compression import (
            MemoryEntry, MemoryCompressor, CompressionManager)
        comp = MemoryCompressor(raw_limit=5, recent_limit=10)
        mgr = CompressionManager(comp)
        now = datetime.now(timezone.utc)
        mems = [
            MemoryEntry(id=str(i), content=f"Memory entry number {i} with some detail.",
                        category="general",
                        timestamp=now - timedelta(minutes=i * 10))
            for i in range(50)
        ]
        result = await mgr.process_all(mems)
        assert result.success
        assert result.memories_processed == 50
        assert result.compressed_count > 0
        assert "recent" in result.tiers_updated or "archive" in result.tiers_updated


# ═══════════════════════════════════════════════════════════════════
# Sentiment Analysis Tests
# ═══════════════════════════════════════════════════════════════════

class TestSentimentLexicon:
    def test_positive_text(self):
        from aria_skills.sentiment_analysis import SentimentLexicon
        v, a, d = SentimentLexicon.score("That was great and perfect!")
        assert v > 0

    def test_negative_text(self):
        from aria_skills.sentiment_analysis import SentimentLexicon
        v, a, d = SentimentLexicon.score("This is terrible and broken")
        assert v < 0

    def test_neutral_text(self):
        from aria_skills.sentiment_analysis import SentimentLexicon
        v, a, d = SentimentLexicon.score("The sky is blue today")
        assert abs(v) < 0.5

    def test_exclamation_arousal(self):
        from aria_skills.sentiment_analysis import SentimentLexicon
        _, a1, _ = SentimentLexicon.score("Hello")
        _, a2, _ = SentimentLexicon.score("Hello!!!")
        assert a2 >= a1


class TestSentiment:
    def test_frustration_positive_zero(self):
        from aria_skills.sentiment_analysis import Sentiment
        s = Sentiment(valence=0.5, arousal=0.8, dominance=0.5)
        assert s.frustration == 0.0

    def test_frustration_negative(self):
        from aria_skills.sentiment_analysis import Sentiment
        s = Sentiment(valence=-0.8, arousal=0.9, dominance=0.5)
        assert s.frustration > 0.5

    def test_satisfaction(self):
        from aria_skills.sentiment_analysis import Sentiment
        s = Sentiment(valence=0.8, arousal=0.5, dominance=0.9)
        assert s.satisfaction > 0.5

    def test_confusion(self):
        from aria_skills.sentiment_analysis import Sentiment
        s = Sentiment(valence=0.0, arousal=0.3, dominance=0.1)
        assert s.confusion > 0.2


class TestSentimentAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_positive(self):
        from aria_skills.sentiment_analysis import SentimentAnalyzer
        analyzer = SentimentAnalyzer()  # no LLM
        s = await analyzer.analyze("This is great and wonderful!")
        assert s.valence > 0

    @pytest.mark.asyncio
    async def test_analyze_negative(self):
        from aria_skills.sentiment_analysis import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        s = await analyzer.analyze("I hate this, it's terrible and broken")
        assert s.valence < 0


class TestConversationAnalyzer:
    @pytest.mark.asyncio
    async def test_trajectory(self):
        from aria_skills.sentiment_analysis import SentimentAnalyzer, ConversationAnalyzer
        analyzer = SentimentAnalyzer()
        conv = ConversationAnalyzer(analyzer)
        messages = [
            {"content": "This is terrible and awful"},
            {"content": "Still bad and broken"},
            {"content": "Actually, that was helpful"},
            {"content": "That was helpful, thanks!"},
            {"content": "Great, perfect solution!"},
            {"content": "Wonderful, excellent work!"},
        ]
        result = await conv.analyze_conversation(messages)
        assert result.messages_analyzed == 6
        assert result.trajectory.value in ("improving", "stable", "insufficient_data")


class TestResponseTuner:
    def test_neutral_tone(self):
        from aria_skills.sentiment_analysis import Sentiment, ResponseTuner
        tuner = ResponseTuner()
        s = Sentiment(valence=0.0, arousal=0.3, dominance=0.5)
        tone = tuner.select_tone(s)
        assert "selected_tone" in tone

    def test_frustration_tone(self):
        from aria_skills.sentiment_analysis import Sentiment, ResponseTuner
        tuner = ResponseTuner()
        s = Sentiment(valence=-0.8, arousal=0.9, dominance=0.3)
        tone = tuner.select_tone(s)
        assert tone["selected_tone"] == "empathetic_supportive"


# ═══════════════════════════════════════════════════════════════════
# Pattern Recognition Tests
# ═══════════════════════════════════════════════════════════════════

class TestTopicExtractor:
    def test_keyword_extraction(self):
        from aria_skills.pattern_recognition import TopicExtractor, MemoryItem
        ext = TopicExtractor()
        now = datetime.now(timezone.utc)
        items = [
            MemoryItem(id="1", content="I need to debug the Python API code",
                       category="general", timestamp=now),
        ]
        mentions = ext.extract(items)
        topics = [m.topic for m in mentions]
        assert "coding" in topics

    def test_entity_extraction(self):
        from aria_skills.pattern_recognition import TopicExtractor, MemoryItem
        ext = TopicExtractor()
        now = datetime.now(timezone.utc)
        items = [
            MemoryItem(id="1", content="PostgreSQL and FastAPI are running on Docker",
                       category="general", timestamp=now),
        ]
        mentions = ext.extract(items)
        topics = [m.topic.lower() for m in mentions]
        assert any("docker" in t or "fastapi" in t or "postgresql" in t for t in topics)


class TestFrequencyTracker:
    def test_recurring_detection(self):
        from aria_skills.pattern_recognition import FrequencyTracker, TopicMention
        tracker = FrequencyTracker(window_days=7)
        now = datetime.now(timezone.utc)
        mentions = [
            TopicMention(topic="coding", timestamp=now - timedelta(days=i),
                         memory_id=str(i))
            for i in range(5)
        ]
        tracker.add_mentions(mentions)
        recurring = tracker.find_recurring(["coding"], min_frequency=0.5)
        assert len(recurring) > 0
        assert recurring[0]["topic"] == "coding"


class TestPatternRecognizer:
    @pytest.mark.asyncio
    async def test_detect_patterns(self):
        from aria_skills.pattern_recognition import PatternRecognizer, MemoryItem
        recognizer = PatternRecognizer(window_days=30)
        now = datetime.now(timezone.utc)
        items = [
            MemoryItem(
                id=str(i),
                content=f"Working on Python API code for project {i}",
                category="technical",
                timestamp=now - timedelta(hours=i),
            )
            for i in range(20)
        ]
        result = await recognizer.analyze(items, min_confidence=0.1)
        assert result.total_memories_analyzed == 20
        # Should detect at least coding topic recurrence
        assert result.patterns_found


# ═══════════════════════════════════════════════════════════════════
# Unified Search Tests
# ═══════════════════════════════════════════════════════════════════

class TestRRFMerger:
    def test_merge_single_list(self):
        from aria_skills.unified_search import RRFMerger, SearchResult
        merger = RRFMerger(k=60)
        results = [
            SearchResult(content="Result A", score=0.9, source="semantic"),
            SearchResult(content="Result B", score=0.7, source="semantic"),
        ]
        merged = merger.merge({"semantic": results}, limit=5)
        assert len(merged) == 2
        assert merged[0].content == "Result A"

    def test_merge_overlapping(self):
        from aria_skills.unified_search import RRFMerger, SearchResult
        merger = RRFMerger(k=60)
        sem = [SearchResult(content="Shared result", score=0.9, source="semantic")]
        graph = [SearchResult(content="Shared result", score=0.8, source="graph")]
        # Single-backend RRF score for rank 1: weight / (k+1)
        single_score = 1.0 / (60 + 1)
        merged = merger.merge({"semantic": sem, "graph": graph}, limit=5)
        # Shared result appears once with combined RRF score from both backends
        assert len(merged) == 1
        assert merged[0].score > single_score  # combined > single backend

    def test_merge_diverse(self):
        from aria_skills.unified_search import RRFMerger, SearchResult
        merger = RRFMerger(k=60)
        sem = [SearchResult(content="Only semantic", score=0.9, source="semantic")]
        graph = [SearchResult(content="Only graph", score=0.8, source="graph")]
        merged = merger.merge({"semantic": sem, "graph": graph}, limit=5)
        assert len(merged) == 2

    def test_content_hash_dedup(self):
        from aria_skills.unified_search import SearchResult
        a = SearchResult(content="Hello world", score=0.5, source="a")
        b = SearchResult(content="Hello world", score=0.3, source="b")
        assert a.content_hash == b.content_hash

    def test_limit_respected(self):
        from aria_skills.unified_search import RRFMerger, SearchResult
        merger = RRFMerger(k=60)
        results = [
            SearchResult(content=f"R{i}", score=0.5, source="semantic")
            for i in range(50)
        ]
        merged = merger.merge({"semantic": results}, limit=10)
        assert len(merged) == 10


# ═══════════════════════════════════════════════════════════════════
# Skill Integration Tests (initialize + health_check)
# ═══════════════════════════════════════════════════════════════════

class TestSkillInitialization:
    @pytest.mark.asyncio
    async def test_memory_compression_init(self):
        from aria_skills.memory_compression import MemoryCompressionSkill
        skill = MemoryCompressionSkill()
        # Should init even without API client
        result = await skill.initialize()
        assert result is True
        status = await skill.health_check()
        assert status.value == "available"

    @pytest.mark.asyncio
    async def test_sentiment_analysis_init(self):
        from aria_skills.sentiment_analysis import SentimentAnalysisSkill, SkillConfig
        config = SkillConfig(name="sentiment_analysis", config={"use_llm": False})
        skill = SentimentAnalysisSkill(config)
        result = await skill.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_pattern_recognition_init(self):
        from aria_skills.pattern_recognition import PatternRecognitionSkill
        skill = PatternRecognitionSkill()
        result = await skill.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_compression_stats_empty(self):
        from aria_skills.memory_compression import MemoryCompressionSkill
        skill = MemoryCompressionSkill()
        await skill.initialize()
        result = await skill.get_compression_stats()
        assert result.success
        assert result.data["has_data"] is False

    @pytest.mark.asyncio
    async def test_sentiment_history_empty(self):
        from aria_skills.sentiment_analysis import SentimentAnalysisSkill, SkillConfig
        config = SkillConfig(name="sentiment_analysis", config={"use_llm": False})
        skill = SentimentAnalysisSkill(config)
        await skill.initialize()
        result = await skill.get_sentiment_history()
        assert result.success
        assert result.data["total_analyses_this_session"] == 0

    @pytest.mark.asyncio
    async def test_pattern_stats_empty(self):
        from aria_skills.pattern_recognition import PatternRecognitionSkill
        skill = PatternRecognitionSkill()
        await skill.initialize()
        result = await skill.get_pattern_stats()
        assert result.success
        assert result.data["has_data"] is False
