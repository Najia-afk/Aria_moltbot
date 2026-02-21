"""
Pattern Recognition Prototype
Detects recurring themes, user behaviors, and conversation patterns.

Pattern Types:
- Topic recurrence (subjects that come up repeatedly)
- Temporal patterns (time-based behaviors)
- Sentiment drift (emotional trends)
- Interest emergence (new topics gaining frequency)
- Knowledge gaps (repeated questions)
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import re


# ===========================
# Data Models
# ===========================

class PatternType(Enum):
    TOPIC_RECURRENCE = "topic_recurrence"
    TEMPORAL_PATTERN = "temporal_pattern"
    SENTIMENT_DRIFT = "sentiment_drift"
    INTEREST_EMERGENCE = "interest_emergence"
    KNOWLEDGE_GAP = "knowledge_gap"
    BEHAVIOR_CYCLE = "behavior_cycle"


@dataclass
class Pattern:
    """Detected pattern."""
    type: PatternType
    subject: str
    confidence: float  # 0.0-1.0
    evidence: List[Any] = field(default_factory=list)
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    frequency_per_day: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        data["type"] = self.type.value
        data["first_seen"] = self.first_seen.isoformat()
        data["last_seen"] = self.last_seen.isoformat()
        return data


@dataclass
class TopicMention:
    """A mention of a topic in memory."""
    topic: str
    timestamp: datetime
    memory_id: str
    sentiment: Optional[float] = None  # -1 to +1
    category: str = "general"


@dataclass
class PatternDetectionResult:
    """Result of pattern detection run."""
    patterns_found: List[Pattern]
    total_memories_analyzed: int
    analysis_window_days: int
    new_patterns: int
    persistent_patterns: int
    metadata: Dict[str, Any] = field(default_factory=dict)


# ===========================
# Topic Extraction
# ===========================

class TopicExtractor:
    """
    Extract topics from memory content.

    Uses:
    - Keyword matching (predefined topics)
    - Named entity recognition (simple regex for now)
    - Category mapping
    """

    def __init__(self):
        # Predefined topic keywords
        self.topic_keywords = {
            "quantum_mechanics": ["quantum", "photon", "entanglement", "qubit", "superposition"],
            "coding": ["code", "python", "function", "class", "debug", "api"],
            "memory_system": ["memory", "compress", "embedding", "pattern", "recall"],
            "security": ["security", "vulnerability", "auth", "encrypt", "password"],
            "goals": ["goal", "task", "complete", "progress", "milestone"],
            "social": ["moltbook", "post", "comment", "telegram", "message"],
        }

        # Simple entity patterns (capitalized words, technical terms)
        self.entity_pattern = re.compile(r'\b[A-Z][a-zA-Z]+(?:[ -][A-Z][a-zA-Z]+)*\b')
        self.tech_pattern = re.compile(r'\b(?:API|LLM|AI|ML|DB|SQL|HTTP|HTTPS|JSON|XML|Docker|Kubernetes)\b', re.IGNORECASE)

    def extract(self, memories: List[Memory]) -> List[TopicMention]:
        """Extract topics from a list of memories."""
        mentions = []

        for memory in memories:
            # Method 1: Category-based topics
            category_topic = self._map_category_to_topic(memory.category)
            if category_topic:
                mentions.append(TopicMention(
                    topic=category_topic,
                    timestamp=memory.timestamp,
                    memory_id=memory.id,
                    category=memory.category
                ))

            # Method 2: Keyword matching
            content_lower = memory.content.lower()
            for topic, keywords in self.topic_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    mentions.append(TopicMention(
                        topic=topic,
                        timestamp=memory.timestamp,
                        memory_id=memory.id,
                        category=memory.category
                    ))

            # Method 3: Named entity extraction
            entities = self._extract_entities(memory.content)
            for entity in entities:
                mentions.append(TopicMention(
                    topic=entity.lower().replace(" ", "_"),
                    timestamp=memory.timestamp,
                    memory_id=memory.id,
                    category=memory.category
                ))

        return mentions

    def _map_category_to_topic(self, category: str) -> Optional[str]:
        """Map memory category to a high-level topic."""
        mapping = {
            "user_command": "interaction",
            "goal": "goals",
            "decision": "decision_making",
            "error": "errors",
            "reflection": "reflection",
            "social": "social",
            "context": "context",
            "system": "system",
            "technical": "coding",
            "security": "security",
        }
        return mapping.get(category)

    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text."""
        entities = []

        # Capitalized multi-word entities
        for match in self.entity_pattern.finditer(text):
            entity = match.group()
            # Filter out sentence starts (low chance of being entity)
            if len(entity) > 3 and entity not in ["The", "This", "That", "When", "What"]:
                entities.append(entity)

        # Technical acronyms
        entities.extend(self.tech_pattern.findall(text))

        return list(set(entities))


# ===========================
# Frequency Tracker
# ===========================

class FrequencyTracker:
    """
    Track topic frequencies over sliding time windows.
    Detects recurrence and emergence patterns.
    """

    def __init__(self, window_days: int = 30):
        self.window_days = window_days
        self.topic_history: Dict[str, List[TopicMention]] = defaultdict(list)

    def add_mentions(self, mentions: List[TopicMention]):
        """Add new topic mentions to history."""
        for mention in mentions:
            self.topic_history[mention.topic].append(mention)

    def get_frequency(
        self,
        topic: str,
        window_days: Optional[int] = None
    ) -> float:
        """
        Calculate frequency of a topic over time window.

        Returns: mentions per day
        """
        window = window_days or self.window_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=window)

        mentions = [
            m for m in self.topic_history.get(topic, [])
            if m.timestamp >= cutoff
        ]

        return len(mentions) / window

    def find_recurring(
        self,
        topics: List[str],
        min_frequency: float = 0.3,
        min_mentions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find topics that recur frequently.

        Returns:
            List of {topic, frequency, total_mentions, is_newly_recurring?}
        """
        recurring = []

        for topic in set(topics):
            freq = self.get_frequency(topic)
            total = len(self.topic_history.get(topic, []))

            if freq >= min_frequency or total >= min_mentions:
                # Check if it's newly recurring (last 3 days spike)
                recent_freq = self.get_frequency(topic, window_days=3)
                is_newly = recent_freq > freq * 1.5 if freq > 0 else False

                recurring.append({
                    "topic": topic,
                    "frequency_per_day": round(freq, 3),
                    "total_mentions": total,
                    "is_newly_recurring": is_newly
                })

        # Sort by frequency
        recurring.sort(key=lambda x: x["frequency_per_day"], reverse=True)
        return recurring

    def find_emerging(
        self,
        min_growth_rate: float = 2.0,
        min_recent_mentions: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find topics that are emerging (growth rate > threshold).

        Emerging = recent frequency > historical average * growth_rate
        """
        emerging = []

        for topic, mentions in self.topic_history.items():
            if len(mentions) < min_recent_mentions:
                continue

            # Split into recent (3 days) and older (before that)
            cutoff_recent = datetime.now(timezone.utc) - timedelta(days=3)
            recent = [m for m in mentions if m.timestamp >= cutoff_recent]
            older = [m for m in mentions if m.timestamp < cutoff_recent]

            if not older:
                # All mentions are recent = new topic
                if len(recent) >= min_recent_mentions:
                    emerging.append({
                        "topic": topic,
                        "recent_mentions": len(recent),
                        "growth_rate": float('inf'),
                        "is_new": True
                    })
                continue

            recent_freq = len(recent) / 3
            older_freq = len(older) / (max(1, (mentions[0].timestamp - older[-1].timestamp).days) if older else 1)

            if recent_freq >= older_freq * min_growth_rate:
                emerging.append({
                    "topic": topic,
                    "recent_mentions": len(recent),
                    "older_mentions": len(older),
                    "recent_freq_per_day": round(recent_freq, 3),
                    "older_freq_per_day": round(older_freq, 3),
                    "growth_rate": round(recent_freq / older_freq, 2) if older_freq > 0 else float('inf')
                })

        emerging.sort(key=lambda x: x.get("growth_rate", 0), reverse=True)
        return emerging


# ===========================
# Pattern Recognizer
# ===========================

class PatternRecognizer:
    """
    Main pattern recognition engine.

    Workflow:
    1. Extract topics from memories
    2. Track frequencies over time
    3. Detect patterns using statistical analysis
    4. Augment with LLM for semantic patterns (if available)
    """

    def __init__(
        self,
        window_days: int = 30,
        llm_analyzer = None
    ):
        self.window_days = window_days
        self.llm_analyzer = llm_analyzer
        self.topic_extractor = TopicExtractor()
        self.frequency_tracker = FrequencyTracker(window_days)
        self.pattern_history: List[Pattern] = []

    async def analyze(
        self,
        memories: List[Memory],
        min_confidence: float = 0.3
    ) -> PatternDetectionResult:
        """
        Detect patterns in memory stream.

        Args:
            memories: Recent memories to analyze
            min_confidence: Minimum confidence to include patterns

        Returns:
            PatternDetectionResult with all detected patterns
        """
        if len(memories) < 10:
            return PatternDetectionResult(
                patterns_found=[],
                total_memories_analyzed=len(memories),
                analysis_window_days=self.window_days,
                new_patterns=0,
                persistent_patterns=0
            )

        # 1. Extract topics
        mentions = self.topic_extractor.extract(memories)
        self.frequency_tracker.add_mentions(mentions)

        # 2. Detect pattern types
        patterns = []

        # Topic recurrence
        recurring = self.frequency_tracker.find_recurring(
            [m.topic for m in mentions]
        )
        for rec in recurring:
            if rec["frequency_per_day"] >= 0.1:  # At least weekly
                pattern = Pattern(
                    type=PatternType.TOPIC_RECURRENCE,
                    subject=rec["topic"],
                    confidence=min(1.0, rec["frequency_per_day"] * 3),  # Scale to 0-1
                    evidence=[f"Frequency: {rec['frequency_per_day']}/day"],
                    first_seen=datetime.now(timezone.utc) - timedelta(days=self.window_days),
                    last_seen=datetime.now(timezone.utc),
                    frequency_per_day=rec["frequency_per_day"]
                )
                patterns.append(pattern)

        # Interest emergence
        emerging = self.frequency_tracker.find_emerging()
        for em in emerging:
            pattern = Pattern(
                type=PatternType.INTEREST_EMERGENCE,
                subject=em["topic"],
                confidence=0.8 if em.get("is_new") else 0.6,
                evidence=[f"Growth rate: {em.get('growth_rate', 1):.1f}x"],
                frequency_per_day=em.get("recent_freq_per_day", 0)
            )
            patterns.append(pattern)

        # 3. Temporal patterns (activity by hour/day)
        temporal_patterns = self._detect_temporal_patterns(memories)
        patterns.extend(temporal_patterns)

        # 4. Sentiment drift (if sentiment data available)
        sentiment_patterns = self._detect_sentiment_drift(memories)
        patterns.extend(sentiment_patterns)

        # 5. Knowledge gaps (repeated questions)
        gap_patterns = self._detect_knowledge_gaps(memories)
        patterns.extend(gap_patterns)

        # 6. LLM-enhanced patterns (if available)
        if self.llm_analyzer:
            llm_patterns = await self._llm_detect_patterns(memories)
            patterns.extend(llm_patterns)

        # Filter by confidence
        patterns = [p for p in patterns if p.confidence >= min_confidence]

        # Deduplicate by subject+type
        unique_patterns = self._deduplicate_patterns(patterns)

        # Track new vs persistent
        now = datetime.now(timezone.utc)
        new_count = 0
        persistent_count = 0

        for pattern in unique_patterns:
            # Check if similar pattern existed before
            is_persistent = any(
                p.type == pattern.type and p.subject == pattern.subject
                for p in self.pattern_history
            )
            if is_persistent:
                persistent_count += 1
            else:
                new_count += 1

        self.pattern_history.extend(unique_patterns)

        return PatternDetectionResult(
            patterns_found=unique_patterns,
            total_memories_analyzed=len(memories),
            analysis_window_days=self.window_days,
            new_patterns=new_count,
            persistent_patterns=persistent_count
        )

    def _detect_temporal_patterns(self, memories: List[Memory]) -> List[Pattern]:
        """Detect time-based patterns (active hours, day of week)."""
        patterns = []

        if len(memories) < 10:
            return patterns

        # Hour distribution
        hours = [m.timestamp.hour for m in memories]
        hour_counts = Counter(hours)

        # Find peak hours (>25% of activity)
        total = len(hours)
        for hour, count in hour_counts.items():
            if count / total >= 0.25:
                patterns.append(Pattern(
                    type=PatternType.TEMPORAL_PATTERN,
                    subject=f"active_hour_{hour:02d}",
                    confidence=count / total,
                    evidence=[f"{count} events during hour {hour}"],
                    metadata={"hour": hour, "count": count}
                ))

        # Day of week pattern
        weekdays = [m.timestamp.weekday() for m in memories]
        weekday_counts = Counter(weekdays)

        for day, count in weekday_counts.items():
            if count / total >= 0.3:
                day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day]
                patterns.append(Pattern(
                    type=PatternType.TEMPORAL_PATTERN,
                    subject=f"active_day_{day_name.lower()}",
                    confidence=count / total,
                    evidence=[f"{count} events on {day_name}"],
                    metadata={"weekday": day, "day_name": day_name}
                ))

        return patterns

    def _detect_sentiment_drift(self, memories: List[Memory]) -> List[Pattern]:
        """Detect significant changes in sentiment over time."""
        patterns = []

        # Check if memories have sentiment scores
        memories_with_sentiment = [m for m in memories if "sentiment" in m.metadata]
        if len(memories_with_sentiment) < 5:
            return patterns

        # Sort by time
        sorted_memories = sorted(memories_with_sentiment, key=lambda m: m.timestamp)

        # Split first half vs second half
        mid = len(sorted_memories) // 2
        first_half = sorted_memories[:mid]
        second_half = sorted_memories[mid:]

        avg_first = sum(m.metadata["sentiment"] for m in first_half) / len(first_half)
        avg_second = sum(m.metadata["sentiment"] for m in second_half) / len(second_half)

        diff = avg_second - avg_first

        if abs(diff) >= 0.3:  # Significant change
            direction = "improving" if diff > 0 else "declining"
            patterns.append(Pattern(
                type=PatternType.SENTIMENT_DRIFT,
                subject="conversation_tone",
                confidence=min(1.0, abs(diff) * 2),
                evidence=[
                    f"First half avg: {avg_first:.2f}",
                    f"Second half avg: {avg_second:.2f}",
                    f"Change: {diff:.2f}"
                ],
                metadata={
                    "direction": direction,
                    "first_half_avg": avg_first,
                    "second_half_avg": avg_second
                }
            ))

        return patterns

    def _detect_knowledge_gaps(self, memories: List[Memory]) -> List[Pattern]:
        """Detect repeated questions = knowledge gap."""
        patterns = []

        # Find question memories
        questions = [m for m in memories if m.content.strip().endswith("?")]

        if len(questions) < 2:
            return patterns

        # Group by topic (simple keyword grouping)
        question_topics = defaultdict(list)
        for q in questions:
            # Extract main subject (first noun phrase)
            words = q.content.lower().split()
            if len(words) >= 3:
                topic = " ".join(words[:3])
                question_topics[topic].append(q)

        # Find repeated question topics
        for topic, qs in question_topics.items():
            if len(qs) >= 2:
                time_span = (qs[-1].timestamp - qs[0].timestamp).total_seconds() / 3600
                if time_span > 1:  # Repeated over time, not just in same conversation
                    patterns.append(Pattern(
                        type=PatternType.KNOWLEDGE_GAP,
                        subject=topic,
                        confidence=min(1.0, len(qs) / 5),
                        evidence=[f"Asked {len(qs)} times over {time_span:.1f}h"],
                        metadata={"question_count": len(qs)}
                    ))

        return patterns

    async def _llm_detect_patterns(self, memories: List[Memory]) -> List[Pattern]:
        """Use LLM to detect semantic patterns not caught by statistics."""
        if not self.llm_analyzer:
            return []

        try:
            # Prepare memory summaries
            summaries = [
                f"[{m.timestamp.isoformat()}] {m.category}: {m.content[:100]}"
                for m in memories[-50:]  # Last 50 memories
            ]

            prompt = (
                "Analyze these memory entries and detect recurring behavioral patterns, "
                "topic cycles, or user preference shifts. Return JSON list:\n"
                "[{\"type\": \"pattern_type\", \"subject\": \"topic\", \"confidence\": 0.8, \"explanation\": \"...\"}]\n"
                "Pattern types: topic_recurrence, temporal_pattern, sentiment_drift, interest_emergence, behavior_cycle\n\n"
                + "\n".join(summaries)
            )

            result = await self.llm_analyzer.generate(prompt)
            llm_patterns = json.loads(result)

            patterns = []
            for p in llm_patterns:
                try:
                    pattern_type = PatternType(p["type"])
                except ValueError:
                    pattern_type = PatternType.TOPIC_RECURRENCE

                patterns.append(Pattern(
                    type=pattern_type,
                    subject=p["subject"],
                    confidence=float(p.get("confidence", 0.5)),
                    evidence=[p.get("explanation", "")]
                ))

            return patterns

        except Exception as e:
            print(f"LLM pattern detection failed: {e}")
            return []

    def _deduplicate_patterns(self, patterns: List[Pattern]) -> List[Pattern]:
        """Remove duplicate patterns (same type+subject)."""
        seen = set()
        unique = []

        for pattern in patterns:
            key = (pattern.type, pattern.subject)
            if key not in seen:
                seen.add(key)
                unique.append(pattern)

        # Sort by confidence
        unique.sort(key=lambda p: p.confidence, reverse=True)
        return unique


# ===========================
# Utility Functions
# ===========================

async def detect_patterns_workflow(
    memories: List[Memory],
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Complete pattern detection workflow.

    Usage:
        result = await detect_patterns_workflow(memories, {
            "window_days": 30,
            "min_confidence": 0.3
        })
    """
    config = config or {}
    recognizer = PatternRecognizer(
        window_days=config.get("window_days", 30)
    )

    result = await recognizer.analyze(
        memories,
        min_confidence=config.get("min_confidence", 0.3)
    )

    return {
        "success": True,
        "patterns_found": len(result.patterns_found),
        "patterns": [p.to_dict() for p in result.patterns_found],
        "new_patterns": result.new_patterns,
        "persistent_patterns": result.persistent_patterns,
        "memories_analyzed": result.total_memories_analyzed,
        "window_days": result.analysis_window_days
    }


# ===========================
# Example Usage
# ===========================

if __name__ == "__main__":
    # Example memories
    example = [
        Memory("1", "What is quantum entanglement?", "user_command", datetime.now(timezone.utc), importance_score=0.7),
        Memory("2", "User likes concise answers.", "preference", datetime.now(timezone.utc), importance_score=0.9),
        Memory("3", "How do I compress data?", "user_command", datetime.now(timezone.utc), importance_score=0.6),
        Memory("4", "Quantum eraser experiment explained.", "technical", datetime.now(timezone.utc), importance_score=0.8),
    ]

    result = asyncio.run(detect_patterns_workflow(example))
    print(json.dumps(result, indent=2, default=str))
