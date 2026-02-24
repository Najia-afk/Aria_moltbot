"""
Tests for the knowledge_graph skill (Layer 3 — domain).

Covers:
- Entity creation (API-backed + fallback)
- Relation management
- Entity querying / search
- Graph traversal
- Error/fallback paths
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_api():
    """Build a mock API client with knowledge-graph endpoints."""
    api = AsyncMock()

    # POST responses
    api.post = AsyncMock(return_value=MagicMock(
        data={"id": "concept:python", "name": "Python", "type": "concept"},
        error=None,
        __bool__=lambda self: True,
    ))

    # GET responses (entities list)
    api.get = AsyncMock(return_value=MagicMock(
        data={"entities": [
            {"id": "concept:python", "name": "Python", "type": "concept"},
        ]},
        error=None,
        __bool__=lambda self: True,
    ))

    return api


async def _make_skill(api=None):
    api = api or _mock_api()
    with patch("aria_skills.knowledge_graph.get_api_client", new_callable=AsyncMock, return_value=api):
        from aria_skills.knowledge_graph import KnowledgeGraphSkill
        skill = KnowledgeGraphSkill(SkillConfig(name="knowledge_graph"))
        await skill.initialize()
    return skill, api


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill, _ = await _make_skill()
    assert await skill.health_check() == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_close():
    skill, _ = await _make_skill()
    await skill.close()
    assert skill._api is None


# ---------------------------------------------------------------------------
# Tests — Entity Creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_entity():
    skill, api = await _make_skill()
    result = await skill.add_entity(name="Python", entity_type="concept")
    assert result.success
    api.post.assert_awaited_once()
    call_args = api.post.call_args
    assert "/knowledge-graph/entities" in call_args.args[0]


@pytest.mark.asyncio
async def test_add_entity_with_properties():
    skill, api = await _make_skill()
    result = await skill.add_entity(
        name="FastAPI", entity_type="framework",
        properties={"language": "python", "version": "0.100"}
    )
    assert result.success


@pytest.mark.asyncio
async def test_add_entity_api_fallback():
    """When API fails, entity is stored in local fallback cache."""
    api = _mock_api()
    api.post = AsyncMock(return_value=MagicMock(
        __bool__=lambda self: False, error="API error"
    ))
    skill, _ = await _make_skill(api)
    result = await skill.add_entity(name="LocalOnly", entity_type="test")
    assert result.success
    assert "test:localonly" in skill._entities


# ---------------------------------------------------------------------------
# Tests — Relation Management
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_relation():
    skill, api = await _make_skill()
    result = await skill.add_relation(
        from_entity="concept:python", relation="uses", to_entity="concept:pip"
    )
    assert result.success


@pytest.mark.asyncio
async def test_add_relation_api_fallback():
    api = _mock_api()
    api.post = AsyncMock(return_value=MagicMock(
        __bool__=lambda self: False, error="API error"
    ))
    skill, _ = await _make_skill(api)
    result = await skill.add_relation(
        from_entity="a", relation="related", to_entity="b"
    )
    assert result.success
    assert len(skill._relations) == 1


# ---------------------------------------------------------------------------
# Tests — Entity Querying
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_entity():
    skill, api = await _make_skill()
    result = await skill.get_entity(query="Python")
    assert result.success
    assert result.data["entity"]["name"] == "Python"


@pytest.mark.asyncio
async def test_get_entity_not_found():
    api = _mock_api()
    api.get = AsyncMock(return_value=MagicMock(
        data={"entities": []},
        error=None,
        __bool__=lambda self: True,
    ))
    skill, _ = await _make_skill(api)
    result = await skill.get_entity(query="Nonexistent")
    assert not result.success


@pytest.mark.asyncio
async def test_get_entity_no_query():
    skill, _ = await _make_skill()
    result = await skill.get_entity()
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Graph Traversal / Query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_by_entity_name():
    api = _mock_api()
    api.get = AsyncMock(return_value=MagicMock(
        data={"nodes": [{"id": "python"}], "edges": [{"from": "python", "to": "pip"}],
              "total_nodes": 1, "total_edges": 1},
        error=None,
        __bool__=lambda self: True,
    ))
    skill, _ = await _make_skill(api)
    result = await skill.query(entity_name="Python", depth=2)
    assert result.success
    assert "entities" in result.data


@pytest.mark.asyncio
async def test_query_by_type_fallback():
    """When API fails, query falls back to local cache."""
    api = _mock_api()
    api.get = AsyncMock(side_effect=Exception("Offline"))
    skill, _ = await _make_skill(api)
    # Pre-populate fallback
    skill._entities["concept:test"] = {"id": "concept:test", "name": "Test", "type": "concept"}
    result = await skill.query(entity_type="concept")
    assert result.success
    assert result.data["total_entities"] >= 1
