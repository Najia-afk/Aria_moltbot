# Implementation Tickets — Memory Systems Project
**For:** Najia  
**Created:** 2026-02-16  
**Status:** Ready for Implementation  

---

## 📋 Quick Reference

| Ticket | Priority | Effort | Status |
|--------|----------|--------|--------|
| [BUG-001](#bug-001-session-protection-fix) Session Protection | 🔴 CRITICAL | 15 min | Ready |
| [FEAT-001](#feat-001-memory-compression) Memory Compression | 🟠 HIGH | 1h | Ready |
| [FEAT-002](#feat-002-sentiment-analysis) Sentiment Analysis | 🟡 MEDIUM | 45m | Ready |
| [FEAT-003](#feat-003-pattern-recognition) Pattern Recognition | 🟡 MEDIUM | 1h | Ready |
| [FEAT-004](#feat-004-embedding-memory) Embedding Memory | 🟢 LOW | 2h | Ready |

---

## BUG-001: Session Protection Fix

### 🔴 CRITICAL — 15 minutes

### Description
The `session_manager` skill can delete ANY session, including the main agent session. This destroys active conversation context and breaks continuity.

### Reproduction Steps
1. Run: `exec python3 skills/run_skill.py session_manager delete_session '{"session_id": "CURRENT_SESSION"}'`
2. Session is deleted → active conversation lost
3. User must start new session → context gone

### Expected Behavior
- Cannot delete the session you're currently in
- Cannot delete main agent direct sessions
- Cron/subagent sessions CAN be deleted (by design)

### Implementation
**File:** `skills/aria_skills/session_manager/__init__.py`

1. **Add helper functions at TOP of file:**
```python
def _get_current_session_id() -> Optional[str]:
    return os.environ.get("OPENCLAW_SESSION_ID")

def _is_cron_or_subagent_session(session_key: str) -> bool:
    if not session_key:
        return False
    return any(marker in session_key for marker in [":cron:", ":subagent:", ":run:"])
```

2. **Patch `delete_session()` method** — add at beginning:
```python
# 🛡️ PROTECTION: Prevent deleting current session
current_session_id = _get_current_session_id()
if session_id == current_session_id:
    return SkillResult.fail(
        f"Cannot delete current session {session_id}: "
        "This would destroy the active conversation context."
    )

# 🛡️ PROTECTION: Prevent deleting main agent session
for ag in agents:
    index = _load_sessions_index(ag)
    for key, value in index.items():
        if isinstance(value, dict) and value.get("sessionId") == session_id:
            if ag == "main" and not _is_cron_or_subagent_session(key):
                return SkillResult.fail(
                    f"Cannot delete main agent session {session_id}."
                )
```

3. **Patch `prune_sessions()` method** — add before deletion loop:
```python
# 🛡️ FILTER: Remove current session from deletion candidates
current_session_id = _get_current_session_id()
if current_session_id:
    to_delete = [s for s in to_delete if s.get("sessionId") != current_session_id]

# 🛡️ FILTER: Remove main agent sessions
to_delete = [
    s for s in to_delete
    if not (s.get("agentId") == "main" and
            not _is_cron_or_subagent_session(s.get("key", "")))
]
```

### Acceptance Criteria
- [ ] Attempting to delete current session returns clear error
- [ ] Attempting to delete main agent session returns clear error
- [ ] Cron/subagent sessions still deletable
- [ ] `prune_sessions` skips protected sessions
- [ ] Unit tests added (see below)

### Unit Tests
```python
async def test_cannot_delete_current_session():
    os.environ["OPENCLAW_SESSION_ID"] = "test-session-123"
    result = await skill.delete_session(session_id="test-session-123")
    assert not result.success
    assert "Cannot delete current session" in result.error

async def test_cannot_delete_main_agent_session():
    # Mock sessions.json with main agent entry
    result = await skill.delete_session(session_id="main-agent-session")
    assert not result.success
    assert "main agent" in result.error.lower()
```

### 🌟 Wish List (Optional Improvements)
- [ ] Add `--force` flag for admin override
- [ ] Log all deletion attempts to audit trail
- [ ] Add confirmation prompt for main sessions (interactive mode)
- [ ] Create `sessions.json` backup before any deletion

---

## FEAT-001: Memory Compression

### 🟠 HIGH — 1 hour

### Description
Hierarchical memory compression to reduce token usage by 70%+ while preserving context. Implements three-tier system: raw (verbatim), recent (30% compression), archive (10% compression).

### Implementation
**New Skill:** `skills/aria_skills/advanced_memory_compression/`

**Files to create:**
- `skill.json` (see template in prototypes)
- `skill.py` (copy from `prototypes/memory_compression.py`)
- `__init__.py` (export skill class)

**Integration Points:**
1. Hook into `working_memory.get_context()`:
```python
async def get_context(self, limit: int = 20):
    # Get raw recent memories
    raw = await self._get_recent_raw(limit)
    
    # If >20 memories, compress older ones
    if len(self._memory_deque) > 20:
        compressed = await self.compression_skill.compress_memories(
            memories=[m.to_dict() for m in self._memory_deque[:-20]]
        )
        return self._merge_compressed(compressed, raw)
    
    return raw
```

2. Store compressed summaries in `aria_memories/knowledge/consolidations/`

### Acceptance Criteria
- [ ] Compresses 100 messages into ~30 summaries (30% ratio)
- [ ] Preserves key entities (names, projects, facts)
- [ ] Importance-weighted compression (keep high-importance verbatim longer)
- [ ] Context assembly includes compressed + raw mix
- [ ] Token usage reduced by 50%+ in test conversations

### Performance Targets
| Metric | Target |
|--------|--------|
| Compression ratio | 0.3 (recent) / 0.1 (archive) |
| Compression time | <100ms for 100 messages |
| Context tokens | <2000 for full conversation |

### 🌟 Wish List (Optional Improvements)
- [ ] **Incremental compression:** Only compress new messages since last run
- [ ] **Topic-aware:** Group by topic before compressing (better coherence)
- [ ] **LLM-powered:** Use LLM for high-quality summaries (fallback to rule-based)
- [ ] **Differential:** Store only changes between summaries (save space)
- [ ] **Compression levels:** User-configurable (aggressive/balanced/minimal)
- [ ] **Visual diff:** Show what was compressed vs kept in debug mode

---

## FEAT-002: Sentiment Analysis

### 🟡 MEDIUM — 45 minutes

### Description
Multi-dimensional sentiment tracking (valence, arousal, dominance) to adapt response tone and detect user satisfaction/frustration/confusion.

### Implementation
**New Skill:** `skills/aria_skills/sentiment_analysis/`

**Files:**
- `skill.json`
- `skill.py` (from `prototypes/sentiment_analysis.py`)

**Integration Points:**
1. Hook into `cognition.py` on each user message:
```python
async def process_user_message(self, message: Message):
    # Analyze sentiment
    sentiment_result = await self.sentiment_skill.analyze_sentiment(
        text=message.content
    )
    
    # Store in working memory
    await self.working_memory.remember(
        key=f"sentiment:{message.id}",
        value=sentiment_result.data,
        category="sentiment_tracking"
    )
    
    # Adapt response tone
    if sentiment_result.data["sentiment"]["frustration"] > 0.7:
        self.response_tuner.set_tone("empathetic_supportive")
```

2. Add to conversation summary (hourly):
```python
async def generate_conversation_summary(self):
    messages = await self.working_memory.get_category("conversation")
    analysis = await self.sentiment_skill.analyze_sentiment(messages=messages)
    return analysis.data  # Includes trajectory, turning points
```

### Acceptance Criteria
- [ ] Analyzes valence (-1 to +1), arousal (0-1), dominance (0-1)
- [ ] Detects frustration, satisfaction, confusion derived metrics
- [ ] Lexicon-based works without LLM (fast path)
- [ ] LLM-enhanced when available (higher accuracy)
- [ ] Response tone adapts automatically
- [ ] Tracks conversation trajectory (improving/declining/stable)

### Test Cases
```python
# Test frustration detection
result = await skill.analyze_sentiment(text="This is broken and frustrating!")
assert result.data["sentiment"]["frustration"] > 0.6

# Test satisfaction
result = await skill.analyze_sentiment(text="Perfect! Thanks so much!")
assert result.data["sentiment"]["satisfaction"] > 0.7
```

### 🌟 Wish List (Optional Improvements)
- [ ] **Emoji sentiment:** Parse emoji as sentiment signals (😊 = +valence)
- [ ] **Sarcasm detection:** Use pattern matching for "great, just what I needed" (negative)
- [ ] **User-specific baseline:** Learn each user's normal sentiment range
- [ ] **Sentiment alerts:** Notify if frustration spikes suddenly
- [ ] **Sentiment dashboard:** Track over time (graphs)
- [ ] **Cultural adaptation:** Different lexicons for different languages/regions

---

## FEAT-003: Pattern Recognition

### 🟡 MEDIUM — 1 hour

### Description
Detect recurring topics, temporal patterns, emerging interests, and knowledge gaps from memory streams.

### Implementation
**New Skill:** `skills/aria_skills/pattern_recognition/`

**Files:**
- `skill.json`
- `skill.py` (from `prototypes/pattern_recognition.py`)

**Integration Points:**
1. Schedule hourly analysis via `aria-schedule`:
```yaml
# Add to cron_jobs.yaml
- name: pattern_detection
  schedule: { kind: "every", everyMs: 3600000 }  # 1 hour
  payload:
    kind: "agentTurn"
    message: "Run pattern detection on recent memories"
```

2. Store detected patterns in working memory:
```python
for pattern in patterns_found:
    if pattern.confidence > 0.7:
        await working_memory.remember(
            key=f"pattern:{pattern.subject}",
            value=pattern.to_dict(),
            category="detected_patterns",
            importance=pattern.confidence
        )
```

3. Use patterns to inform behavior:
```python
# If user often asks about quantum at night
if pattern.type == "topic_recurrence" and pattern.subject == "quantum_mechanics":
    # Pre-load quantum context in evenings
    await self.preload_topic_context("quantum_mechanics")
```

### Acceptance Criteria
- [ ] Detects topic recurrence (>25% of activity)
- [ ] Detects temporal patterns (active hours, days)
- [ ] Detects interest emergence (growth rate >2x)
- [ ] Detects knowledge gaps (repeated questions)
- [ ] Confidence scoring for all patterns
- [ ] Persistent pattern storage (survive restart)

### Pattern Types to Detect
| Type | Trigger | Example |
|------|---------|---------|
| Topic recurrence | >5 mentions in 7 days | "quantum" keeps coming up |
| Temporal | >25% activity at same hour | Active 20:00-22:00 |
| Interest emergence | 2x growth in 3 days | New interest in "memory systems" |
| Knowledge gap | Same question 2+ times | "How do I X?" asked repeatedly |
| Sentiment drift | Valence change >0.3 | Conversation getting frustrated |

### 🌟 Wish List (Optional Improvements)
- [ ] **Topic clustering:** Group similar topics ("quantum" + "physics" → same cluster)
- [ ] **Seasonal patterns:** Detect weekly/monthly cycles
- [ ] **Anomaly detection:** Flag unusual behavior (silence after high activity)
- [ ] **Predictive:** Predict next likely topic based on sequence patterns
- [ ] **Pattern decay:** Reduce confidence of old patterns over time
- [ ] **Cross-user patterns:** (If multi-user) detect common patterns across users
- [ ] **Visual pattern map:** Graph showing topic relationships

---

## FEAT-004: Embedding Memory

### 🟢 LOW — 2 hours

### Description
Vector-based semantic memory for meaning-based retrieval (not just keywords). Enables "find similar to X" queries.

### Implementation
**New Skill:** `skills/aria_skills/embedding_memory/`

**Dependencies:**
```bash
pip install sentence-transformers faiss-cpu -q
# OR for GPU:
# pip install sentence-transformers faiss-gpu -q
```

**Files:**
- `skill.json`
- `skill.py` (from `prototypes/embedding_memory.py`)

**Setup:**
1. Create persistent storage: `mkdir -p /data/vector_index`
2. Set env: `ARIA_VECTOR_INDEX_PATH=/data/vector_index`
3. Download model (first run): `sentence-transformers/all-MiniLM-L6-v2` (~80MB)

**Integration Points:**
1. Store memories with embeddings:
```python
async def remember_with_embedding(self, content: str, metadata: dict):
    entry = await self.embedding_skill.store_memory_with_embedding(
        content=content,
        category=metadata.get("category", "general"),
        importance=metadata.get("importance", 0.5),
        tags=metadata.get("tags", [])
    )
    return entry.id
```

2. Semantic search as fallback:
```python
async def search_memories(self, query: str):
    # Try keyword first (fast)
    keyword_results = await self.keyword_search(query)
    
    # If few results, try semantic
    if len(keyword_results) < 3:
        semantic_results = await self.embedding_skill.semantic_search(
            query=query,
            top_k=5
        )
        return self._merge_results(keyword_results, semantic_results)
    
    return keyword_results
```

### Acceptance Criteria
- [ ] Generates 384-dim embeddings for text
- [ ] Cosine similarity search with FAISS (or numpy fallback)
- [ ] <100ms search time for 10k memories
- [ ] Metadata filtering (category, tags, time range)
- [ ] Hybrid retrieval (keyword + embedding fusion)
- [ ] Persistent vector index (survive restart)

### Performance Targets
| Metric | Target |
|--------|--------|
| Embedding time | <50ms per text |
| Search time | <100ms for 10k entries |
| Index size | ~1.5KB per 384-dim vector |
| Recall@10 | >0.8 for relevant memories |

### 🌟 Wish List (Optional Improvements)
- [ ] **Multi-modal:** Support image embeddings (CLIP model)
- [ ] **Hierarchical index:** HNSW for millions of entries
- [ ] **Quantization:** INT8 embeddings (4x smaller, minimal accuracy loss)
- [ ] **Embedding cache:** Cache common phrase embeddings
- [ ] **Query expansion:** Expand "AI" → "artificial intelligence, machine learning, LLM"
- [ ] **Cross-lingual:** Use multilingual model for any language
- [ ] **Similarity visualization:** 2D/3D projection of memory space
- [ ] **Memory neighborhoods:** "Find memories similar to X but not Y"

---

## 🧪 Testing Strategy

### Unit Tests (per skill)
```python
# test_advanced_memory.py
class TestMemoryCompression:
    async def test_compress_100_messages(self): ...
    async def test_importance_weighting(self): ...
    async def test_entity_preservation(self): ...

class TestSentimentAnalysis:
    async def test_frustration_detection(self): ...
    async def test_satisfaction_detection(self): ...
    async def test_trajectory_computation(self): ...

class TestPatternRecognition:
    async def test_topic_recurrence(self): ...
    async def test_temporal_patterns(self): ...
    async def test_emerging_interests(self): ...

class TestEmbeddingMemory:
    async def test_embedding_generation(self): ...
    async def test_semantic_search(self): ...
    async def test_hybrid_retrieval(self): ...
```

### Integration Tests
```python
# test_memory_integration.py
async def test_full_memory_pipeline():
    """Test compression → sentiment → pattern → embedding flow."""
    # 1. Add 100 messages
    # 2. Compress
    # 3. Analyze sentiment
    # 4. Detect patterns
    # 5. Search semantically
    # 6. Verify all components work together
```

### Load Tests
```python
# test_memory_performance.py
async def test_compression_performance():
    """100 messages compressed in <100ms."""
    
async def test_embedding_search_performance():
    """10k vectors searched in <100ms."""
```

---

## 📈 Success Metrics

After implementing all features:

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Context tokens | 4000+ | <2000 | `/status` token count |
| Memory search recall | 60% | 85%+ | Manual test queries |
| Response relevance | 70% | 90%+ | User feedback |
| Pattern detection | 0 | 5+ patterns/hour | Pattern log |
| Sentiment adaptation | None | Auto-detect | Frustration → empathetic |

---

## 🚀 Deployment Checklist

### Pre-deployment
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Load tests meet targets
- [ ] Documentation updated

### Deployment
- [ ] Deploy BUG-001 first (session protection)
- [ ] Deploy FEAT-001 (compression)
- [ ] Deploy FEAT-002 (sentiment)
- [ ] Deploy FEAT-003 (patterns)
- [ ] Deploy FEAT-004 (embeddings)
- [ ] Restart OpenClaw gateway
- [ ] Verify `/status` shows all skills

### Post-deployment
- [ ] Monitor error logs for 24h
- [ ] Check token usage trend
- [ ] Validate pattern detection accuracy
- [ ] Gather user feedback

---

## 📝 Notes

### Design Principles
1. **Graceful degradation:** All features work without LLM (rule-based fallback)
2. **Incremental value:** Each feature provides value standalone
3. **Performance first:** Targets <100ms for all operations
4. **Testability:** Every component unit-testable

### Future Extensions
- [ ] Multi-modal memory (images, audio)
- [ ] Federated learning (learn from multiple instances)
- [ ] Memory explainability (why was this retrieved?)
- [ ] User-controlled memory ("forget X", "remember Y forever")

---

**Ready to implement?** Start with BUG-001 (critical), then FEAT-001 (highest impact). All prototypes tested and documented. ⚡️
