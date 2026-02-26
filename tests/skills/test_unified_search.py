"""
Tests for the unified_search skill (Layer 3 — domain).

Covers:
- RRFMerger: merge, deduplication, weighting
- Backend wrappers (SemanticBackend, GraphBackend, MemoryBackend)
- UnifiedSearchSkill: initialize, search, semantic_search, graph_search, memory_search
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.unified_search import (
    UnifiedSearchSkill,
    RRFMerger,
    SearchResult,
    SemanticBackend,
    GraphBackend,
    MemoryBackend,
)


# ---------------------------------------------------------------------------
# RRFMerger tests
# ---------------------------------------------------------------------------

def _sr(content, score, source):
    return SearchResult(content=content, score=score, source=source)


def test_rrf_merge_basic():
    merger = RRFMerger(k=60)
    ranked = {
        "semantic": [_sr("doc A", 0.9, "semantic"), _sr("doc B", 0.8, "semantic")],
        "graph": [_sr("doc B", 0.7, "graph"), _sr("doc C", 0.6, "graph")],
    }
    merged = merger.merge(ranked, limit=10)
    assert len(merged) == 3
    # doc B appears in both → boosted score
    contents = [r.content for r in merged]
    assert "doc B" in contents


def test_rrf_merge_respects_limit():
    merger = RRFMerger(k=60)
    ranked = {
        "semantic": [_sr(f"doc {i}", 0.9 - i * 0.01, "semantic") for i in range(20)],
    }
    merged = merger.merge(ranked, limit=5)
    assert len(merged) == 5


def test_rrf_merge_deduplication():
    merger = RRFMerger(k=60)
    # Same content in both backends
    ranked = {
        "semantic": [_sr("duplicate content", 0.9, "semantic")],
        "memory": [_sr("duplicate content", 0.5, "memory")],
    }
    merged = merger.merge(ranked, limit=10)
    assert len(merged) == 1  # Deduplicated by content hash


def test_rrf_merge_weights():
    # Semantic weight > memory weight → semantic results score higher
    merger = RRFMerger(k=60, weights={"semantic": 2.0, "memory": 0.5})
    ranked = {
        "semantic": [_sr("sem doc", 0.9, "semantic")],
        "memory": [_sr("mem doc", 0.9, "memory")],
    }
    merged = merger.merge(ranked, limit=10)
    # First result should be from semantic (higher weight)
    assert merged[0].content == "sem doc"


def test_rrf_merge_empty():
    merger = RRFMerger()
    merged = merger.merge({}, limit=10)
    assert merged == []


# ---------------------------------------------------------------------------
# Backend wrapper tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semantic_backend(mock_api_client):
    mock_api_client.search_memories_semantic = AsyncMock(return_value=SkillResult.ok([
        {"content": "test memory", "similarity": 0.85, "category": "general", "id": "1"},
    ]))
    backend = SemanticBackend(mock_api_client)
    results = await backend.search("test query")
    assert len(results) == 1
    assert results[0].source == "semantic"


@pytest.mark.asyncio
async def test_graph_backend(mock_api_client):
    mock_api_client.graph_search = AsyncMock(return_value=SkillResult.ok({
        "results": [{"name": "Entity A", "description": "Test entity", "id": "e1"}]
    }))
    backend = GraphBackend(mock_api_client)
    results = await backend.search("Entity A")
    assert len(results) == 1
    assert results[0].source == "graph"


@pytest.mark.asyncio
async def test_memory_backend(mock_api_client):
    mock_api_client.get_memories = AsyncMock(return_value=SkillResult.ok([
        {"content": "some test data", "category": "general", "id": "m1"},
    ]))
    backend = MemoryBackend(mock_api_client)
    results = await backend.search("test")
    assert len(results) == 1
    assert results[0].source == "memory"


@pytest.mark.asyncio
async def test_semantic_backend_failure(mock_api_client):
    mock_api_client.search_memories_semantic = AsyncMock(return_value=SkillResult.fail("error"))
    backend = SemanticBackend(mock_api_client)
    results = await backend.search("query")
    assert results == []


# ---------------------------------------------------------------------------
# UnifiedSearchSkill tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_initialize(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_skill_search(mock_api_client):
    mock_api_client.search_memories_semantic = AsyncMock(return_value=SkillResult.ok([
        {"content": "semantic result", "similarity": 0.9, "id": "s1"},
    ]))
    mock_api_client.graph_search = AsyncMock(return_value=SkillResult.ok({"results": []}))
    mock_api_client.get_memories = AsyncMock(return_value=SkillResult.ok([]))

    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        await skill.initialize()
        result = await skill.search(query="test query")
    assert result.success
    assert result.data["total_results"] >= 1
    assert "semantic" in result.data["backends_used"]


@pytest.mark.asyncio
async def test_skill_search_no_query(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        await skill.initialize()
        result = await skill.search(query="")
    assert not result.success


@pytest.mark.asyncio
async def test_skill_search_not_initialized():
    skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
    skill._merger = None
    result = await skill.search(query="test")
    assert not result.success


@pytest.mark.asyncio
async def test_skill_semantic_search(mock_api_client):
    mock_api_client.search_memories_semantic = AsyncMock(return_value=SkillResult.ok([
        {"content": "hello", "similarity": 0.8, "id": "x1"},
    ]))
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        await skill.initialize()
        result = await skill.semantic_search(query="hello")
    assert result.success
    assert result.data["backend"] == "semantic"


@pytest.mark.asyncio
async def test_skill_graph_search(mock_api_client):
    mock_api_client.graph_search = AsyncMock(return_value=SkillResult.ok({
        "results": [{"name": "X", "description": "desc", "id": "g1"}]
    }))
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        await skill.initialize()
        result = await skill.graph_search(query="X")
    assert result.success
    assert result.data["backend"] == "graph"


@pytest.mark.asyncio
async def test_skill_memory_search(mock_api_client):
    mock_api_client.get_memories = AsyncMock(return_value=SkillResult.ok([
        {"content": "some memory about coding", "category": "general", "id": "m1"},
    ]))
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        await skill.initialize()
        result = await skill.memory_search(query="coding")
    assert result.success
    assert result.data["backend"] == "memory"


@pytest.mark.asyncio
async def test_skill_close(mock_api_client):
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = UnifiedSearchSkill(SkillConfig(name="unified_search"))
        await skill.initialize()
        await skill.close()
    assert skill._status == SkillStatus.UNAVAILABLE
    assert skill._api is None
