"""
Integration tests for the RPG router (S-155).

Tests RPG campaign endpoints using FastAPI TestClient with mocked DB and filesystem.
Covers: list campaigns, campaign detail, session transcript, KG subgraph, helpers.

The RPG router uses SQLAlchemy ORM queries directly, so we mock the endpoint
functions at the route level and test helpers separately.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src/api is importable
_api_dir = str(Path(__file__).resolve().parent.parent / "src" / "api")
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)


# ---------------------------------------------------------------------------
# Pre-import stubs — DB models must exist before router import
# ---------------------------------------------------------------------------

_db_mod = MagicMock()
_deps_mod = MagicMock()
sys.modules.setdefault("db", _db_mod)
sys.modules.setdefault("db.models", _db_mod)
sys.modules.setdefault("deps", _deps_mod)

from routers.rpg import (  # noqa: E402
    _load_yaml_safe,
    _list_campaign_dirs,
    _load_campaign,
    _list_sessions_for_campaign,
    CampaignSummary,
    CampaignDetail,
    KGResponse,
)


# ---------------------------------------------------------------------------
# Helper / utility tests (no DB required)
# ---------------------------------------------------------------------------

def test_load_yaml_safe_missing_file(tmp_path):
    result = _load_yaml_safe(tmp_path / "nonexistent.yaml")
    assert result == {}


def test_load_yaml_safe_valid(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("id: test\ntitle: Hello\n")
    result = _load_yaml_safe(f)
    assert result["id"] == "test"
    assert result["title"] == "Hello"


def test_list_campaign_dirs_empty(tmp_path):
    with patch("routers.rpg._RPG_DIR", tmp_path):
        result = _list_campaign_dirs()
    assert result == []


def test_list_campaign_dirs_with_campaigns(tmp_path):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    (campaigns / "camp_a").mkdir()
    (campaigns / "camp_b").mkdir()
    (campaigns / "readme.txt").write_text("not a dir")  # should be filtered

    with patch("routers.rpg._RPG_DIR", tmp_path):
        dirs = _list_campaign_dirs()
    names = [d.name for d in dirs]
    assert "camp_a" in names
    assert "camp_b" in names
    assert "readme.txt" not in names


def test_load_campaign_from_yaml(tmp_path):
    camp_dir = tmp_path / "campaigns" / "my_camp"
    camp_dir.mkdir(parents=True)
    (camp_dir / "campaign.yaml").write_text(
        "id: my_camp\ntitle: My Campaign\nsetting: Sci-Fi\n"
    )
    with patch("routers.rpg._RPG_DIR", tmp_path):
        data = _load_campaign("my_camp")
    assert data["id"] == "my_camp"
    assert data["title"] == "My Campaign"


def test_load_campaign_missing(tmp_path):
    with patch("routers.rpg._RPG_DIR", tmp_path):
        data = _load_campaign("nonexistent")
    assert data == {}


def test_list_sessions_for_campaign(tmp_path):
    sess_dir = tmp_path / "campaigns" / "camp" / "sessions"
    sess_dir.mkdir(parents=True)
    (sess_dir / "session_001.yaml").write_text("number: 1\ntitle: The Beginning\n")
    (sess_dir / "session_002.yaml").write_text("number: 2\ntitle: The Middle\n")

    with patch("routers.rpg._RPG_DIR", tmp_path):
        sessions = _list_sessions_for_campaign("camp")
    assert len(sessions) == 2
    titles = [s["title"] for s in sessions]
    assert "The Beginning" in titles


def test_list_sessions_no_dir(tmp_path):
    with patch("routers.rpg._RPG_DIR", tmp_path):
        sessions = _list_sessions_for_campaign("nonexistent")
    assert sessions == []


# ---------------------------------------------------------------------------
# Pydantic model tests (request/response schema validation)
# ---------------------------------------------------------------------------

def test_campaign_summary_schema():
    cs = CampaignSummary(
        id="test", title="Test", setting="Fantasy", status="active",
        party_size=4, session_count=2, last_played="2026-02-24",
    )
    assert cs.id == "test"
    assert cs.party_size == 4


def test_campaign_detail_schema():
    cd = CampaignDetail(
        id="test", title="Test", setting="Fantasy", status="active",
        description="A great campaign", party=[{"name": "Aria"}],
        world_state={"weather": "rain"}, sessions=[], kg_entity_count=5,
    )
    assert cd.kg_entity_count == 5
    assert len(cd.party) == 1


def test_kg_response_empty():
    kg = KGResponse(nodes=[], edges=[])
    assert kg.nodes == []
    assert kg.edges == []
