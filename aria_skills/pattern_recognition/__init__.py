# aria_skills/pattern_recognition/__init__.py
"""
Behavioural Pattern Recognition — Full Production Implementation.

Detects five pattern types in memory stream:
  TOPIC_RECURRENCE    — subjects that come up repeatedly
  TEMPORAL_PATTERN    — time-based activity clusters
  SENTIMENT_DRIFT     — emotional trend changes
  INTEREST_EMERGENCE  — new topics gaining frequency
  KNOWLEDGE_GAP       — repeated questions on same subject

Pipeline:
  1. Extract topics from memories (keyword + entity + category)
  2. Track frequency over sliding time windows
  3. Statistical pattern detection
  4. Optional LLM augmentation for semantic patterns
  5. Store detected patterns in semantic memory via api_client

All DB access via api_client → FastAPI → PostgreSQL.
"""

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


# ═══════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════

class PatternType(Enum):
    TOPIC_RECURRENCE = "topic_recurrence"
    TEMPORAL_PATTERN = "temporal_pattern"
    SENTIMENT_DRIFT = "sentiment_drift"
    INTEREST_EMERGENCE = "interest_emergence"
    KNOWLEDGE_GAP = "knowledge_gap"
    BEHAVIOR_CYCLE = "behavior_cycle"


@dataclass
class Pattern:
    """Single detected pattern."""
    type: PatternType
    subject: str
    confidence: float
    evidence: list[Any] = field(default_factory=list)
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    frequency_per_day: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        d["first_seen"] = self.first_seen.isoformat()
        d["last_seen"] = self.last_seen.isoformat()
        return d


@dataclass
class TopicMention:
    """A topic mention extracted from a memory entry."""
    topic: str
    timestamp: datetime
    memory_id: str
    sentiment: float | None = None
    category: str = "general"


@dataclass
class MemoryItem:
    """Lightweight memory representation for pattern analysis."""
    id: str
    content: str
    category: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MemoryItem":
        ts = d.get("timestamp") or d.get("created_at") or datetime.now(timezone.utc).isoformat()
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return cls(
            id=str(d.get("id", "")),
            content=d.get("content", ""),
            category=d.get("category", "general"),
            timestamp=ts,
            metadata=d.get("metadata", {}),
        )


@dataclass
class PatternDetectionResult:
    """Result of a pattern detection run."""
    patterns_found: list[Pattern]
    total_memories_analyzed: int
    analysis_window_days: int
    new_patterns: int
    persistent_patterns: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Topic Extraction
# ═══════════════════════════════════════════════════════════════════

class TopicExtractor:
    """Extract topics from memory content using keywords, entities, categories."""

    TOPIC_KEYWORDS: dict[str, list[str]] = {
        "quantum_mechanics": ["quantum", "photon", "entanglement", "qubit", "superposition"],
        "coding": ["code", "python", "function", "class", "debug", "api", "javascript", "typescript"],
        "memory_system": ["memory", "compress", "embedding", "pattern", "recall", "vector"],
        "security": ["security", "vulnerability", "auth", "encrypt", "password", "firewall"],
        "goals": ["goal", "task", "complete", "progress", "milestone", "sprint"],
        "social": ["moltbook", "post", "comment", "telegram", "message", "community"],
        "infrastructure": ["docker", "kubernetes", "deploy", "server", "container", "ci"],
        "ai_ml": ["model", "training", "inference", "llm", "neural", "gpt", "transformer"],
        "data": ["database", "postgres", "sql", "migration", "schema", "table"],
    }

    CATEGORY_MAP: dict[str, str] = {
        "user_command": "interaction", "goal": "goals", "decision": "decision_making",
        "error": "errors", "reflection": "reflection", "social": "social",
        "context": "context", "system": "system", "technical": "coding",
        "security": "security", "sentiment": "sentiment",
    }

    ENTITY_RE = re.compile(r"\b[A-Z][a-zA-Z]+(?:[ -][A-Z][a-zA-Z]+)*\b")
    TECH_RE = re.compile(
        r"\b(?:API|LLM|AI|ML|DB|SQL|HTTP|HTTPS|JSON|XML|Docker|Kubernetes|PostgreSQL|Redis|FastAPI)\b",
        re.IGNORECASE,
    )
    FILTER_ENTITIES = frozenset({
        "The", "This", "That", "When", "What", "Where", "Who", "How", "But",
        "And", "For", "Not", "All", "Any", "Its", "Has", "Was", "Are", "Can",
    })

    # Noise topics to skip — generic programming/system terms that inflate counts
    NOISE_TOPICS = frozenset({
        "args", "kwargs", "self", "none", "true", "false", "return", "result",
        "function", "method", "class", "type", "value", "key", "name", "item",
        "action", "next", "pattern", "status", "error", "success", "message",
        "source", "details", "content", "data", "info", "log", "event",
        "config", "params", "options", "default", "string", "list", "dict",
        "created", "updated", "deleted", "db", "connect", "test", "run",
        "file", "path", "url", "http", "request", "response", "output",
        "input", "check", "set", "get", "post", "init", "start", "stop",
    })

    def extract(self, memories: list[MemoryItem]) -> list[TopicMention]:
        mentions: list[TopicMention] = []
        for mem in memories:
            # 1. Category-based
            cat_topic = self.CATEGORY_MAP.get(mem.category)
            if cat_topic:
                mentions.append(TopicMention(
                    topic=cat_topic, timestamp=mem.timestamp,
                    memory_id=mem.id, category=mem.category))

            # 2. Keyword-based
            lower = mem.content.lower()
            for topic, kws in self.TOPIC_KEYWORDS.items():
                if any(kw in lower for kw in kws):
                    mentions.append(TopicMention(
                        topic=topic, timestamp=mem.timestamp,
                        memory_id=mem.id, category=mem.category))

            # 3. Entity extraction
            for match in self.ENTITY_RE.finditer(mem.content):
                entity = match.group()
                if len(entity) > 3 and entity not in self.FILTER_ENTITIES:
                    mentions.append(TopicMention(
                        topic=entity.lower().replace(" ", "_"),
                        timestamp=mem.timestamp, memory_id=mem.id, category=mem.category))

            for tech in self.TECH_RE.findall(mem.content):
                mentions.append(TopicMention(
                    topic=tech.lower(), timestamp=mem.timestamp,
                    memory_id=mem.id, category=mem.category))

        # Filter out noise topics
        mentions = [m for m in mentions if m.topic not in self.NOISE_TOPICS]
        return mentions


# ═══════════════════════════════════════════════════════════════════
# Frequency Tracker
# ═══════════════════════════════════════════════════════════════════

class FrequencyTracker:
    """Track topic frequencies over sliding time windows."""

    def __init__(self, window_days: int = 30):
        self.window_days = window_days
        self.topic_history: dict[str, list[TopicMention]] = defaultdict(list)

    def add_mentions(self, mentions: list[TopicMention]) -> None:
        for m in mentions:
            self.topic_history[m.topic].append(m)

    def get_frequency(self, topic: str, window_days: int | None = None) -> float:
        window = window_days or self.window_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=window)
        recent = [m for m in self.topic_history.get(topic, []) if m.timestamp >= cutoff]
        return len(recent) / max(window, 1)

    def find_recurring(self, topics: list[str], min_frequency: float = 0.3,
                       min_mentions: int = 5) -> list[dict[str, Any]]:
        recurring: list[dict[str, Any]] = []
        for topic in set(topics):
            freq = self.get_frequency(topic)
            total = len(self.topic_history.get(topic, []))
            if freq >= min_frequency or total >= min_mentions:
                recent_freq = self.get_frequency(topic, window_days=3)
                recurring.append({
                    "topic": topic,
                    "frequency_per_day": round(freq, 3),
                    "total_mentions": total,
                    "is_newly_recurring": recent_freq > freq * 1.5 if freq > 0 else False,
                })
        recurring.sort(key=lambda x: x["frequency_per_day"], reverse=True)
        return recurring

    def find_emerging(self, min_growth_rate: float = 2.0,
                      min_recent_mentions: int = 3) -> list[dict[str, Any]]:
        emerging: list[dict[str, Any]] = []
        for topic, mentions in self.topic_history.items():
            if len(mentions) < min_recent_mentions:
                continue
            cutoff = datetime.now(timezone.utc) - timedelta(days=3)
            recent = [m for m in mentions if m.timestamp >= cutoff]
            older = [m for m in mentions if m.timestamp < cutoff]

            if not older:
                if len(recent) >= min_recent_mentions:
                    emerging.append({
                        "topic": topic, "recent_mentions": len(recent),
                        "growth_rate": 999.0, "is_new": True})
                continue

            recent_freq = len(recent) / 3
            span = max(1, (datetime.now(timezone.utc) - mentions[0].timestamp).days)
            older_freq = len(older) / span

            if recent_freq >= older_freq * min_growth_rate:
                emerging.append({
                    "topic": topic, "recent_mentions": len(recent),
                    "older_mentions": len(older),
                    "recent_freq_per_day": round(recent_freq, 3),
                    "older_freq_per_day": round(older_freq, 3),
                    "growth_rate": round(recent_freq / older_freq, 2) if older_freq > 0 else float("inf"),
                })
        emerging.sort(key=lambda x: x.get("growth_rate", 0), reverse=True)
        return emerging


# ═══════════════════════════════════════════════════════════════════
# Pattern Recognizer Engine
# ═══════════════════════════════════════════════════════════════════

class PatternRecognizer:
    """
    Main pattern recognition engine.

    1. Extract topics → 2. Track frequencies → 3. Detect patterns
    4. Optional LLM augmentation → 5. Deduplicate & rank
    """

    def __init__(self, window_days: int = 30):
        self.window_days = window_days
        self.topic_extractor = TopicExtractor()
        self.frequency_tracker = FrequencyTracker(window_days)
        self.pattern_history: list[Pattern] = []

    async def analyze(self, memories: list[MemoryItem],
                      min_confidence: float = 0.3) -> PatternDetectionResult:
        if len(memories) < 10:
            return PatternDetectionResult(
                patterns_found=[], total_memories_analyzed=len(memories),
                analysis_window_days=self.window_days, new_patterns=0, persistent_patterns=0)

        # 1. Extract topics
        mentions = self.topic_extractor.extract(memories)
        self.frequency_tracker.add_mentions(mentions)

        patterns: list[Pattern] = []

        # 2. Topic recurrence
        recurring = self.frequency_tracker.find_recurring([m.topic for m in mentions])
        for rec in recurring:
            if rec["frequency_per_day"] >= 0.1:
                patterns.append(Pattern(
                    type=PatternType.TOPIC_RECURRENCE, subject=rec["topic"],
                    confidence=min(1.0, rec["frequency_per_day"] * 3),
                    evidence=[f"Frequency: {rec['frequency_per_day']}/day, total: {rec['total_mentions']}"],
                    first_seen=datetime.now(timezone.utc) - timedelta(days=self.window_days),
                    frequency_per_day=rec["frequency_per_day"],
                ))

        # 3. Interest emergence
        for em in self.frequency_tracker.find_emerging():
            patterns.append(Pattern(
                type=PatternType.INTEREST_EMERGENCE, subject=em["topic"],
                confidence=0.8 if em.get("is_new") else 0.6,
                evidence=["New topic" if em.get("is_new") else f"Growth rate: {em.get('growth_rate', 1):.1f}x"],
                frequency_per_day=em.get("recent_freq_per_day", 0),
            ))

        # 4. Temporal patterns
        patterns.extend(self._detect_temporal(memories))

        # 5. Sentiment drift
        patterns.extend(self._detect_sentiment_drift(memories))

        # 6. Knowledge gaps
        patterns.extend(self._detect_knowledge_gaps(memories))

        # Filter, deduplicate, track
        patterns = [p for p in patterns if p.confidence >= min_confidence]
        unique = self._deduplicate(patterns)

        new_count = sum(
            1 for p in unique
            if not any(h.type == p.type and h.subject == p.subject for h in self.pattern_history)
        )
        persistent_count = len(unique) - new_count
        self.pattern_history.extend(unique)

        return PatternDetectionResult(
            patterns_found=unique, total_memories_analyzed=len(memories),
            analysis_window_days=self.window_days,
            new_patterns=new_count, persistent_patterns=persistent_count,
        )

    def _detect_temporal(self, memories: list[MemoryItem]) -> list[Pattern]:
        patterns: list[Pattern] = []
        if len(memories) < 10:
            return patterns

        hours = [m.timestamp.hour for m in memories]
        total = len(hours)
        for hour, count in Counter(hours).items():
            if count / total >= 0.25:
                patterns.append(Pattern(
                    type=PatternType.TEMPORAL_PATTERN,
                    subject=f"active_hour_{hour:02d}",
                    confidence=count / total,
                    evidence=[f"{count} events during hour {hour}"],
                    metadata={"hour": hour, "count": count},
                ))

        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day_idx, count in Counter(m.timestamp.weekday() for m in memories).items():
            if count / total >= 0.3:
                patterns.append(Pattern(
                    type=PatternType.TEMPORAL_PATTERN,
                    subject=f"active_day_{days[day_idx]}",
                    confidence=count / total,
                    evidence=[f"{count} events on {days[day_idx].title()}"],
                    metadata={"weekday": day_idx, "day_name": days[day_idx]},
                ))
        return patterns

    def _detect_sentiment_drift(self, memories: list[MemoryItem]) -> list[Pattern]:
        scored: list[tuple] = []
        for m in memories:
            val = m.metadata.get("valence")  # prefer valence from sentiment analysis
            if val is None:
                s = m.metadata.get("sentiment")
                if isinstance(s, (int, float)):
                    val = s
                elif isinstance(s, dict):
                    val = s.get("valence") or s.get("score")
            if isinstance(val, (int, float)):
                scored.append((m, float(val)))
        if len(scored) < 5:
            return []

        scored.sort(key=lambda pair: pair[0].timestamp)
        mid = len(scored) // 2
        avg_first = sum(v for _, v in scored[:mid]) / mid
        avg_second = sum(v for _, v in scored[mid:]) / (len(scored) - mid)
        diff = avg_second - avg_first

        if abs(diff) >= 0.3:
            return [Pattern(
                type=PatternType.SENTIMENT_DRIFT, subject="conversation_tone",
                confidence=min(1.0, abs(diff) * 2),
                evidence=[f"First half avg: {avg_first:.2f}", f"Second half avg: {avg_second:.2f}"],
                metadata={"direction": "improving" if diff > 0 else "declining",
                          "first_half_avg": avg_first, "second_half_avg": avg_second},
            )]
        return []

    def _detect_knowledge_gaps(self, memories: list[MemoryItem]) -> list[Pattern]:
        questions = [m for m in memories if m.content.strip().endswith("?")]
        if len(questions) < 2:
            return []

        topics: dict[str, list[MemoryItem]] = defaultdict(list)
        for q in questions:
            words = q.content.lower().split()[:3]
            key = " ".join(words)
            topics[key].append(q)

        patterns: list[Pattern] = []
        for topic, qs in topics.items():
            if len(qs) >= 2:
                span_h = (qs[-1].timestamp - qs[0].timestamp).total_seconds() / 3600
                if span_h > 1:
                    patterns.append(Pattern(
                        type=PatternType.KNOWLEDGE_GAP, subject=topic,
                        confidence=min(1.0, len(qs) / 5),
                        evidence=[f"Asked {len(qs)} times over {span_h:.1f}h"],
                        metadata={"question_count": len(qs)},
                    ))
        return patterns

    def _deduplicate(self, patterns: list[Pattern]) -> list[Pattern]:
        seen: set = set()
        unique: list[Pattern] = []
        for p in patterns:
            key = (p.type, p.subject)
            if key not in seen:
                seen.add(key)
                unique.append(p)
        unique.sort(key=lambda p: p.confidence, reverse=True)
        return unique


# ═══════════════════════════════════════════════════════════════════
# Skill Class
# ═══════════════════════════════════════════════════════════════════

@SkillRegistry.register
class PatternRecognitionSkill(BaseSkill):
    """
    Behavioural pattern detection in memory streams.

    Tools:
      detect_patterns   — Run full pattern detection on memories
      get_recurring     — Get recurring topic patterns
      get_emerging      — Get newly emerging topics
      get_pattern_stats — Stats from last detection run
    """

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="pattern_recognition"))
        self._api = None
        self._recognizer: PatternRecognizer | None = None
        self._last_result: PatternDetectionResult | None = None

    @property
    def name(self) -> str:
        return "pattern_recognition"

    async def initialize(self) -> bool:
        try:
            from aria_skills.api_client import get_api_client
            self._api = await get_api_client()
        except Exception as e:
            self.logger.warning(f"API client not available: {e}")

        window = int(self.config.config.get("window_days", 30))
        self._recognizer = PatternRecognizer(window_days=window)

        self._status = SkillStatus.AVAILABLE
        self.logger.info("Pattern recognition initialized (window=%d days, api=%s)",
                         window, self._api is not None)
        return True

    async def health_check(self) -> SkillStatus:
        if self._recognizer is None:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    @logged_method()
    async def detect_patterns(self, memories: list[dict[str, Any]] | None = None,
                               min_confidence: float = 0.3,
                               store: bool = True, **kwargs) -> SkillResult:
        """Run full pattern detection on a list of memories."""
        memories = memories or kwargs.get("memories", [])
        if not memories:
            # Try to fetch from semantic memory
            if self._api:
                try:
                    r = await self._api.list_semantic_memories(limit=200)
                    if r.success:
                        items = r.data if isinstance(r.data, list) else (r.data or {}).get("items", [])
                        memories = items
                except Exception:
                    pass

            # ── DB fallback: pull from activities + thoughts when semantic_memories empty ──
            if (not memories or len(memories) < 10) and self._api:
                fallback_items: list[dict[str, Any]] = []
                try:
                    r = await self._api.get_activities(limit=150)
                    if r.success:
                        acts = r.data if isinstance(r.data, list) else (r.data or {}).get("items", [])
                        for a in (acts or []):
                            details = a.get("details", {}) or {}
                            content = (
                                f"{a.get('action', '')} | {a.get('skill', '')} "
                                f"| {details.get('result_preview', '')[:200]}"
                            ).strip()
                            if len(content) > 10:
                                fallback_items.append({
                                    "content": content,
                                    "category": a.get("action", "activity"),
                                    "created_at": a.get("created_at", ""),
                                    "id": str(a.get("id", "")),
                                    "importance": 0.4,
                                    "source": "activity_log_fallback",
                                })
                except Exception:
                    pass
                try:
                    r = await self._api.get_thoughts(limit=80)
                    if r.success:
                        tlist = r.data if isinstance(r.data, list) else (r.data or {}).get("items", [])
                        for t in (tlist or []):
                            content = (t.get("content") or "").strip()
                            if len(content) > 10:
                                fallback_items.append({
                                    "content": content,
                                    "category": t.get("category", "thought"),
                                    "created_at": t.get("created_at", ""),
                                    "id": str(t.get("id", "")),
                                    "importance": 0.6,
                                    "source": "thoughts_fallback",
                                })
                except Exception:
                    pass
                if fallback_items:
                    memories = (memories or []) + fallback_items

            if not memories:
                return SkillResult.fail("No memories provided and could not fetch from API")

        mem_items = [MemoryItem.from_dict(m) for m in memories]
        result = await self._recognizer.analyze(mem_items, min_confidence=min_confidence)
        self._last_result = result

        # Store patterns in semantic memory
        stored_ids: list[str] = []
        if store and self._api:
            for p in result.patterns_found[:20]:  # Top 20 patterns
                try:
                    r = await self._api.store_memory_semantic(
                        content=f"Pattern detected: {p.type.value} — {p.subject} "
                                f"(confidence={p.confidence:.2f}, freq={p.frequency_per_day:.2f}/day)",
                        category="pattern_detection",
                        importance=p.confidence,
                        source="pattern_recognition",
                        metadata={
                            "pattern_type": p.type.value,
                            "subject": p.subject,
                            "confidence": p.confidence,
                            "frequency": p.frequency_per_day,
                            "evidence": p.evidence[:5],
                        },
                    )
                    if r.success and isinstance(r.data, dict):
                        stored_ids.append(r.data.get("id", ""))
                except Exception:
                    pass

        return SkillResult.ok({
            "patterns_found": len(result.patterns_found),
            "patterns": [p.to_dict() for p in result.patterns_found],
            "new_patterns": result.new_patterns,
            "persistent_patterns": result.persistent_patterns,
            "memories_analyzed": result.total_memories_analyzed,
            "window_days": result.analysis_window_days,
            "semantic_ids_stored": stored_ids,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @logged_method()
    async def get_recurring(self, min_frequency: float = 0.3, **kwargs) -> SkillResult:
        """Get recurring topic patterns from tracker."""
        if not self._recognizer:
            return SkillResult.fail("Pattern recognizer not initialized")

        all_topics = list(self._recognizer.frequency_tracker.topic_history.keys())
        recurring = self._recognizer.frequency_tracker.find_recurring(
            all_topics, min_frequency=min_frequency)
        return SkillResult.ok({
            "recurring_topics": recurring,
            "total_tracked_topics": len(all_topics),
        })

    @logged_method()
    async def get_emerging(self, min_growth_rate: float = 2.0, **kwargs) -> SkillResult:
        """Get newly emerging topics."""
        if not self._recognizer:
            return SkillResult.fail("Pattern recognizer not initialized")

        emerging = self._recognizer.frequency_tracker.find_emerging(
            min_growth_rate=min_growth_rate)
        return SkillResult.ok({"emerging_topics": emerging})

    @logged_method()
    async def get_pattern_stats(self, **kwargs) -> SkillResult:
        """Get statistics from the last pattern detection run."""
        if self._last_result is None:
            return SkillResult.ok({"has_data": False, "message": "No detection run yet."})

        r = self._last_result
        by_type: dict[str, int] = {}
        for p in r.patterns_found:
            by_type[p.type.value] = by_type.get(p.type.value, 0) + 1

        return SkillResult.ok({
            "has_data": True,
            "patterns_found": len(r.patterns_found),
            "new_patterns": r.new_patterns,
            "persistent_patterns": r.persistent_patterns,
            "by_type": by_type,
            "memories_analyzed": r.total_memories_analyzed,
            "window_days": r.analysis_window_days,
            "history_size": len(self._recognizer.pattern_history) if self._recognizer else 0,
        })

    async def close(self) -> None:
        self._api = None
        self._recognizer = None
        self._status = SkillStatus.UNAVAILABLE
