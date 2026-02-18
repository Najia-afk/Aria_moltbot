```skill
---
name: aria-memory-compression
description: "ðŸ—œï¸ 3-tier hierarchical memory compression"
metadata: {"aria": {"emoji": "ðŸ—œï¸"}}
---

# aria-memory-compression

3-tier hierarchical memory compression engine. Scores memory importance,
compresses via LLM summarization (with rule-based fallback), and manages
raw â†’ recent â†’ archive tiers. Stores compressed summaries in semantic memory.

## Architecture

```
Raw memories (limit: 20)
    â†“ ImportanceScorer (recency Ã— significance Ã— category Ã— length)
    â†“ MemoryCompressor (LLM via LiteLLM + fallback)
Recent tier (limit: 100, ratio: 0.3)
    â†“
Archive tier (all older, ratio: 0.1)
    â†“
SemanticMemory (category: compressed_recent / compressed_archive)
```

## Usage

```bash
# Compress a batch of memories through the pipeline
exec python3 /app/skills/run_skill.py memory_compression compress_memories '{"memories": [{"content": "...", "category": "task", "timestamp": "2026-02-16T10:00:00Z"}]}'

# Compress recent session (last N hours)
exec python3 /app/skills/run_skill.py memory_compression compress_session '{"hours_back": 6}'

# Get working context within token budget
exec python3 /app/skills/run_skill.py memory_compression get_context_budget '{"max_tokens": 2000}'

# Check compression statistics
exec python3 /app/skills/run_skill.py memory_compression get_compression_stats '{}'
```

## Functions

### compress_memories
Compress a list of memories through the 3-tier pipeline. Scores importance,
groups by tier, LLM-summarizes each group, stores in semantic memory.
Returns compression ratio, tokens saved, and summaries.

### compress_session
Quick compress of recent session activity via `api_client.summarize_session()`.
Useful for end-of-session cleanup.

### get_context_budget
Retrieve working memory context within a token budget. Includes both raw
working memory items and compressed summaries from previous runs.

### get_compression_stats
Get statistics from the last compression run â€” memories processed,
compression ratio, tokens saved, tier breakdown.

## Dependencies
- `api_client` (semantic memory storage, working memory, session summarization)
- LiteLLM proxy (kimi model for LLM summarization)
```
