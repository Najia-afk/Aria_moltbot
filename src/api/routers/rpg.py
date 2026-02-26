"""
RPG Dashboard API — Campaign overview, KG visualization, session transcripts.

Part of Sprint 1 "The Crystal Ball". Feeds the self-contained RPG dashboard
at /rpg/index.html. All DB access via SQLAlchemy ORM — skills NEVER imported.

Endpoints:
  GET /api/rpg/campaigns             — List all campaigns with summary
  GET /api/rpg/campaign/{id}         — Full campaign detail
  GET /api/rpg/session/{id}/transcript — Session message history
  GET /api/rpg/campaign/{id}/kg      — KG subgraph (vis-network format)
"""

import logging
import os
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db

try:
    from db.models import (
        KnowledgeEntity,
        KnowledgeRelation,
        EngineChatSession,
        EngineChatMessage,
    )
except ImportError:
    from ..db.models import (
        KnowledgeEntity,
        KnowledgeRelation,
        EngineChatSession,
        EngineChatMessage,
    )

router = APIRouter(tags=["RPG Dashboard"])
logger = logging.getLogger("aria.api.rpg")

# ── Paths (from env, never hardcoded) ────────────────────────────────────────

_MEMORIES_PATH = Path(
    os.getenv("ARIA_MEMORIES_PATH", "/aria_memories")
)
_RPG_DIR = _MEMORIES_PATH / "rpg"


# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class CampaignSummary(BaseModel):
    """Lightweight campaign listing entry."""
    id: str
    title: str
    setting: str
    status: str
    party_size: int = 0
    session_count: int = 0
    last_played: Optional[str] = None


class CampaignDetail(BaseModel):
    """Full campaign info including party, world state, and sessions."""
    id: str
    title: str
    setting: str
    status: str
    description: str = ""
    party: list[dict] = []
    world_state: dict = {}
    sessions: list[dict] = []
    kg_entity_count: int = 0


class KGResponse(BaseModel):
    """Knowledge graph subgraph for vis-network rendering."""
    nodes: list[dict]
    edges: list[dict]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_yaml_safe(path: Path) -> dict:
    """Load YAML file, return empty dict on failure."""
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("RPG data parse error: %s", e)
        return {}


def _list_campaign_dirs() -> list[Path]:
    """List campaign directories under aria_memories/rpg/campaigns/."""
    campaigns_dir = _RPG_DIR / "campaigns"
    if not campaigns_dir.exists():
        return []
    return [d for d in campaigns_dir.iterdir() if d.is_dir()]


def _load_campaign(campaign_id: str) -> dict:
    """Load campaign YAML from disk."""
    campaign_file = _RPG_DIR / "campaigns" / campaign_id / "campaign.yaml"
    return _load_yaml_safe(campaign_file)


def _list_sessions_for_campaign(campaign_id: str) -> list[dict]:
    """List session files for a campaign."""
    sessions_dir = _RPG_DIR / "campaigns" / campaign_id / "sessions"
    if not sessions_dir.exists():
        return []
    sessions = []
    for f in sorted(sessions_dir.glob("*.yaml")):
        d = _load_yaml_safe(f)
        sessions.append({
            "file": f.name,
            "number": d.get("number", 0),
            "title": d.get("title", f.stem),
        })
    return sessions


# ── Entity type → vis-network color mapping ──────────────────────────────────

_TYPE_COLORS = {
    "player_character": "#4A90D9",
    "npc":              "#27AE60",
    "npc_companion":    "#2ECC71",
    "location":         "#F39C12",
    "city":             "#E67E22",
    "tavern":           "#D35400",
    "dungeon_room":     "#8E44AD",
    "monster":          "#E74C3C",
    "enemy":            "#C0392B",
    "campaign":         "#3498DB",
    "session":          "#1ABC9C",
    "quest":            "#9B59B6",
    "artifact":         "#F1C40F",
    "magical_construct":"#16A085",
    "divine_event":     "#E8D44D",
    "concept":          "#95A5A6",
    "character":        "#5DADE2",
    "person":           "#48C9B0",
}

_DEFAULT_COLOR = "#BDC3C7"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/rpg/campaigns", response_model=list[CampaignSummary])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    """List all RPG campaigns with summary stats."""
    campaigns: list[CampaignSummary] = []

    # 1. Load from YAML files
    for campaign_dir in _list_campaign_dirs():
        data = _load_yaml_safe(campaign_dir / "campaign.yaml")
        if not data:
            continue
        campaigns.append(CampaignSummary(
            id=data.get("id", campaign_dir.name),
            title=data.get("title", campaign_dir.name),
            setting=data.get("setting", "Unknown"),
            status=data.get("status", "active"),
            party_size=len(data.get("party", [])),
            session_count=data.get("current_session", 0),
            last_played=str(data.get("updated_at", "")) or None,
        ))

    # 2. Also check KG for campaign entities not on disk
    stmt = select(KnowledgeEntity).where(KnowledgeEntity.type == "campaign")
    result = await db.execute(stmt)
    kg_campaigns = result.scalars().all()

    existing_ids = {c.id for c in campaigns}
    for entity in kg_campaigns:
        eid = entity.name.lower().replace(" ", "_")
        if eid not in existing_ids:
            existing_ids.add(eid)
            props = entity.properties or {}
            campaigns.append(CampaignSummary(
                id=eid,
                title=entity.name,
                setting=props.get("setting", "Unknown"),
                status=props.get("status", "active"),
                party_size=props.get("party_size", 0),
                session_count=props.get("session_count", 0),
                last_played=str(entity.updated_at) if entity.updated_at else None,
            ))

    return campaigns


@router.get("/rpg/campaign/{campaign_id}")
async def get_campaign_detail(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Full campaign detail: party, world state, sessions, KG stats."""
    data = _load_campaign(campaign_id)

    if not data:
        # Fallback: check KG
        stmt = select(KnowledgeEntity).where(KnowledgeEntity.type == "campaign")
        result = await db.execute(stmt)
        for entity in result.scalars().all():
            if entity.name.lower().replace(" ", "_") == campaign_id:
                data = {
                    "id": campaign_id,
                    "title": entity.name,
                    "setting": (entity.properties or {}).get("setting", "Unknown"),
                    "status": "active",
                    "description": (entity.properties or {}).get("description", ""),
                    "party": [],
                }
                break

    if not data:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    # Load world state
    world = _load_yaml_safe(_RPG_DIR / "campaigns" / campaign_id / "world.yaml")

    # Count KG entities connected to the campaign entity
    campaign_name = data.get("title", campaign_id.replace("_", " ").title())
    seed_stmt = select(KnowledgeEntity).where(KnowledgeEntity.name == campaign_name)
    seed_result = await db.execute(seed_stmt)
    seed = seed_result.scalars().first()

    kg_count = 0
    if seed:
        rel_stmt = select(KnowledgeRelation).where(
            (KnowledgeRelation.from_entity == seed.id) |
            (KnowledgeRelation.to_entity == seed.id)
        )
        rel_result = await db.execute(rel_stmt)
        kg_count = len(rel_result.scalars().all())

    # Sessions from YAML
    sessions = _list_sessions_for_campaign(campaign_id)

    # Also include engine chat sessions for RPG if we can identify them
    rpg_session_stmt = select(EngineChatSession).where(
        EngineChatSession.session_type == "interactive",
        EngineChatSession.title.ilike(f"%{campaign_name}%"),
    )
    rresult = await db.execute(rpg_session_stmt)
    for s in rresult.scalars().all():
        sessions.append({
            "session_id": str(s.id),
            "title": s.title or "Untitled Session",
            "message_count": s.message_count or 0,
        })

    return CampaignDetail(
        id=data.get("id", campaign_id),
        title=data.get("title", campaign_id),
        setting=data.get("setting", "Unknown"),
        status=data.get("status", "active"),
        description=data.get("description", ""),
        party=data.get("party", []),
        world_state=world,
        sessions=sessions,
        kg_entity_count=kg_count,
    )


@router.get("/rpg/session/{session_id}/transcript")
async def get_session_transcript(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve session message history for dashboard display."""
    stmt = (
        select(EngineChatMessage)
        .where(EngineChatMessage.session_id == session_id)
        .order_by(EngineChatMessage.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    if not messages:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or empty")

    transcript = []
    for msg in messages:
        transcript.append({
            "role": msg.role or "unknown",
            "content": msg.content or "",
            "timestamp": str(msg.created_at) if msg.created_at else None,
            "tool_calls": msg.tool_calls,
        })

    return {"session_id": session_id, "message_count": len(transcript), "messages": transcript}


@router.get("/rpg/campaign/{campaign_id}/kg", response_model=KGResponse)
async def get_campaign_kg(
    campaign_id: str,
    max_depth: int = Query(default=3, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
):
    """
    KG subgraph for this campaign — vis-network compatible format.

    BFS from campaign entity through relations up to max_depth hops.
    Nodes color-coded by type, edges labeled by relation_type.
    """
    data = _load_campaign(campaign_id)
    campaign_name = data.get("title") if data else campaign_id.replace("_", " ")

    # Find seed entity — prefer type='campaign', case-insensitive name match
    stmt = select(KnowledgeEntity).where(
        KnowledgeEntity.name.ilike(campaign_name)
    )
    result = await db.execute(stmt)
    candidates = result.scalars().all()
    seed = None
    for c in candidates:
        if c.type == "campaign":
            seed = c
            break
    if not seed and candidates:
        seed = candidates[0]

    if not seed:
        # Partial match
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.name.ilike(f"%{campaign_id.replace('_', '%')}%")
        )
        result = await db.execute(stmt)
        seed = result.scalars().first()

    if not seed:
        return KGResponse(nodes=[], edges=[])

    # BFS traversal using entity UUIDs
    visited_ids: set[str] = set()
    nodes: list[dict] = []
    edges: list[dict] = []

    def _add_entity_node(entity: KnowledgeEntity):
        eid = str(entity.id)
        if eid in visited_ids:
            return
        visited_ids.add(eid)
        etype = entity.type or "concept"
        color = _TYPE_COLORS.get(etype, _DEFAULT_COLOR)
        props = entity.properties or {}
        tooltip_parts = [f"Type: {etype}"]
        for k, v in list(props.items())[:5]:
            tooltip_parts.append(f"{k}: {v}")

        nodes.append({
            "id": eid,
            "label": entity.name,
            "group": etype,
            "color": color,
            "title": "\n".join(tooltip_parts),
        })

    # Add seed
    _add_entity_node(seed)

    queue: deque[tuple[str, int]] = deque([(str(seed.id), 0)])

    while queue:
        entity_uuid, depth = queue.popleft()

        if depth >= max_depth:
            continue

        # Relations FROM this entity
        stmt = select(KnowledgeRelation).where(
            KnowledgeRelation.from_entity == entity_uuid
        )
        result = await db.execute(stmt)
        outgoing = result.scalars().all()

        for rel in outgoing:
            to_id = str(rel.to_entity)
            edges.append({
                "from": entity_uuid,
                "to": to_id,
                "label": rel.relation_type or "",
                "arrows": "to",
            })
            if to_id not in visited_ids:
                e_stmt = select(KnowledgeEntity).where(KnowledgeEntity.id == rel.to_entity)
                e_result = await db.execute(e_stmt)
                target = e_result.scalars().first()
                if target:
                    _add_entity_node(target)
                    queue.append((to_id, depth + 1))

        # Relations TO this entity
        stmt = select(KnowledgeRelation).where(
            KnowledgeRelation.to_entity == entity_uuid
        )
        result = await db.execute(stmt)
        incoming = result.scalars().all()

        for rel in incoming:
            from_id = str(rel.from_entity)
            edges.append({
                "from": from_id,
                "to": entity_uuid,
                "label": rel.relation_type or "",
                "arrows": "to",
            })
            if from_id not in visited_ids:
                e_stmt = select(KnowledgeEntity).where(KnowledgeEntity.id == rel.from_entity)
                e_result = await db.execute(e_stmt)
                source = e_result.scalars().first()
                if source:
                    _add_entity_node(source)
                    queue.append((from_id, depth + 1))

    # Deduplicate edges
    seen_edges: set[str] = set()
    unique_edges: list[dict] = []
    for edge in edges:
        key = f"{edge['from']}→{edge['to']}:{edge['label']}"
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(edge)

    return KGResponse(nodes=nodes, edges=unique_edges)
