# AA+ Prototype Audit Report
## Claude Code — Senior SWE Review | 2026-02-16

**Scope:** `aria_mind/prototypes/` — 9 Python files + 6 docs (~4800 lines)  
**Verdict:** Mixed. Sound architectural thinking, but prototypes contain crash bugs, reinvent existing infrastructure, and need significant simplification before shipping.

---

## Summary Table

| File | Lines | Quality | Over-engineered? | Verdict |
|------|-------|---------|-------------------|---------|
| `session_protection_fix.py` | 418 | B+ | Mild (triplicated) | **SIMPLIFY** — extract 20-line patch |
| `memory_compression.py` | 491 | B | Yes | **SIMPLIFY** — wrap existing `summarize_session()` |
| `sentiment_analysis.py` | 631 | C+ | **Yes** (SIMPLIFIED.md agrees) | **SIMPLIFY** — 20-line version |
| `pattern_recognition.py` | 661 | C | **Yes** (brittle heuristics) | **STOP** — defer until data justifies |
| `embedding_memory.py` | 836 | C- | **CRITICAL** (reinvents pgvector) | **STOP** — use `api_client` |
| `advanced_memory_skill.py` | 380 | D | Yes (broken imports) | **STOP** — rebuild after fixing components |
| `IMPLEMENTATION_TICKETS.md` | ~500 | A- | No | **SHIP** (update estimates) |
| `MEMORY_SYSTEM_GUIDE.md` | 656 | B | Mild | **SHIP** (add pseudocode warnings) |
| `EMBEDDING_REVISED.md` | 152 | **A+** | No — *anti-overengineering* | **SHIP** (authoritative) |
| `SCHEMA_DECISION.md` | 196 | B+ | Mild (academic) | **SHIP** as reference |
| `SENTIMENT_INTELLIGENCE_DESIGN.md` | 505 | F for scope | **EXTREME** | **STOP** — archive |
| `SENTIMENT_SIMPLIFIED.md` | 128 | **A+** | No — *anti-overengineering* | **SHIP** (authoritative) |
| `README_IMPLEMENTATION.md` | 197 | C | Contradicts REVISED | **STOP** — rewrite |

---

## Critical Issues (Showstoppers)

### 1. `embedding_memory.py` reinvents pgvector (836 wasted lines)
The `api_client` already provides:
- `store_memory_semantic()` — stores with auto-embedding via backend
- `search_memories_semantic()` — cosine similarity via pgvector  
- `summarize_session()` — episodic memory compression

Building a custom FAISS store, SentenceTransformer integration, HybridRetriever, and MetadataIndex is pure waste. `EMBEDDING_REVISED.md` correctly says: "Don't build FAISS/sentence-transformers — use api_client."

**Action:** Delete. Use existing API. Zero new code needed.

### 2. Crash bug in `sentiment_analysis.py`
Line ~471: `messages_analyzed=len(mentions)` — `mentions` is undefined in `analyze_conversation()` scope. This is a `NameError` at runtime.

Also: lexicon has `" thrilled"` (leading space) that won't match word-boundary regex. `"?"` and `"?!!!"` in EXCITED_WORDS are punctuation, not words.

**Action:** Fix bugs if simplifying. Better: use the 20-line version from `SENTIMENT_SIMPLIFIED.md`.

### 3. `advanced_memory_skill.py` broken imports
- `SkillRegistry` used as decorator but never imported
- Imports from `prototypes.memory_compression` — not a valid package
- `Optional` used without import  
- `analyze_sentiment` passes `use_llm=` to constructor expecting `llm_classifier=`

**Action:** Cannot run. Rewrite from scratch after simplifying components.

---

## Over-Engineering Flags

| Flag | Evidence | Impact |
|------|----------|--------|
| **FAISS vector store** | 836 lines when `api_client.search_memories_semantic()` exists | Waste: ~2h dev + numpy/FAISS dependency |
| **RL sentiment engine** | 505-line design for feedback loop + HTML dashboard | YAGNI — no user validation data exists yet |
| **4-weight ImportanceScorer** | `recency_weight=0.4, significance_weight=0.3, category_weight=0.2, length_weight=0.1` | No calibration data. Simple boolean filter covers 90% |
| **60-word lexicon** | Building full VAD system on ~20 positive + ~20 negative words | Near-zero signal. Use VADER (7500+ terms) or LLM-only |
| **3-word question grouping** | `" ".join(words[:3])` → "how do i" matches everything | False positives make feature useless |
| **Triplicated patch code** | Same protection logic 3x in session_protection_fix.py | 418 lines for a 20-line fix |

---

## What Aria Did Well

1. **Self-correction pattern.** Creating `EMBEDDING_REVISED.md` to correct `embedding_memory.py` and `SENTIMENT_SIMPLIFIED.md` to correct the RL design shows excellent intellectual honesty.

2. **Correct bug identification.** The session protection bug is real and dangerous — `delete_session()` has zero safeguards. The env-var approach is sound and minimal.

3. **Architecture awareness.** Prototypes correctly reference `SkillResult`, `BaseSkill`, `@logged_method()`, and understand the 5-layer system. The designs fit the codebase even when the code has bugs.

---

## Recommended Action Plan

### Phase 1: Ship (Low Risk, High Value)
1. **BUG-001 — Session Protection** (~15 min)
   - Extract the 20 lines of protection logic
   - Patch `session_manager/__init__.py` directly
   - Test: try to delete current session → should fail

### Phase 2: Simplify & Ship (Medium)  
2. **Basic Sentiment** (~30 min)
   - Use `SENTIMENT_SIMPLIFIED.md` approach
   - Threshold rules + store via `api_client.store_memory_semantic()`
   - Skip lexicon, skip VAD model, skip RL dashboard

3. **Memory Compression wrapper** (~30 min)
   - Wrap `api_client.summarize_session()` 
   - Keep `ImportanceScorer` only if needed (probably not)
   - No new dependencies

### Phase 3: Defer (Not Ready)
4. **Pattern Recognition** — defer until semantic_memories has >100 entries
5. **Embedding Memory** — delete prototype, use existing api_client
6. **RL Sentiment Dashboard** — archive, revisit when basic sentiment proves value

---

## Verdict

> **Ship BUG-001 + simplified sentiment + compression wrapper. Delete/archive everything else. The existing infrastructure (api_client + pgvector + FastAPI endpoints) already provides 80% of what the prototypes try to build from scratch.**

The prototypes show Aria thinking about the right problems, but building solutions that are 10x more complex than needed. The self-correction documents (EMBEDDING_REVISED.md, SENTIMENT_SIMPLIFIED.md) prove Aria can recognize this — we just need to follow through on the simplified versions.
