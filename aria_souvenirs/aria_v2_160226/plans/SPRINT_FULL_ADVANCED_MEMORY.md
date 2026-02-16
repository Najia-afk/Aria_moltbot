# Sprint Plan: Full Advanced Memory Implementation
## Branch: `dev/aria-v2-160226-full`
## Date: 2026-02-16

---

## Objective

Replace simplified stub implementations of 4 advanced memory subsystems
with full production-grade engines adapted from the prototype files.

The previous sprint created thin wrappers (126-138 lines each) that only
delegated to `api_client`. This sprint delivers the **real engines** with
full scoring, compression, multi-dimensional analysis, pattern detection,
and RRF search — all properly integrated into the 5-layer architecture.

---

## Architecture Constraint (5-Layer)

```
PostgreSQL + pgvector
    ↕
SQLAlchemy ORM (src/api/db/models.py)
    ↕
FastAPI API (src/api/routers/*.py)
    ↕
api_client (aria_skills/api_client/)
    ↕
Skills (aria_skills/)
    ↕
ARIA Mind (aria_mind/cognition.py)
```

Skills NEVER import SQLAlchemy or make raw SQL. All DB access flows
through `api_client` → FastAPI → ORM.

---

## Deliverables

### 1. Memory Compression (`aria_skills/memory_compression/`)
- **Lines**: ~370 (was 126)
- **Components**: ImportanceScorer, MemoryCompressor, CompressionManager, MemoryCompressionSkill
- **Tools**: compress_memories, compress_session, get_context_budget, get_compression_stats
- **Key Features**:
  - 3-tier pipeline: raw (20) → recent (100) → archive (all older)
  - Importance scoring: recency × significance × category × length
  - LLM summarization via LiteLLM (kimi model) with rule-based fallback
  - Compressed summaries stored in semantic memory (`compressed_recent`, `compressed_archive`)
  - Token savings estimation

### 2. Sentiment Analysis (`aria_skills/sentiment_analysis/`)
- **Lines**: ~420 (was 129)
- **Components**: SentimentLexicon, LLMSentimentClassifier, SentimentAnalyzer, ConversationAnalyzer, ResponseTuner
- **Tools**: analyze_message, analyze_conversation, get_tone_recommendation, get_sentiment_history
- **Key Features**:
  - Multi-dimensional: valence, arousal, dominance
  - Derived metrics: frustration, satisfaction, confusion
  - Multi-strategy blend: fast lexicon (30%) + LLM (70%) when ambiguous
  - Conversation trajectory: improving/declining/stable
  - Volatility, turning points, peak detection
  - 4 adaptive tone profiles (empathetic, step-by-step, celebratory, neutral)
  - **Bug fix**: prototype line 457 `len(mentions)` → `len(sentiments)`

### 3. Pattern Recognition (`aria_skills/pattern_recognition/`) — NEW
- **Lines**: ~370
- **Components**: TopicExtractor, FrequencyTracker, PatternRecognizer
- **Tools**: detect_patterns, get_recurring, get_emerging, get_pattern_stats
- **Key Features**:
  - 5 pattern types: topic recurrence, temporal, sentiment drift, interest emergence, knowledge gap
  - Multi-method topic extraction: keywords (9 domains), entity regex, category mapping
  - Sliding window frequency tracking (configurable, default 30 days)
  - Emergence detection via growth rate analysis (recent vs historical frequency)
  - Temporal patterns: peak hours, active days of week
  - Knowledge gap detection: repeated questions over time
  - Auto-storage of detected patterns in semantic memory

### 4. Unified Search (`aria_skills/unified_search/`)
- **Lines**: ~300 (was 138)
- **Components**: RRFMerger, SemanticBackend, GraphBackend, MemoryBackend, UnifiedSearchSkill
- **Tools**: search, semantic_search, graph_search, memory_search
- **Key Features**:
  - Reciprocal Rank Fusion (RRF) with k=60
  - 3 backends: semantic (pgvector cosine), graph (ILIKE), memory (text)
  - Configurable weights (semantic=1.0, graph=0.8, memory=0.6)
  - Content-hash deduplication across backends
  - Backend selection per query

### 5. API Router (`src/api/routers/analysis.py`) — NEW
- **Endpoints**:
  - `POST /analysis/sentiment/message` — Single message sentiment
  - `POST /analysis/sentiment/conversation` — Full conversation analysis
  - `GET /analysis/sentiment/history` — Stored sentiment events
  - `POST /analysis/patterns/detect` — Run pattern detection
  - `GET /analysis/patterns/history` — Stored patterns
  - `POST /analysis/compression/run` — Compress memories
  - `GET /analysis/compression/history` — Stored compressions
- Registered in `src/api/main.py`

### 6. Web Dashboard (`src/web/templates/patterns.html`) — NEW
- Chart.js doughnut (patterns by type) + bar (confidence distribution)
- Stats grid: total, topic, temporal, emerging, gap counts
- Pattern list with color-coded type indicators
- "Run Detection" button triggers API
- Added to nav menu in `base.html`

### 7. Cognition Integration (`aria_mind/cognition.py`)
- Sentiment analysis hooked into `process()` at Step 2.1
- Injects `user_sentiment`, `derived_sentiment`, `tone_recommendation` into context
- Graceful degradation: sentiment skipped if module unavailable

### 8. Tests (`tests/test_advanced_memory.py`)
- 34 tests, all passing
- Covers: ImportanceScorer, MemoryCompressor, CompressionManager, SentimentLexicon,
  Sentiment derived metrics, SentimentAnalyzer, ConversationAnalyzer, ResponseTuner,
  TopicExtractor, FrequencyTracker, PatternRecognizer, RRFMerger, SearchResult,
  Skill initialization for all 3 skills

---

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `aria_skills/memory_compression/__init__.py` | Replaced | ~370 |
| `aria_skills/sentiment_analysis/__init__.py` | Replaced | ~420 |
| `aria_skills/pattern_recognition/__init__.py` | Created | ~370 |
| `aria_skills/unified_search/__init__.py` | Replaced | ~300 |
| `src/api/routers/analysis.py` | Created | ~340 |
| `src/api/main.py` | Modified | +2 lines |
| `src/web/templates/patterns.html` | Created | ~240 |
| `src/web/templates/base.html` | Modified | +3 lines |
| `src/web/app.py` | Modified | +4 lines |
| `aria_mind/cognition.py` | Modified | +30 lines |
| `tests/test_advanced_memory.py` | Created | ~280 |

---

## Status: COMPLETE

All subsystems implemented, tested, and integrated.
Ready for Docker rebuild and production validation.
