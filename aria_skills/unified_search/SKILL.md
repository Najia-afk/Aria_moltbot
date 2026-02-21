```skill
---
name: aria-unified-search
description: "🔎 RRF-merged search across semantic + graph + memory backends"
metadata: {"aria": {"emoji": "🔎"}}
---

# aria-unified-search

Unified search engine that queries semantic memories (pgvector cosine),
knowledge graph (ILIKE), and traditional memories (text match), then
merges results via Reciprocal Rank Fusion (RRF) with content-hash
deduplication.

## Architecture

```
Query
    ↓ (parallel to 3 backends)
    ├── SemanticBackend (pgvector cosine similarity via api_client)
    ├── GraphBackend (ILIKE text match via api_client.graph_search)
    └── MemoryBackend (text match via api_client.get_memories)
    ↓
RRFMerger (k=60)
    ├── semantic weight: 1.0
    ├── graph weight: 0.8
    └── memory weight: 0.6
    ↓
Content-hash deduplication
    ↓
Ranked results (SearchResult objects)
```

## RRF Formula

$$\text{score}(d) = \sum_{b \in \text{backends}} \frac{w_b}{k + \text{rank}_b(d)}$$

Where $k = 60$ (damping constant) and $w_b$ is the backend weight.

## Usage

```bash
# Unified search across all backends
exec python3 /app/skills/run_skill.py unified_search search '{"query": "security best practices"}'

# With filters
exec python3 /app/skills/run_skill.py unified_search search '{"query": "AI safety", "limit": 10, "backends": ["semantic", "graph"], "min_importance": 0.5}'

# Semantic-only search
exec python3 /app/skills/run_skill.py unified_search semantic_search '{"query": "deployment pipeline"}'

# Graph-only search
exec python3 /app/skills/run_skill.py unified_search graph_search '{"query": "moltbook"}'

# Memory-only search
exec python3 /app/skills/run_skill.py unified_search memory_search '{"query": "user preferences"}'
```

## Functions

### search
Unified search across all backends with RRF merge. Returns deduplicated,
ranked results with backend attribution and timing info.

### semantic_search
Search semantic memories only via pgvector cosine similarity.
Supports category and importance filters.

### graph_search
Search knowledge graph only via ILIKE text matching on entity names
and relation labels.

### memory_search
Search traditional key-value memories only via text matching.
Supports category filter.

## Dependencies
- `api_client` (all 3 backend searches)
```
