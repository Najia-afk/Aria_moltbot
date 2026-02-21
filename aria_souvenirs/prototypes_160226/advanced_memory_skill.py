"""
Aria Advanced Memory Skill
Combines: compression, pattern recognition, sentiment, embeddings.
"""

from typing import Any
from dataclasses import asdict
import asyncio

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method


# ===========================
# Import Prototype Components
# ===========================

# These will be copied from prototypes/
from prototypes.memory_compression import (
    MemoryCompressor,
    CompressionManager,
    compress_memories_workflow
)
from prototypes.pattern_recognition import (
    PatternRecognizer,
    detect_patterns_workflow
)
from prototypes.sentiment_analysis import (
    SentimentAnalyzer,
    ConversationAnalyzer,
    analyze_sentiment_workflow,
    ResponseTuner
)
from prototypes.embedding_memory import (
    EmbeddingMemory,
    create_embedding_memory,
    RetrievalStrategy,
    semantic_search_workflow
)


# ===========================
# Main Skill Class
# ===========================

@SkillRegistry.register
class AdvancedMemorySkill(BaseSkill):
    """
    Unified advanced memory system for Aria.

    Provides:
    - Hierarchical memory compression
    - Pattern recognition (topics, temporal, sentiment drift)
    - Multi-dimensional sentiment analysis
    - Semantic vector search
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self.compressor: MemoryCompressor | None = None
        self.pattern_recognizer: PatternRecognizer | None = None
        self.sentiment_analyzer: SentimentAnalyzer | None = None
        self.embedding_memory: EmbeddingMemory | None = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "advanced_memory"

    async def initialize(self) -> bool:
        """Initialize all subsystems."""
        try:
            # Initialize components (lazy loading OK)
            self.compressor = MemoryCompressor()
            self.pattern_recognizer = PatternRecognizer()
            self.sentiment_analyzer = SentimentAnalyzer()
            # Embedding memory initialized on first use (heavy)

            self._status = SkillStatus.AVAILABLE
            self._initialized = True
            self.logger.info("AdvancedMemorySkill initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            self._status = SkillStatus.UNAVAILABLE
            return False

    async def health_check(self) -> SkillStatus:
        return self._status

    # ═══════════════════════════════════════════════════════════════
    # Tool 1: compress_memories
    # ═══════════════════════════════════════════════════════════════

    @logged_method()
    async def compress_memories(
        self,
        memories: list[dict[str, Any]] = None,
        **kwargs
    ) -> SkillResult:
        """
        Compress memories into hierarchical tiers.

        Args:
            memories: List of memory dicts with keys:
                - id: str
                - content: str
                - category: str
                - timestamp: ISO datetime string
                - importance_score: float (optional)

        Returns:
            Compression results with active context ready for LLM
        """
        if not memories or len(memories) < 5:
            return SkillResult.ok({
                "compressed": False,
                "reason": "Not enough memories to compress (need >= 5)",
                "memories_processed": len(memories) if memories else 0
            })

        # Convert dicts to Memory objects
        from datetime import datetime
        from prototypes.memory_compression import Memory

        mem_objects = []
        for m in memories:
            mem_objects.append(Memory(
                id=m["id"],
                content=m["content"],
                category=m.get("category", "general"),
                timestamp=datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")),
                importance_score=m.get("importance_score", 0.5),
                metadata=m.get("metadata", {})
            ))

        # Run compression
        result = await compress_memories_workflow(mem_objects, kwargs)

        return SkillResult.ok(result)

    # ═══════════════════════════════════════════════════════════════
    # Tool 2: detect_patterns
    # ═══════════════════════════════════════════════════════════════

    @logged_method()
    async def detect_patterns(
        self,
        memories: list[dict[str, Any]] = None,
        window_days: int = 30,
        min_confidence: float = 0.3,
        **kwargs
    ) -> SkillResult:
        """
        Detect patterns in memory stream.

        Args:
            memories: List of memory dicts (see compress_memories)
            window_days: Analysis window in days
            min_confidence: Minimum confidence threshold

        Returns:
            List of detected patterns with confidence scores
        """
        if not memories:
            return SkillResult.fail("No memories provided for pattern detection")

        # Convert to Memory objects
        from datetime import datetime
        from prototypes.pattern_recognition import Memory

        mem_objects = [
            Memory(
                id=m["id"],
                content=m["content"],
                category=m.get("category", "general"),
                timestamp=datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")),
                importance_score=m.get("importance_score", 0.5)
            )
            for m in memories
        ]

        # Run detection
        result = await detect_patterns_workflow(
            mem_objects,
            config={"window_days": window_days, "min_confidence": min_confidence}
        )

        return SkillResult.ok(result)

    # ═══════════════════════════════════════════════════════════════
    # Tool 3: analyze_sentiment
    # ═══════════════════════════════════════════════════════════

    @logged_method()
    async def analyze_sentiment(
        self,
        text: str = None,
        messages: list[dict[str, Any]] = None,
        use_llm: bool = False,
        **kwargs
    ) -> SkillResult:
        """
        Analyze sentiment of text or conversation.

        Args:
            text: Single message to analyze
            messages: List of {"content": str, "timestamp": ...} for conversation analysis
            use_llm: Use LLM for higher accuracy (requires llm skill)

        Returns:
            Sentiment analysis results with trajectory if conversation
        """
        if text:
            # Single message analysis
            analyzer = SentimentAnalyzer(use_llm=use_llm)
            sentiment = await analyzer.analyze(text)
            result = {
                "sentiment": sentiment.to_dict(),
                "tone_recommendation": ResponseTuner().select_tone(sentiment)
            }
            return SkillResult.ok(result)

        elif messages:
            # Conversation analysis
            result = await analyze_sentiment_workflow(messages, config={"use_llm": use_llm})
            return SkillResult.ok(result)

        else:
            return SkillResult.fail("Must provide either 'text' or 'messages'")

    # ═══════════════════════════════════════════════════════════════
    # Tool 4: semantic_search
    # ═══════════════════════════════════════════════════════════

    @logged_method()
    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        min_similarity: float = 0.5,
        category: str = None,
        tags: list[str] = None,
        **kwargs
    ) -> SkillResult:
        """
        Search memories using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity (0-1)
            category: Optional category filter
            tags: Optional tag list filter

        Returns:
            List of similar memories with similarity scores
        """
        try:
            # Lazy initialize embedding memory
            if not self.embedding_memory:
                self.embedding_memory = await create_embedding_memory({
                    "embedding_model": "local",  # or configurable
                    "dimension": 384
                })

            # Build filters
            filters = {}
            if category:
                filters["category"] = category
            if tags:
                filters["tags"] = tags

            strategy = RetrievalStrategy(
                top_k=top_k,
                min_similarity=min_similarity
            )

            results = await self.embedding_memory.recall(
                query,
                strategy=strategy,
                filters=filters if filters else None
            )

            return SkillResult.ok({
                "query": query,
                "results": [r.entry.to_dict() for r in results],
                "result_count": len(results)
            })

        except Exception as e:
            self.logger.error(f"Semantic search failed: {e}")
            return SkillResult.fail(f"Search failed: {str(e)}")

    # ═══════════════════════════════════════════════════════════════
    # Tool 5: store_memory_with_embedding
    # ═════════════════════════════════════════════════════════════

    @logged_method()
    async def store_memory_with_embedding(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        tags: list[str] = None,
        **kwargs
    ) -> SkillResult:
        """
        Store a memory with embedding for future semantic search.

        Args:
            content: Text content to store
            category: Memory category
            importance: Importance score 0-1
            tags: Optional metadata tags

        Returns:
            Stored memory entry ID
        """
        try:
            # Lazy init
            if not self.embedding_memory:
                self.embedding_memory = await create_embedding_memory()

            entry = await self.embedding_memory.remember(
                content=content,
                metadata={
                    "category": category,
                    "importance": importance,
                    "tags": tags or []
                }
            )

            return SkillResult.ok({
                "stored": True,
                "entry_id": entry.id,
                "embedding_dim": len(entry.embedding)
            })

        except Exception as e:
            self.logger.error(f"Store failed: {e}")
            return SkillResult.fail(f"Store failed: {str(e)}")


# ===========================
# Utility: get_memory_insights
# ===========================

async def get_memory_insights_workflow(
    recent_memories: list[dict[str, Any]],
    pattern_days: int = 30
) -> dict[str, Any]:
    """
    Complete insights workflow: compression + patterns + sentiment.

    Convenience function for one-click analysis.
    """
    # Initialize skill
    from aria_skills.registry import SkillRegistry
    config = SkillConfig(name="advanced_memory", config={})
    skill = AdvancedMemorySkill(config)
    await skill.initialize()

    # 1. Compress memories
    compression_result = await skill.compress_memories(recent_memories)

    # 2. Detect patterns
    pattern_result = await skill.detect_patterns(recent_memories, window_days=pattern_days)

    # 3. Sentiment (if >2 messages)
    if len(recent_memories) >= 2:
        sentiment_result = await skill.analyze_sentiment(messages=recent_memories)
    else:
        sentiment_result = None

    return {
        "compression": compression_result.data if compression_result.success else None,
        "patterns": pattern_result.data if pattern_result.success else None,
        "sentiment": sentiment_result.data if sentiment_result and sentiment_result.success else None,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
