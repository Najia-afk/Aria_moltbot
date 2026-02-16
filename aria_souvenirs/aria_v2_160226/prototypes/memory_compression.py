"""
Memory Compression Prototype
Reduces token usage by summarizing old memories into hierarchical tiers.

Tiers:
- raw: Last 20 messages (verbatim, high-value)
- recent: Last 100 messages (compressed to 30%)
- archive: Everything older (compressed to 10%)
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import json


# ===========================
# Data Models
# ===========================

@dataclass
class Memory:
    """Raw memory entry."""
    id: str
    content: str
    category: str
    timestamp: datetime
    importance_score: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressedMemory:
    """Compressed memory summary."""
    tier: str  # "raw", "recent", "archive"
    summary: str
    original_count: int
    compressed_count: int
    key_entities: List[str]
    timestamp: datetime
    key_facts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_ids: List[str] = field(default_factory=list)

    def to_dict(self):
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class CompressionResult:
    """Result of compression operation."""
    success: bool
    memories_processed: int
    compressed_count: int
    compression_ratio: float
    tiers_updated: Dict[str, int]
    errors: List[str] = field(default_factory=list)


# ===========================
# Importance Scoring
# ===========================

class ImportanceScorer:
    """Score memories by importance to decide what to keep/compress."""

    def __init__(
        self,
        recency_weight: float = 0.4,
        significance_weight: float = 0.3,
        category_weight: float = 0.2,
        length_weight: float = 0.1
    ):
        self.recency_weight = recency_weight
        self.significance_weight = significance_weight
        self.category_weight = category_weight
        self.length_weight = length_weight

        # Category importance multipliers
        self.category_importance = {
            "user_command": 1.0,
            "goal": 1.0,
            "decision": 0.9,
            "error": 0.8,
            "reflection": 0.7,
            "social": 0.5,
            "context": 0.4,
            "system": 0.3,
        }

    def score(self, memory: Memory, now: Optional[datetime] = None) -> float:
        """Calculate importance score (0.0-1.0)."""
        if now is None:
            now = datetime.now(timezone.utc)

        # 1. Recency (exponential decay: 1 hour = 1.0, 24 hours = 0.3)
        age_hours = (now - memory.timestamp).total_seconds() / 3600
        recency = 2.0 ** (-age_hours / 4)  # Half-life ~4 hours
        recency = max(0.1, min(1.0, recency))

        # 2. Significance (from metadata or default)
        significance = memory.importance_score

        # 3. Category importance
        category_mult = self.category_importance.get(memory.category, 0.5)

        # 4. Length penalty (too short = low info, too long = verbose)
        content_len = len(memory.content)
        if content_len < 20:
            length_score = 0.3
        elif 20 <= content_len <= 500:
            length_score = 1.0
        else:
            length_score = 0.7

        # Weighted sum
        total = (
            recency * self.recency_weight +
            significance * self.significance_weight +
            category_mult * self.category_weight +
            length_score * self.length_weight
        )

        return max(0.0, min(1.0, total))


# ===========================
# Compression Engine
# ===========================

class MemoryCompressor:
    """
    Hierarchical memory compression system.

    Strategy:
    1. Keep last N messages verbatim (raw tier)
    2. Compress recent messages to summaries (~30% size)
    3. Archive old messages into key-fact summaries (~10% size)
    """

    def __init__(
        self,
        raw_limit: int = 20,
        recent_limit: int = 100,
        compression_ratios: Dict[str, float] = None,
        llm_summarizer = None  # Optional LLM for better summaries
    ):
        self.raw_limit = raw_limit
        self.recent_limit = recent_limit
        self.compression_ratios = compression_ratios or {
            "recent": 0.3,
            "archive": 0.1
        }
        self.llm_summarizer = llm_summarizer
        self.scorer = ImportanceScorer()

    async def compress_tier(
        self,
        memories: List[Memory],
        target_tier: str,
        target_count: int
    ) -> List[CompressedMemory]:
        """
        Compress memories into target tier with specified target count.

        Args:
            memories: Input memories to compress
            target_tier: "recent" or "archive"
            target_count: Approximate number of compressed items to produce

        Returns:
            List of compressed memory summaries
        """
        if not memories:
            return []

        now = datetime.now(timezone.utc)

        # 1. Score memories by importance
        scored = [(m, self.scorer.score(m, now)) for m in memories]
        scored.sort(key=lambda x: x[1], reverse=True)

        # 2. Select representative sample
        # Keep top (target_count / compression_ratio) memories for compression
        ratio = self.compression_ratios.get(target_tier, 0.3)
        keep_count = max(1, int(target_count / ratio))
        to_compress = scored[:keep_count]

        # 3. Generate summaries
        compressed = []
        batch_size = 20  # Summarize in batches

        for i in range(0, len(to_compress), batch_size):
            batch = to_compress[i:i+batch_size]
            batch_memories = [m for m, _ in batch]

            summary = await self._summarize_batch(batch_memories, target_tier)

            compressed.append(CompressedMemory(
                tier=target_tier,
                summary=summary["text"],
                original_count=len(batch_memories),
                compressed_count=1,
                key_entities=summary["entities"],
                timestamp=now,
                key_facts=summary["facts"],
                original_ids=[m.id for m in batch_memories]
            ))

        return compressed

    async def _summarize_batch(
        self,
        memories: List[Memory],
        tier: str
    ) -> Dict[str, Any]:
        """
        Generate summary for a batch of memories.

        Uses LLM if available, otherwise rule-based extraction.
        """
        contents = [m.content for m in memories]
        categories = [m.category for m in memories]

        # Simple summarization (no LLM)
        if not self.llm_summarizer:
            return self._rule_based_summary(contents, categories)

        # LLM-based summarization
        try:
            prompt = self._build_summary_prompt(contents, tier)
            result = await self.llm_summarizer.generate(prompt)

            # Parse LLM output (expect JSON)
            parsed = json.loads(result)
            return {
                "text": parsed.get("summary", ""),
                "entities": parsed.get("entities", []),
                "facts": parsed.get("facts", [])
            }
        except Exception as e:
            # Fallback to rule-based
            return self._rule_based_summary(contents, categories)

    def _build_summary_prompt(self, contents: List[str], tier: str) -> str:
        """Build prompt for LLM summarization."""
        if tier == "recent":
            instruction = (
                "Summarize these conversation excerpts into a concise paragraph. "
                "Preserve key facts, decisions, and user preferences. "
                "Return as JSON: {\"summary\": \"...\", \"entities\": [\"person1\", ...], \"facts\": [\"fact1\", ...]}"
            )
        else:  # archive
            instruction = (
                "Extract only the most important persistent knowledge from these memories. "
                "Focus on long-term facts, learned preferences, and recurring patterns. "
                "Be extremely concise. Return as JSON."
            )

        return f"{instruction}\n\nMemories:\n" + "\n".join(f"- {c}" for c in contents[:20])

    def _rule_based_summary(
        self,
        contents: List[str],
        categories: List[str]
    ) -> Dict[str, Any]:
        """Simple rule-based summarization when LLM unavailable."""
        # Extract first sentences, unique topics
        first_sentences = []
        entities = set()
        facts = []

        for c in contents:
            # Get first sentence (up to 100 chars)
            first = c.split('.')[0][:100]
            if first and first not in first_sentences:
                first_sentences.append(first)

            # Simple entity extraction (capitalized words)
            words = c.split()
            for word in words:
                if word.istitle() and len(word) > 2:
                    entities.add(word.strip(".,!?;:"))

        summary = f"{len(contents)} {categories[0] if categories else 'general'} events. " + " ".join(first_sentences[:3])

        return {
            "text": summary[:300],
            "entities": list(entities)[:10],
            "facts": facts
        }


# ===========================
# Compression Manager
# ===========================

class CompressionManager:
    """
    Manages hierarchical compression workflow.
    """

    def __init__(self, compressor: MemoryCompressor):
        self.compressor = compressor
        self.tiers = {
            "raw": {"limit": 20, "memories": []},
            "recent": {"limit": 100, "memories": []},
            "archive": {"limit": None, "memories": []}  # No limit, but ratio-based
        }
        self.compressed_store: List[CompressedMemory] = []

    async def process_all(
        self,
        memories: List[Memory]
    ) -> CompressionResult:
        """
        Process all memories through the compression pipeline.

        Strategy:
        1. Sort by recency
        2. Keep top raw_limit in "raw" tier (verbatim)
        3. Compress next recent_limit into "recent" tier summaries
        4. Compress remainder into "archive" tier summaries
        """
        if len(memories) < 10:
            return CompressionResult(
                success=True,
                memories_processed=len(memories),
                compressed_count=len(memories),
                compression_ratio=1.0,
                tiers_updated={}
            )

        # Sort by recency (newest first)
        memories.sort(key=lambda m: m.timestamp, reverse=True)

        # Tier assignment
        raw_memories = memories[:self.compressor.raw_limit]
        recent_memories = memories[self.compressor.raw_limit:][:self.compressor.recent_limit]
        archive_memories = memories[self.compressor.raw_limit + self.compressor.recent_limit:]

        result = CompressionResult(
            success=True,
            memories_processed=len(memories),
            compressed_count=0,
            compression_ratio=0,
            tiers_updated={}
        )

        # Process recent tier
        if recent_memories:
            recent_compressed = await self.compressor.compress_tier(
                recent_memories,
                "recent",
                self.compressor.recent_limit
            )
            self.compressed_store.extend(recent_compressed)
            result.tiers_updated["recent"] = len(recent_compressed)
            result.compressed_count += len(recent_compressed)

        # Process archive tier
        if archive_memories:
            archive_compressed = await self.compressor.compress_tier(
                archive_memories,
                "archive",
                max(1, len(archive_memories) // 10)  # Target ~10% compression
            )
            self.compressed_store.extend(archive_compressed)
            result.tiers_updated["archive"] = len(archive_compressed)
            result.compressed_count += len(archive_compressed)

        # Calculate compression ratio
        result.compression_ratio = result.compressed_count / len(memories) if memories else 0

        return result

    def get_active_memories(
        self,
        raw_memories: List[Memory]
    ) -> List[Dict[str, Any]]:
        """
        Assemble active context from raw + compressed memories.

        Returns list ready for LLM context injection.
        """
        # Get fresh raw memories (top N)
        raw_memories.sort(key=lambda m: m.timestamp, reverse=True)
        active_raw = raw_memories[:self.compressor.raw_limit]

        # Get relevant compressed summaries (from recent tier)
        recent_compressed = [c for c in self.compressed_store if c.tier == "recent"]
        archive_compressed = [c for c in self.compressed_store if c.tier == "archive"]

        # Build context
        context_parts = []

        # 1. Recent compressed summaries
        if recent_compressed:
            context_parts.append("RECENT OVERVIEW:\n" + "\n".join(
                f"- {c.summary}" for c in recent_compressed[-5:]  # Last 5 summaries
            ))

        # 2. Raw recent messages
        if active_raw:
            context_parts.append("RECENT MESSAGES:\n" + "\n".join(
                f"[{m.timestamp.strftime('%H:%M')}] {m.content[:150]}..."
                for m in active_raw[:10]
            ))

        # 3. Archive knowledge (key facts only)
        if archive_compressed:
            context_parts.append("LONG-TERM KNOWLEDGE:\n" + "\n".join(
                f"- {c.summary}" for c in archive_compressed[-3:]  # Last 3 archive summaries
            ))

        return [{"content": "\n\n".join(context_parts), "tokens_est": self._estimate_tokens(context_parts)}]

    def _estimate_tokens(self, parts: List[str]) -> int:
        """Rough token estimation (4 chars per token)."""
        total_chars = sum(len(p) for p in parts)
        return total_chars // 4


# ===========================
# Utility Functions
# ===========================

async def compress_memories_workflow(
    raw_memories: List[Memory],
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Complete compression workflow.

    Usage:
        result = await compress_memories_workflow(memories, {
            "raw_limit": 20,
            "recent_limit": 100
        })
    """
    config = config or {}
    compressor = MemoryCompressor(
        raw_limit=config.get("raw_limit", 20),
        recent_limit=config.get("recent_limit", 100)
    )
    manager = CompressionManager(compressor)

    result = await manager.process_all(raw_memories)

    return {
        "success": result.success,
        "memories_processed": result.memories_processed,
        "compression_ratio": result.compression_ratio,
        "tiers": result.tiers_updated,
        "context_active": manager.get_active_memories(raw_memories),
        "stats": {
            "compressed_count": result.compressed_count,
            "tokens_saved_estimate": int(result.memories_processed * 50 * (1 - result.compression_ratio))
        }
    }


# ===========================
# Example Usage
# ===========================

if __name__ == "__main__":
    # Example memories
    example_memories = [
        Memory(
            id="1",
            content="User asked about quantum eraser experiment. Explained it involves entangled photons and double-slit.",
            category="user_command",
            timestamp=datetime.now(timezone.utc),
            importance_score=0.8
        ),
        Memory(
            id="2",
            content="User likes concise answers without fluff.",
            category="preference",
            timestamp=datetime.now(timezone.utc),
            importance_score=0.9
        ),
    ]

    # Run compression
    result = asyncio.run(compress_memories_workflow(example_memories))
    print(json.dumps(result, indent=2, default=str))
