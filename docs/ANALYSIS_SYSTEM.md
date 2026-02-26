# Aria Analysis System — Sentiment, Patterns, Compression

> Documentation of Aria's cognitive analysis subsystem: sentiment analysis, behavioral pattern recognition, and memory compression.

---

## Overview

The Analysis subsystem provides three complementary cognitive capabilities:

| Component | Skill | Purpose |
|-----------|-------|---------|
| **Sentiment Analysis** | `sentiment_analysis` | Multi-dimensional emotional analysis (valence, arousal, dominance) |
| **Pattern Recognition** | `pattern_recognition` | Behavioral pattern detection in memory streams |
| **Memory Compression** | `memory_compression` | Hierarchical memory compression for token efficiency |

All three are L3 Domain Skills that access data via `api_client` → FastAPI → PostgreSQL. The REST API facade is in `src/api/routers/analysis.py` (2004 lines, 17 endpoints).

---

## Architecture

```
┌──────────── Analysis Subsystem ──────────────────────────────┐
│                                                               │
│  Dashboard Templates                                          │
│    ├── sentiment.html    ← Sentiment charts & timeline        │
│    └── patterns.html     ← Pattern detection results          │
│                                                               │
│  REST API: src/api/routers/analysis.py (17 endpoints)         │
│    ├── /analysis/sentiment/*    (11 endpoints)                │
│    ├── /analysis/patterns/*     (2 endpoints)                 │
│    ├── /analysis/compression/*  (3 endpoints)                 │
│    └── /analysis/seed-memories  (1 endpoint)                  │
│                                                               │
│  Skills (aria_skills/)                                        │
│    ├── sentiment_analysis/   (962 lines)                      │
│    ├── pattern_recognition/  (640 lines)                      │
│    └── memory_compression/   (527 lines)                      │
│                                                               │
│  Storage                                                      │
│    ├── PostgreSQL: SentimentEvent, SemanticMemory tables       │
│    └── pgvector embeddings via LiteLLM (nomic-embed-text)     │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Sentiment Analysis

### Skill: `aria_skills/sentiment_analysis/`

**Class:** `SentimentAnalysisSkill` (962 lines)  
**Model:** Multi-dimensional VAD (Valence-Arousal-Dominance)

#### Three Dimensions

| Dimension | Range | Description |
|-----------|-------|-------------|
| **Valence** | -1.0 to +1.0 | Negative ↔ Positive |
| **Arousal** | 0.0 to 1.0 | Calm ↔ Excited |
| **Dominance** | 0.0 to 1.0 | Submissive ↔ Dominant |

#### Derived Metrics

| Metric | Formula | Meaning |
|--------|---------|---------|
| **Frustration** | high arousal × negative valence | User is upset and agitated |
| **Satisfaction** | positive valence × high dominance | User is pleased and confident |
| **Confusion** | low dominance × neutral valence | User is uncertain |

#### Conversation-Level Analytics

| Metric | Description |
|--------|-------------|
| **Trajectory** | Improving / Declining / Stable / Insufficient data |
| **Volatility** | Standard deviation of valence across messages |
| **Turning points** | Significant sentiment shift moments |
| **Resolution** | Final conversation sentiment state |

#### Adaptive Response Tuner

Selects tone profile based on current sentiment state:
- High frustration → empathetic, patient tone
- High satisfaction → matching enthusiasm
- High confusion → clear, structured responses

### Key Functions

| Function | Description |
|----------|-------------|
| `analyze_message()` | Analyze single message → Sentiment (valence, arousal, dominance) |
| `analyze_conversation()` | Aggregate analysis → ConversationSentiment with trajectory |
| `generate_reply_recommendation()` | Suggest response tone based on sentiment |
| `get_sentiment_history()` | Retrieve historical sentiment events |

---

## Pattern Recognition

### Skill: `aria_skills/pattern_recognition/`

**Class:** `PatternRecognitionSkill` (640 lines)

#### Pattern Types

| Type | Description |
|------|-------------|
| `TOPIC_RECURRENCE` | Subjects that come up repeatedly |
| `TEMPORAL_PATTERN` | Time-based activity clusters (e.g., morning coding sessions) |
| `SENTIMENT_DRIFT` | Emotional trend changes over time |
| `INTEREST_EMERGENCE` | New topics gaining frequency |
| `KNOWLEDGE_GAP` | Repeated questions on same subject |
| `BEHAVIOR_CYCLE` | Cyclic behavioral patterns |

#### Pipeline

```
1. Extract topics from memories (keyword + entity + category)
      ↓
2. Track frequency over sliding time windows
      ↓
3. Statistical pattern detection (threshold-based)
      ↓
4. Optional LLM augmentation for semantic patterns
      ↓
5. Store detected patterns in semantic memory via api_client
```

### Key Functions

| Function | Description |
|----------|-------------|
| `detect_patterns()` | Run full pattern detection pipeline on memory stream |
| `get_pattern_history()` | Retrieve previously detected patterns |
| `extract_topics()` | Extract topic mentions from memory entries |

---

## Memory Compression

### Skill: `aria_skills/memory_compression/`

**Class:** `MemoryCompressionSkill` (527 lines)  
**Model:** Uses primary LLM from `aria_models/models.yaml` (default: kimi)

#### Three-Tier Compression

| Tier | Scope | Compression | Description |
|------|-------|-------------|-------------|
| **Raw** | Last 20 messages | 0% (verbatim) | High-value recent messages preserved exactly |
| **Recent** | Last 100 messages | ~30% | Compressed summaries retaining key facts |
| **Archive** | Everything older | ~10% | Heavily compressed, only essential knowledge |

**Result:** 70%+ token reduction while preserving key facts, decisions, and user preferences.

#### Importance Scoring

Messages are scored by importance before compression:
- User preferences and decisions → high importance
- System/cron messages → low importance
- Emotional/personal content → medium-high importance
- Routine operational messages → low importance

### Key Functions

| Function | Description |
|----------|-------------|
| `compress_session()` | Compress memories from a time window |
| `compress_all()` | Run full three-tier compression pipeline |
| `get_compression_stats()` | Get compression metrics and token savings |

---

## REST API Endpoints

**Router:** `src/api/routers/analysis.py`  
**Prefix:** `/analysis`  
**Tags:** `Analysis`

### Sentiment Endpoints (11)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sentiment/message` | Analyze single message sentiment |
| POST | `/sentiment/backfill-sessions` | Backfill sentiment for engine chat sessions |
| POST | `/sentiment/conversation` | Analyze full conversation sentiment |
| POST | `/sentiment/reply` | Generate sentiment-aware reply recommendation |
| POST | `/sentiment/backfill-messages` | Backfill sentiment from legacy JSONL messages |
| GET | `/sentiment/history` | Query sentiment event history with filters |
| GET | `/sentiment/score` | Get aggregate sentiment score/stats |
| POST | `/sentiment/seed-references` | Seed reference sentiment calibration data |
| POST | `/sentiment/feedback` | Submit human feedback on sentiment accuracy |
| POST | `/sentiment/auto-promote` | Auto-promote high-confidence sentiment results |
| POST | `/sentiment/cleanup-placeholders` | Remove placeholder sentiment entries |

### Pattern Endpoints (2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/patterns/detect` | Run pattern detection on memory stream |
| GET | `/patterns/history` | Query detected pattern history |

### Compression Endpoints (3)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/compression/run` | Run memory compression pipeline |
| GET | `/compression/history` | Query compression operation history |
| POST | `/compression/auto-run` | Auto-run compression based on memory volume |

### Utility Endpoints (1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/seed-memories` | Seed semantic memories for analysis calibration |

---

## Noise Filtering

The analysis router includes sophisticated noise filtering to prevent system/cron messages from contaminating sentiment data:

- **Attribution stripping**: Removes gateway prefixes (`[Telegram ...]`, `[Mon 2026-...]`, `System: [...]`)
- **Test data detection**: Filters dummy/lorem/placeholder text
- **Cron/system detection**: Excludes automated prompts (`read heartbeat.md`, `cron:`, `/no_think`)
- **Transcript detection**: Identifies and handles pasted conversation transcripts
- **Minimum character threshold**: Filters very short/empty messages

---

## Embedding Generation

Semantic analysis uses vector embeddings generated via LiteLLM:
- **Model:** `nomic-embed-text` (via Ollama/LiteLLM)
- **Storage:** pgvector columns in SemanticMemory table
- **Timeout:** 5s with zero-vector fallback
- **Endpoint:** `LITELLM_URL/v1/embeddings`

---

## Dashboard Pages

### sentiment.html
- Sentiment timeline chart (Chart.js)
- Valence/arousal/dominance breakdown
- Conversation trajectory visualization
- Turning point markers
- Feedback submission interface

### patterns.html
- Detected pattern listing with confidence scores
- Pattern type grouping
- Temporal heatmaps
- Topic recurrence frequency charts

---

## Integration Points

| System | Integration |
|--------|-------------|
| **Working Memory** | Sentiment context injected into active sessions |
| **Heartbeat** | Periodic sentiment and pattern analysis in cron cycles |
| **Knowledge Graph** | Patterns stored as KG entities for cross-referencing |
| **Response Tuning** | Sentiment drives adaptive response tone selection |
| **Memory Consolidation** | Compression reduces token usage in long sessions |

---

*Part of Aria's L3 Domain Skills layer. All DB access via api_client → FastAPI → SQLAlchemy → PostgreSQL.*
