# aria_skills/unified_search/__init__.py
"""
Unified Search — Full Production Implementation.

Merges three retrieval backends using Reciprocal Rank Fusion (RRF):
  1. Semantic search  — pgvector cosine similarity (nomic-embed-text 768d)
  2. Knowledge graph  — ILIKE entity/relation search via skill graph
  3. Memory search    — Full-text keyword search on memories table

RRF formula:  score(d) = SUM( 1 / (k + rank_i(d)) )  for each backend
  k = 60 (standard smoothing constant)

Supports:
  - Weighted backend contributions
  - Category/source filters
  - Importance thresholds
  - Deduplication by content hash

All retrieval via api_client → FastAPI → PostgreSQL.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


# ═══════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SearchResult:
    """Single search result with score and source info."""
    content: str
    score: float
    source: str           # "semantic", "graph", "memory"
    category: str = ""
    importance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_id: str = ""

    @property
    def content_hash(self) -> str:
        return hashlib.md5(self.content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "score": round(self.score, 4),
            "source": self.source,
            "category": self.category,
            "importance": self.importance,
            "metadata": self.metadata,
            "id": self.original_id,
        }


@dataclass
class MergedSearchResult:
    """Result after RRF merge of multiple backends."""
    results: List[SearchResult]
    total_results: int
    backends_used: List[str]
    query: str
    elapsed_ms: float = 0.0
    backend_counts: Dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Reciprocal Rank Fusion
# ═══════════════════════════════════════════════════════════════════

class RRFMerger:
    """
    Reciprocal Rank Fusion for combining ranked result lists.

    score(d) = SUM( weight_i / (k + rank_i(d)) ) for each backend i
    """

    def __init__(self, k: int = 60, weights: Optional[Dict[str, float]] = None):
        self.k = k
        self.weights = weights or {"semantic": 1.0, "graph": 0.8, "memory": 0.6}

    def merge(self, ranked_lists: Dict[str, List[SearchResult]],
              limit: int = 20) -> List[SearchResult]:
        """
        Merge multiple ranked lists using RRF.

        Args:
            ranked_lists: {backend_name: [SearchResult sorted by relevance]}
            limit: Max results to return

        Returns:
            Merged and re-ranked results
        """
        score_map: Dict[str, float] = {}       # content_hash → rrf_score
        result_map: Dict[str, SearchResult] = {}  # content_hash → best result
        source_map: Dict[str, List[str]] = {}   # content_hash → [sources]

        for backend, results in ranked_lists.items():
            w = self.weights.get(backend, 0.5)
            for rank_idx, result in enumerate(results):
                h = result.content_hash
                rrf_score = w / (self.k + rank_idx + 1)

                score_map[h] = score_map.get(h, 0.0) + rrf_score

                if h not in result_map or result.score > result_map[h].score:
                    result_map[h] = result

                if h not in source_map:
                    source_map[h] = []
                if backend not in source_map[h]:
                    source_map[h].append(backend)

        # Build final results sorted by RRF score
        merged: List[SearchResult] = []
        for h, rrf_score in sorted(score_map.items(), key=lambda x: x[1], reverse=True):
            r = result_map[h]
            r.score = rrf_score
            sources = source_map.get(h, [r.source])
            if len(sources) > 1:
                r.metadata["sources"] = sources
                r.source = "+".join(sources)
            merged.append(r)

        return merged[:limit]


# ═══════════════════════════════════════════════════════════════════
# Search Backends
# ═══════════════════════════════════════════════════════════════════

class SemanticBackend:
    """Search via pgvector cosine similarity."""

    def __init__(self, api_client):
        self._api = api_client

    async def search(self, query: str, limit: int = 20,
                     category: Optional[str] = None,
                     min_importance: float = 0.0) -> List[SearchResult]:
        try:
            result = await self._api.search_memories_semantic(
                query=query, limit=limit, category=category,
                min_importance=min_importance)
            if not result.success:
                return []

            items = result.data if isinstance(result.data, list) else (
                result.data.get("results", result.data.get("items", []))
                if isinstance(result.data, dict) else [])

            results: List[SearchResult] = []
            for item in items:
                results.append(SearchResult(
                    content=item.get("content", ""),
                    score=float(item.get("similarity", item.get("score", 0.5))),
                    source="semantic",
                    category=item.get("category", ""),
                    importance=float(item.get("importance", 0)),
                    metadata=item.get("metadata", {}),
                    original_id=str(item.get("id", "")),
                ))
            return results
        except Exception:
            return []


class GraphBackend:
    """Search via knowledge graph entity/relation ILIKE."""

    def __init__(self, api_client):
        self._api = api_client

    async def search(self, query: str, limit: int = 20,
                     entity_type: Optional[str] = None) -> List[SearchResult]:
        try:
            result = await self._api.graph_search(
                query=query, limit=limit, entity_type=entity_type)
            if not result.success:
                return []

            items = result.data if isinstance(result.data, list) else (
                result.data.get("results", result.data.get("entities", []))
                if isinstance(result.data, dict) else [])

            results: List[SearchResult] = []
            for item in items:
                name = item.get("name", item.get("label", ""))
                desc = item.get("description", item.get("properties", {}).get("description", ""))
                content = f"{name}: {desc}" if desc else name
                results.append(SearchResult(
                    content=content,
                    score=float(item.get("score", item.get("relevance", 0.5))),
                    source="graph",
                    category=item.get("entity_type", item.get("type", "")),
                    metadata={k: v for k, v in item.items() if k not in ("name", "description")},
                    original_id=str(item.get("id", "")),
                ))
            return results
        except Exception:
            return []


class MemoryBackend:
    """Search via traditional text-match memories."""

    def __init__(self, api_client):
        self._api = api_client

    async def search(self, query: str, limit: int = 20,
                     category: Optional[str] = None) -> List[SearchResult]:
        try:
            result = await self._api.get_memories(
                category=category, limit=limit, search=query)
            if not result.success:
                return []

            items = result.data if isinstance(result.data, list) else (
                result.data.get("items", result.data.get("memories", []))
                if isinstance(result.data, dict) else [])

            results: List[SearchResult] = []
            for item in items:
                results.append(SearchResult(
                    content=item.get("content", ""),
                    score=0.5,
                    source="memory",
                    category=item.get("category", ""),
                    importance=float(item.get("importance", item.get("importance_score", 0))),
                    metadata=item.get("metadata", {}),
                    original_id=str(item.get("id", "")),
                ))
            return results
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════════════
# Skill Class
# ═══════════════════════════════════════════════════════════════════

@SkillRegistry.register
class UnifiedSearchSkill(BaseSkill):
    """
    Unified search across semantic, graph, and memory backends with RRF.

    Tools:
      search           — Full unified search with RRF merge
      semantic_search  — Search semantic memories only
      graph_search     — Search knowledge graph only
      memory_search    — Search traditional memories only
    """

    def __init__(self, config: Optional[SkillConfig] = None):
        super().__init__(config or SkillConfig(name="unified_search"))
        self._api = None
        self._semantic: Optional[SemanticBackend] = None
        self._graph: Optional[GraphBackend] = None
        self._memory: Optional[MemoryBackend] = None
        self._merger: Optional[RRFMerger] = None
        self._search_count = 0

    @property
    def name(self) -> str:
        return "unified_search"

    async def initialize(self) -> bool:
        try:
            from aria_skills.api_client import get_api_client
            self._api = await get_api_client()
        except Exception as e:
            self.logger.error(f"API client required for unified search: {e}")
            self._status = SkillStatus.UNAVAILABLE
            return False

        self._semantic = SemanticBackend(self._api)
        self._graph = GraphBackend(self._api)
        self._memory = MemoryBackend(self._api)

        weights = {
            "semantic": float(self.config.config.get("weight_semantic", 1.0)),
            "graph": float(self.config.config.get("weight_graph", 0.8)),
            "memory": float(self.config.config.get("weight_memory", 0.6)),
        }
        k = int(self.config.config.get("rrf_k", 60))
        self._merger = RRFMerger(k=k, weights=weights)

        self._status = SkillStatus.AVAILABLE
        self.logger.info("Unified search initialized (weights=%s, k=%d)", weights, k)
        return True

    async def health_check(self) -> SkillStatus:
        if self._api is None:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    @logged_method()
    async def search(self, query: str = "", limit: int = 20,
                     backends: Optional[List[str]] = None,
                     category: Optional[str] = None,
                     min_importance: float = 0.0, **kwargs) -> SkillResult:
        """
        Unified search across all backends with RRF merge.

        Args:
            query: Search query text
            limit: Max results to return
            backends: Which backends to use (default: all)
            category: Optional category filter
            min_importance: Minimum importance threshold
        """
        import time

        query = query or kwargs.get("query", "")
        if not query:
            return SkillResult.fail("No query provided")

        backends = backends or kwargs.get("backends", ["semantic", "graph", "memory"])
        start = time.monotonic()

        ranked_lists: Dict[str, List[SearchResult]] = {}
        backend_counts: Dict[str, int] = {}

        # Run backends (sequential to avoid overwhelming API)
        if "semantic" in backends and self._semantic:
            results = await self._semantic.search(
                query, limit=limit, category=category, min_importance=min_importance)
            ranked_lists["semantic"] = results
            backend_counts["semantic"] = len(results)

        if "graph" in backends and self._graph:
            results = await self._graph.search(query, limit=limit)
            ranked_lists["graph"] = results
            backend_counts["graph"] = len(results)

        if "memory" in backends and self._memory:
            results = await self._memory.search(query, limit=limit, category=category)
            ranked_lists["memory"] = results
            backend_counts["memory"] = len(results)

        # RRF merge
        merged = self._merger.merge(ranked_lists, limit=limit)
        elapsed = (time.monotonic() - start) * 1000

        self._search_count += 1

        return SkillResult.ok({
            "query": query,
            "results": [r.to_dict() for r in merged],
            "total_results": len(merged),
            "backends_used": list(ranked_lists.keys()),
            "backend_counts": backend_counts,
            "elapsed_ms": round(elapsed, 1),
            "search_number": self._search_count,
        })

    @logged_method()
    async def semantic_search(self, query: str = "", limit: int = 20,
                               category: Optional[str] = None, **kwargs) -> SkillResult:
        """Search semantic memories only."""
        query = query or kwargs.get("query", "")
        if not query:
            return SkillResult.fail("No query provided")

        results = await self._semantic.search(query, limit=limit, category=category)
        return SkillResult.ok({
            "query": query,
            "results": [r.to_dict() for r in results],
            "total_results": len(results),
            "backend": "semantic",
        })

    @logged_method()
    async def graph_search(self, query: str = "", limit: int = 20, **kwargs) -> SkillResult:
        """Search knowledge graph only."""
        query = query or kwargs.get("query", "")
        if not query:
            return SkillResult.fail("No query provided")

        results = await self._graph.search(query, limit=limit)
        return SkillResult.ok({
            "query": query,
            "results": [r.to_dict() for r in results],
            "total_results": len(results),
            "backend": "graph",
        })

    @logged_method()
    async def memory_search(self, query: str = "", limit: int = 20,
                             category: Optional[str] = None, **kwargs) -> SkillResult:
        """Search traditional memories only."""
        query = query or kwargs.get("query", "")
        if not query:
            return SkillResult.fail("No query provided")

        results = await self._memory.search(query, limit=limit, category=category)
        return SkillResult.ok({
            "query": query,
            "results": [r.to_dict() for r in results],
            "total_results": len(results),
            "backend": "memory",
        })

    async def close(self) -> None:
        self._api = None
        self._semantic = None
        self._graph = None
        self._memory = None
        self._status = SkillStatus.UNAVAILABLE
