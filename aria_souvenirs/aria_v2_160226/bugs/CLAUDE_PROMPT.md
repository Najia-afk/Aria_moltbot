# CLAUDE — Memory Systems Implementation Prompt
## Handoff Document | 2026-02-16

**From:** Aria Blue (Product Owner + Implementation Lead)  
**To:** Claude Code (Senior Software Engineer)  
**Context:** Najia will implement all components. You support the implementation.

---

## 🎯 MISSION

Implement 4 advanced memory subsystems for Aria Blue to improve context management, sentiment awareness, pattern detection, and semantic search. **Critical bug fix required first.**

---

## 📁 SOURCE OF TRUTH

All implementation files are in:
```
/root/.openclaw/workspace/prototypes/
```

**Files (9 total, ~4800 lines):**

| File | Purpose | Status |
|------|---------|--------|
| `MEMORY_SYSTEM_GUIDE.md` | Architecture & technical specs | Ready |
| `README_IMPLEMENTATION.md` | Quick start checklist | Ready |
| `IMPLEMENTATION_TICKETS.md` | 5 detailed tickets with AC | Ready |
| `session_protection_fix.py` | **CRITICAL BUG FIX** | Ready |
| `memory_compression.py` | Hierarchical compression | Ready |
| `sentiment_analysis.py` | Multi-dimensional sentiment | Ready |
| `pattern_recognition.py` | Pattern detection engine | Ready |
| `embedding_memory.py` | Vector semantic search | Ready |
| `advanced_memory_skill.py` | Unified skill class | Ready |

---

## 🔴 CRITICAL: BUG-001 Session Protection

### Problem
`session_manager` skill can delete the main agent session → destroys conversation context.

### Fix Location
`skills/aria_skills/session_manager/__init__.py`

### Implementation (from `session_protection_fix.py`)

1. **Add helper functions at TOP:**
```python
def _get_current_session_id() -> Optional[str]:
    return os.environ.get("OPENCLAW_SESSION_ID")

def _is_cron_or_subagent_session(session_key: str) -> bool:
    if not session_key:
        return False
    return any(marker in session_key for marker in [":cron:", ":subagent:", ":run:"])
```

2. **Patch `delete_session()`** — add after `session_id` validation:
```python
# 🛡️ PROTECTION: Prevent deleting current session
current_session_id = _get_current_session_id()
if session_id == current_session_id:
    return SkillResult.fail(
        f"Cannot delete current session {session_id}: "
        "This would destroy the active conversation context."
    )

# Check if main agent session
for ag in agents:
    index = _load_sessions_index(ag)
    for key, value in index.items():
        if isinstance(value, dict) and v.get("sessionId") == session_id:
            if ag == "main" and not _is_cron_or_subagent_session(key):
                return SkillResult.fail("Cannot delete main agent session.")
```

3. **Patch `prune_sessions()`** — filter before deletion:
```python
# 🛡️ FILTER: Remove protected sessions
current_session_id = _get_current_session_id()
if current_session_id:
    to_delete = [s for s in to_delete if s.get("sessionId") != current_session_id]

to_delete = [
    s for s in to_delete
    if not (s.get("agentId") == "main" and
            not _is_cron_or_subagent_session(s.get("key", "")))
]
```

### Test
```bash
exec python3 skills/run_skill.py session_manager delete_session '{"session_id": "CURRENT"}'
# Should fail with clear error
```

---

## 🟠 FEAT-001: Memory Compression

### Goal
Reduce token usage by 70% using hierarchical compression (raw/recent/archive tiers).

### Implementation Steps

1. **Create skill directory:**
```bash
mkdir -p skills/aria_skills/advanced_memory_compression
```

2. **Create files:**
- `skill.json` — use template from MEMORY_SYSTEM_GUIDE.md
- `skill.py` — copy from `prototypes/memory_compression.py`
- `__init__.py` — export skill class

3. **Register skill:**
Add to `skills/aria_skills/registry.py`:
```python
from aria_skills.advanced_memory_compression import MemoryCompressionSkill
```

4. **Integration:**
Hook into `working_memory.get_context()` to compress old memories automatically.

### Key Classes
- `ImportanceScorer` — scores memories by importance
- `MemoryCompressor` — compresses batches
- `CompressionManager` — manages 3-tier pipeline

### Test
```python
# Compress 100 messages
result = await skill.compress_memories(memories=[...])
assert result["compression_ratio"] < 0.4
```

---

## 🟡 FEAT-002: Sentiment Analysis

### Goal
Track valence/arousal/dominance to adapt response tone.

### Implementation Steps

1. **Create skill:** `skills/aria_skills/sentiment_analysis/`
2. **Copy:** `prototypes/sentiment_analysis.py` → `skill.py`
3. **Register** in registry
4. **Integration:** Hook into `cognition.py` to analyze each user message

### Key Classes
- `SentimentAnalyzer` — main analyzer (lexicon + LLM)
- `ConversationAnalyzer` — trajectory tracking
- `ResponseTuner` — adapts tone based on sentiment

### Derived Metrics
- `frustration` = arousal × |negative valence|
- `satisfaction` = valence × dominance
- `confusion` = (1 - dominance) × neutral valence

---

## 🟡 FEAT-003: Pattern Recognition

### Goal
Detect recurring topics, temporal patterns, emerging interests.

### Implementation Steps

1. **Create skill:** `skills/aria_skills/pattern_recognition/`
2. **Copy:** `prototypes/pattern_recognition.py` → `skill.py`
3. **Register** in registry
4. **Schedule:** Hourly cron job via `aria-schedule`

### Key Classes
- `TopicExtractor` — extracts topics from memories
- `FrequencyTracker` — tracks topic frequencies
- `PatternRecognizer` — detects all pattern types

### Pattern Types
- `TOPIC_RECURRENCE` — topics that come up repeatedly
- `TEMPORAL_PATTERN` — active hours, days
- `INTEREST_EMERGENCE` — new topics with growth
- `KNOWLEDGE_GAP` — repeated questions

---

## 🟢 FEAT-004: Semantic Memory Integration (REVISED)

### ⚠️ IMPORTANT: Use Existing Infrastructure!

**Don't build new embedding system** — `api_client` already provides:
- `store_memory_semantic()` — stores with auto-embedding
- `search_memories_semantic()` — semantic search via pgvector
- `summarize_session()` — session compression

### Implementation Steps

1. **No new dependencies needed!** ✅

2. **Use existing api_client methods:**
```python
# Store with embedding
await api_client.store_memory_semantic(
    content="User likes concise answers",
    category="preference",
    importance=0.9,
    metadata={"tags": ["communication"]}
)

# Semantic search
results = await api_client.search_memories_semantic(
    query="how does user like responses",
    limit=10,
    min_importance=0.5
)
```

3. **Integration only** — create wrapper in `advanced_memory` skill

### Key Methods (from api_client)
- `store_memory_semantic()` — auto-embedding via backend
- `search_memories_semantic()` — pgvector similarity search
- `summarize_session()` — for memory compression

### Backend
- PostgreSQL with pgvector extension
- GraphQL API
- Already deployed and working!

---

## 🧪 TESTING

### Unit Tests (create `tests/test_advanced_memory.py`)
```python
class TestMemoryCompression:
    async def test_compress_100_messages(self): ...
    async def test_importance_weighting(self): ...

class TestSentimentAnalysis:
    async def test_frustration_detection(self): ...
    async def test_satisfaction_detection(self): ...

class TestPatternRecognition:
    async def test_topic_recurrence(self): ...

class TestEmbeddingMemory:
    async def test_embedding_generation(self): ...
    async def test_semantic_search(self): ...
```

### Integration Test
```python
async def test_full_pipeline():
    """Compression → Sentiment → Pattern → Embedding"""
```

---

## 📊 CURRENT SYSTEM STATE

### Active Goals
- **"Clear Moltbook Draft Backlog"** — 85% complete, in `doing` column
- **New goal needed:** "Implement Memory Systems" (suggested)

### System Health
- Sessions: 4 active (target ≤5) ✅
- Health checks: All green ✅
- Work cycles: Running every ~15 min ✅

### Moltbook Status
- **Account suspended** (duplicate_content, offense #1)
- Recovery window: 24-48h (next check: 21:00Z today)
- Pending drafts: 17 (on hold until suspension lifted)

### Recent Activity (Last 6h)
- 100 activities logged
- Consistent work cycle execution
- 6-hour review completed 12:00Z
- Documentation created (this prompt)

---

## 🛠️ DEVELOPMENT WORKFLOW

### How to Test Skills
```bash
# Run skill directly
exec python3 skills/run_skill.py <skill_name> <tool> '<json_args>'

# Example:
exec python3 skills/run_skill.py sentiment_analysis analyze_sentiment '{"text": "Hello!"}'
```

### Skill Structure
```
skills/aria_skills/<skill_name>/
├── skill.json      # Manifest
├── skill.py        # Main implementation
└── __init__.py     # Exports
```

### Registry Registration
Add import to `skills/aria_skills/registry.py`:
```python
from aria_skills.advanced_memory_compression import MemoryCompressionSkill
```

---

## 📝 NOTES FOR IMPLEMENTATION

### Design Principles
1. **Graceful degradation:** All features work without LLM
2. **Incremental value:** Each feature standalone
3. **Performance first:** <100ms operations
4. **Testability:** Unit-testable components

### Common Pitfalls
- **DO NOT** instantiate skills directly — use `run_skill.py`
- **DO NOT** use `aria_mind/` prefix — workspace IS `aria_mind/`
- **DO NOT** write files to workspace — use `aria_memories/`

### Environment Variables
- `OPENCLAW_SESSION_ID` — for session protection
- `ARIA_API_URL` — for API client (semantic memory via api_client)

---

## ✅ IMPLEMENTATION CHECKLIST

### Phase 1: Bug Fix (FIRST)
- [ ] Apply session protection patches
- [ ] Test deletion protection
- [ ] Deploy

### Phase 2: Skills
- [ ] Create `advanced_memory_compression/` skill
- [ ] Create `sentiment_analysis/` skill
- [ ] Create `pattern_recognition/` skill
- [ ] Create `embedding_memory/` skill
- [ ] Register all in `registry.py`

### Phase 3: Integration
- [ ] Hook compression into `working_memory` (use `api_client.summarize_session()`)
- [ ] Hook sentiment into `cognition.py` (store in semantic memory)
- [ ] Schedule pattern detection hourly (use KG + semantic search)
- [ ] Use existing `api_client.search_memories_semantic()` — no setup needed! ✅

### Phase 4: Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Performance targets met

---

## 🆘 SUPPORT

If stuck:
1. Check `IMPLEMENTATION_TICKETS.md` for detailed specs
2. Check `MEMORY_SYSTEM_GUIDE.md` for architecture
3. Reference prototypes — they're working code
4. Test incrementally — one skill at a time

---

## 🎯 SUCCESS CRITERIA

| Metric | Target |
|--------|--------|
| Context tokens | <2000 (from 4000+) |
| Memory search recall | >85% |
| Compression ratio | <0.3 |
| Pattern detection | 5+ patterns/hour |
| Sentiment adaptation | Auto-detect & respond |

---

**Ready to implement. Najia will do the work — you support with code review, debugging, and refinements.**

Good luck! ⚡️

---

## 🧠 BONUS: Sentiment Intelligence System (Najia's Idea)

### Concept
Bidirectional sentiment feedback with reinforcement learning:
1. System analyzes sentiment automatically
2. Stores in session JSONL + generates HTML dashboard
3. User validates/corrects via web interface
4. System learns and improves accuracy over time

### Key Features
- **Per-session HTML report** with sentiment trajectory graph
- **Confidence scores** — system knows when it's uncertain
- **Simple feedback** — radio buttons (correct/partial/wrong)
- **Reinforcement learning** — weight adjustment based on corrections
- **Pattern learning** — "Najia frustrated at 17:00 when debugging"

### Data Flow
```
Session JSONL → Auto Analysis → HTML Dashboard → User Feedback → 
Learning Engine → Updated Weights → Better Next Analysis
```

### Implementation
See `SENTIMENT_INTELLIGENCE_DESIGN.md` for:
- Data models
- HTML dashboard template
- Learning engine algorithm
- Learning metrics tracking

### Effort
- Phase 1 (Basic): 30 min
- Phase 2 (Feedback): 1 hour  
- Phase 3 (Learning): 2 hours
- Phase 4 (Intelligence): Ongoing

### Files
- `sentiment_analyzer_v2.py` — with feedback integration
- `sentiment_dashboard.html` — interactive report
- `learning_engine.py` — RL weight adjustment

**This is next-level personalization — the system learns YOU.**
