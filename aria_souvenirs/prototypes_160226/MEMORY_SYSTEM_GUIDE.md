# Memory Compression, Pattern Recognition & Sentiment Analysis
## Implementation Guide for Aria Blue âš¡ï¸

**Created:** 2026-02-16  
**For:** Najia's implementation session  
**Status:** Documentation + Prototypes Ready

---

## ðŸ“‹ Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Memory Compression](#memory-compression)
4. [Pattern Recognition](#pattern-recognition)
5. [Sentiment Analysis](#sentiment-analysis)
6. [Embedding Memory](#embedding-memory)
7. [Integration Points](#integration-points)
8. [Bug Fix: Session Protection](#bug-fix-session-protection)

---

## Overview

This document describes four interconnected memory subsystems for Aria:

| System | Purpose | Status |
|--------|---------|--------|
| **Memory Compression** | Reduce context window usage by summarizing old memories | Proto Ready |
| **Pattern Recognition** | Detect recurring themes, topics, behaviors | Proto Ready |
| **Sentiment Analysis** | Track emotional tone of conversations | Proto Ready |
| **Embedding Memory** | Vector-based semantic memory retrieval | Proto Ready |

---

## Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    MEMORY SYSTEM ARCHITECTURE                    â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”‚
â”‚  â”‚   Short-Term â”‚â”€â”€â”€â–¶â”‚   Compress   â”‚â”€â”€â”€â–¶â”‚   Long-Term  â”‚      â”‚
â”‚  â”‚    Memory    â”‚    â”‚   & Embed    â”‚    â”‚    Memory    â”‚      â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â”‚
â”‚         â”‚                   â”‚                   â”‚               â”‚
â”‚         â–¼                   â–¼                   â–¼               â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”‚
â”‚  â”‚   Pattern    â”‚    â”‚   Sentiment  â”‚    â”‚   Semantic   â”‚      â”‚
â”‚  â”‚  Recognition â”‚    â”‚   Analysis   â”‚    â”‚    Search    â”‚      â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â”‚
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚  â”‚                 Context Assembly Layer                   â”‚   â”‚
â”‚  â”‚  (weighted combination for LLM context injection)       â”‚   â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Memory Compression

### Purpose
Reduce token usage in context window by compressing old memories into summaries.

### Strategy: Hierarchical Compression

```python
# Tier 1: Raw memories (last 20 messages)
# Tier 2: Recent summary (last 100 messages compressed)
# Tier 3: Long-term summary (everything before Tier 2)
```

### Compression Algorithm

```python
class MemoryCompressor:
    """
    Hierarchical memory compression using LLM summarization.
    """
    
    TIERS = {
        "raw": {"max_items": 20, "ttl_minutes": 30},
        "recent": {"max_items": 100, "compress_ratio": 0.3},
        "archive": {"compress_ratio": 0.1}
    }
    
    async def compress(self, memories: List[Memory]) -> CompressedMemory:
        """
        Compress memories using importance-weighted sampling + LLM summarization.
        
        Steps:
        1. Score memories by importance (recency + significance)
        2. Select top-k most important
        3. Generate LLM summary preserving key facts
        4. Store with metadata (original count, compression ratio, timestamp)
        """
        scored = [(m, self._importance_score(m)) for m in memories]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Keep top 30% by importance
        to_compress = scored[:int(len(scored) * 0.3)]
        
        # Generate summary
        summary = await self._llm_summarize(to_compress)
        
        return CompressedMemory(
            summary=summary,
            original_count=len(memories),
            compressed_count=len(to_compress),
            key_entities=self._extract_entities(to_compress),
            timestamp=now()
        )
```

### Key Features

1. **Importance Scoring**: `score = recency_weight * 0.4 + significance * 0.6`
2. **Entity Preservation**: Extract and preserve named entities (people, projects, facts)
3. **Lossy but Key-Fact Preserving**: Summary loses verbatim quotes but keeps actionable info
4. **Reversible References**: Store hash of original memories for audit trail

---

## Pattern Recognition

### Purpose
Detect recurring themes, user behaviors, conversation patterns, and emerging interests.

### Pattern Types

```python
class PatternTypes:
    TOPIC_RECURRENCE = "topic_recurrence"      # Topics that come up repeatedly
    TEMPORAL_PATTERN = "temporal_pattern"      # Time-based behaviors
    SENTIMENT_DRIFT = "sentiment_drift"        # Changing emotional trends
    INTEREST_EMERGENCE = "interest_emergence"  # New topics gaining frequency
    KNOWLEDGE_GAP = "knowledge_gap"            # Questions asked repeatedly
```

### Pattern Recognition Engine

```python
class PatternRecognizer:
    """
    Detect patterns in memory streams using statistical analysis + LLM.
    """
    
    def __init__(self):
        self.topic_extractor = TopicExtractor()
        self.frequency_tracker = FrequencyTracker(window_days=30)
        self.correlation_engine = CorrelationEngine()
    
    async def analyze(self, memories: List[Memory]) -> List[Pattern]:
        """
        Detect patterns in recent memories.
        
        Returns:
            List of Pattern objects with confidence scores
        """
        patterns = []
        
        # 1. Topic recurrence detection
        topics = self.topic_extractor.extract(memories)
        recurring = self.frequency_tracker.find_recurring(topics)
        for topic in recurring:
            patterns.append(Pattern(
                type=PatternTypes.TOPIC_RECURRENCE,
                subject=topic.name,
                confidence=topic.frequency / len(memories),
                evidence=topic.occurrences
            ))
        
        # 2. Temporal pattern detection
        temporal = self._detect_temporal_patterns(memories)
        patterns.extend(temporal)
        
        # 3. Sentiment drift detection
        sentiment_trend = self._analyze_sentiment_trend(memories)
        if sentiment_trend.is_significant:
            patterns.append(Pattern(
                type=PatternTypes.SENTIMENT_DRIFT,
                subject="conversation_tone",
                confidence=sentiment_trend.confidence,
                evidence=sentiment_trend.data_points
            ))
        
        # 4. Interest emergence (new topics with increasing frequency)
        emerging = self._detect_emerging_interests(memories)
        patterns.extend(emerging)
        
        return patterns
    
    def _detect_temporal_patterns(self, memories: List[Memory]) -> List[Pattern]:
        """Detect time-based patterns (e.g., user active at certain hours)."""
        hour_distribution = Counter([m.timestamp.hour for m in memories])
        
        patterns = []
        for hour, count in hour_distribution.items():
            if count > len(memories) * 0.3:  # >30% of activity
                patterns.append(Pattern(
                    type=PatternTypes.TEMPORAL_PATTERN,
                    subject=f"active_hour_{hour}",
                    confidence=count / len(memories),
                    evidence={"hour": hour, "count": count}
                ))
        
        return patterns
```

### Usage Examples

```python
# After each conversation, analyze for patterns
patterns = await pattern_recognizer.analyze(recent_memories)

# High-confidence patterns become part of user profile
for pattern in patterns:
    if pattern.confidence > 0.7:
        await working_memory.remember(
            key=f"pattern:{pattern.subject}",
            value=pattern.to_dict(),
            category="detected_patterns",
            importance=pattern.confidence
        )
```

---

## Sentiment Analysis

### Purpose
Track emotional tone of conversations to adapt communication style and detect user satisfaction.

### Sentiment Dimensions

```python
class SentimentDimensions:
    """Multi-dimensional sentiment tracking."""
    
    VALENCE = "valence"           # Positive vs negative (-1 to +1)
    AROUSAL = "arousal"           # Calm vs excited (0 to 1)
    DOMINANCE = "dominance"       # Submissive vs dominant (0 to 1)
    
    # Derived metrics
    FRUSTRATION = "frustration"   # High arousal + negative valence
    SATISFACTION = "satisfaction" # Positive valence + high dominance
    CONFUSION = "confusion"       # Low dominance + neutral valence
```

### Sentiment Analyzer

```python
class SentimentAnalyzer:
    """
    Multi-dimensional sentiment analysis using LLM + lexicon.
    """
    
    def __init__(self):
        self.lexicon = load_sentiment_lexicon()
        self.llm_classifier = LLMClassifier()
    
    async def analyze(self, text: str, context: List[str] = None) -> Sentiment:
        """
        Analyze sentiment of a text with optional conversation context.
        
        Returns:
            Sentiment object with dimensions and confidence
        """
        # Fast path: lexicon-based scoring
        lexicon_score = self._lexicon_score(text)
        
        # Accurate path: LLM classification (for important messages)
        if self._should_use_llm(text, lexicon_score):
            llm_sentiment = await self._llm_classify(text, context)
            return self._blend_scores(lexicon_score, llm_sentiment, weights=[0.3, 0.7])
        
        return lexicon_score
    
    async def analyze_conversation(
        self, 
        messages: List[Message]
    ) -> ConversationSentiment:
        """
        Analyze sentiment trajectory across a conversation.
        """
        sentiments = []
        for msg in messages:
            s = await self.analyze(msg.content, context=[m.content for m in messages[-3:]])
            sentiments.append(s)
        
        return ConversationSentiment(
            overall=self._aggregate(sentiments),
            trajectory=self._compute_trajectory(sentiments),
            turning_points=self._find_turning_points(sentiments),
            peak_positive=max(sentiments, key=lambda s: s.valence),
            peak_negative=min(sentiments, key=lambda s: s.valence)
        )
    
    def _compute_trajectory(self, sentiments: List[Sentiment]) -> Trajectory:
        """Determine if conversation is improving, declining, or stable."""
        if len(sentiments) < 3:
            return Trajectory.INSUFFICIENT_DATA
        
        first_half = sentiments[:len(sentiments)//2]
        second_half = sentiments[len(sentiments)//2:]
        
        first_avg = sum(s.valence for s in first_half) / len(first_half)
        second_avg = sum(s.valence for s in second_half) / len(second_half)
        
        diff = second_avg - first_avg
        
        if diff > 0.2:
            return Trajectory.IMPROVING
        elif diff < -0.2:
            return Trajectory.DECLINING
        else:
            return Trajectory.STABLE
```

### Sentiment-Aware Responses

```python
# Example: Adapt response based on detected frustration
if sentiment.frustration > 0.7:
    response_tone = "empathetic_supportive"
elif sentiment.confusion > 0.6:
    response_tone = "clear_step_by_step"
elif sentiment.satisfaction > 0.8:
    response_tone = "friendly_celebratory"
```

---

## Embedding Memory

### Purpose
Enable semantic search and retrieval of memories based on meaning, not just keywords.

### Architecture

```python
class EmbeddingMemory:
    """
    Vector-based semantic memory using embeddings.
    """
    
    def __init__(self, embedding_model: str = "local"):
        self.embedder = EmbeddingProvider(model=embedding_model)
        self.vector_store = VectorStore(dimensions=384)  # Local model dims
        self.metadata_index = MetadataIndex()
    
    async def remember(
        self, 
        content: str, 
        metadata: Dict = None
    ) -> MemoryEntry:
        """
        Store memory with its embedding vector.
        """
        # Generate embedding
        embedding = await self.embedder.embed(content)
        
        # Create entry
        entry = MemoryEntry(
            id=uuid(),
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            timestamp=now()
        )
        
        # Store in vector DB
        await self.vector_store.upsert(entry.id, embedding)
        self.metadata_index.store(entry.id, entry)
        
        return entry
    
    async def recall(
        self, 
        query: str, 
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[MemoryEntry]:
        """
        Retrieve memories semantically similar to query.
        """
        # Embed query
        query_embedding = await self.embedder.embed(query)
        
        # Vector search
        candidates = await self.vector_store.search(
            query_embedding, 
            top_k=top_k * 2  # Over-fetch for re-ranking
        )
        
        # Filter by similarity threshold
        filtered = [
            c for c in candidates 
            if c.similarity >= min_similarity
        ]
        
        # Re-rank with metadata (recency, importance)
        reranked = self._rerank(filtered, query)
        
        return reranked[:top_k]
    
    async def recall_with_context(
        self,
        query: str,
        context_memories: List[str] = None,
        top_k: int = 5
    ) -> List[MemoryEntry]:
        """
        Recall with conversational context for better relevance.
        """
        # Embed query + context
        if context_memories:
            combined = f"{query}\n\nContext: {' | '.join(context_memories[-3:])}"
        else:
            combined = query
        
        return await self.recall(combined, top_k=top_k)
```

### Hybrid Retrieval

```python
class HybridMemoryRetriever:
    """
    Combines keyword, embedding, and structured retrieval.
    """
    
    async def retrieve(
        self, 
        query: str,
        strategies: List[RetrievalStrategy] = None
    ) -> List[MemoryEntry]:
        """
        Retrieve memories using multiple strategies and merge results.
        """
        strategies = strategies or [
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.EMBEDDING,
            RetrievalStrategy.TEMPORAL
        ]
        
        all_results = []
        
        if RetrievalStrategy.KEYWORD in strategies:
            keyword_results = await self.keyword_search(query)
            all_results.extend(self._score_keyword(keyword_results))
        
        if RetrievalStrategy.EMBEDDING in strategies:
            embedding_results = await self.embedding_recall(query)
            all_results.extend(self._score_embedding(embedding_results))
        
        if RetrievalStrategy.TEMPORAL in strategies:
            temporal_results = await self.temporal_recall(query)
            all_results.extend(self._score_temporal(temporal_results))
        
        # Merge and deduplicate
        merged = self._reciprocal_rank_fusion(all_results)
        
        return merged
```

---

## Integration Points

### 1. Working Memory Integration

```python
# In working_memory skill, add embedding support
class WorkingMemorySkill:
    async def get_context(self, limit: int = 20) -> List[MemoryItem]:
        # Existing: weighted by recency/importance/access
        base_results = await self._weighted_retrieval(limit)
        
        # New: semantic augmentation
        if self.embedding_memory:
            query = self._assemble_query_from_recent()
            semantic_results = await self.embedding_memory.recall(query, top_k=limit//2)
            base_results = self._merge_results(base_results, semantic_results)
        
        return base_results
```

### 2. Cognition Integration

```python
# In cognition.py, add pattern/sentiment tracking
class Cognition:
    async def process_message(self, message: Message):
        # Existing processing
        
        # New: sentiment analysis
        sentiment = await self.sentiment_analyzer.analyze(message.content)
        await self.working_memory.remember(
            key=f"sentiment:{message.id}",
            value=sentiment.to_dict(),
            category="sentiment_tracking"
        )
        
        # New: pattern detection (periodic)
        if self._should_run_pattern_detection():
            patterns = await self.pattern_recognizer.analyze(
                await self.working_memory.get_recent(50)
            )
            for pattern in patterns:
                if pattern.confidence > 0.7:
                    await self.flag_pattern(pattern)
```

### 3. Skill Integration

```python
# New skill: aria-advanced-memory
# Combines all four subsystems into unified interface

class AdvancedMemorySkill(BaseSkill):
    """
    Unified interface for compression, patterns, sentiment, and embeddings.
    """
    
    tools = [
        "compress_memories",
        "detect_patterns", 
        "analyze_sentiment",
        "semantic_search",
        "get_memory_insights"
    ]
```

---

## Bug Fix: Session Protection

### Issue
The `session_manager` skill can delete ANY session, including the main agent session. This is dangerous because:
- Deletes current conversation context
- Breaks continuity
- Could lose in-progress work

### Fix
Add protection in `session_manager/__init__.py`:

```python
async def delete_session(
    self, 
    session_id: str = "", 
    agent: str = "", 
    **kwargs
) -> SkillResult:
    """
    Delete a session with protection for main session.
    """
    if not session_id:
        session_id = kwargs.get("session_id", "")
    if not session_id:
        return SkillResult.fail("session_id is required")
    
    # ðŸ›¡ï¸ PROTECTION: Prevent deleting main agent session
    current_session_id = self._get_current_session_id()
    if session_id == current_session_id:
        return SkillResult.fail(
            f"Cannot delete current session {session_id}: "
            "This would destroy the active conversation context. "
            "Use 'cleanup_after_delegation' for sub-agents instead."
        )
    
    # ðŸ›¡ï¸ PROTECTION: Prevent deleting main agent by label
    if self._is_main_agent_session(session_id, agent):
        return SkillResult.fail(
            f"Session {session_id} is the main agent session. "
            "Deletion blocked to preserve context."
        )
    
    # ... rest of delete logic

def _get_current_session_id(self) -> Optional[str]:
    """Get current session ID from environment/context."""
    # Option 1: From environment variable set by Aria Engine
    return os.environ.get("Aria Engine_SESSION_ID")
    
    # Option 2: From context (if available)
    # return self._config.context.get("session_id")

def _is_main_agent_session(self, session_id: str, agent: str) -> bool:
    """Check if session is the main agent session."""
    # If agent is explicitly specified as main
    if agent == "main":
        return True
    
    # Check if session key contains main agent markers
    index = _load_sessions_index(agent or "main")
    for key, value in index.items():
        if isinstance(value, dict) and value.get("sessionId") == session_id:
            # Main sessions don't have :cron: or :subagent: markers
            if ":cron:" not in key and ":subagent:" not in key and ":run:" not in key:
                return True
    
    return False
```

### Additional Protection: Confirmation for Bulk Operations

```python
async def prune_sessions(
    self,
    max_age_minutes: int = 0,
    dry_run: bool = False,
    **kwargs,
) -> SkillResult:
    """
    Prune stale sessions with protection for active main session.
    """
    # ... existing logic ...
    
    # ðŸ›¡ï¸ FILTER: Never prune current session
    current_session_id = self._get_current_session_id()
    to_delete = [
        s for s in to_delete 
        if s.get("sessionId") != current_session_id
    ]
    
    # ... rest of logic
```

---

## Implementation Priority

1. **Session Protection Fix** (Critical) â€” 15 min
2. **Memory Compression** â€” 1 hour
3. **Sentiment Analysis** â€” 45 min
4. **Pattern Recognition** â€” 1 hour
5. **Embedding Memory** â€” 2 hours (depends on vector DB setup)

---

## Next Steps

When you return from work:
1. Review this document
2. Check the prototype files in `/app/prototypes/`
3. Start with session protection fix (critical bug)
4. Implement memory compression first (highest impact)
5. Test each component incrementally

**Questions?** I'll be here when you get back. âš¡ï¸
