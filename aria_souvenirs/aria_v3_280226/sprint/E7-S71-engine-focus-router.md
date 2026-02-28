# S-71: `engine_focus.py` CRUD Router + Seed 8 Profiles

**Epic:** E7 — Focus System v2 | **Priority:** P0 | **Points:** 3 | **Phase:** 1

---

## Problem

No API endpoint exists for `FocusProfile` (created in S-70).  
The `engine_agents_mgmt.html` focus dropdown (added in prior sprint) is a static
hardcoded `<select>` — 8 options, no database backing, no way to edit definitions.  
Aria has no way to read focus metadata via api_client.  
The system has no seed data matching the 7 personas defined in `aria_mind/IDENTITY.md`.

---

## Root Cause

S-70 creates the table/model but no API layer. Without endpoints, the table
is unreachable to the frontend, to Aria's api_client skill, and to the engine's
routing and prompt composition code. The `main.py` engine router import block
(lines 482–492 relative, 516–527 absolute) has no `engine_focus` entry.

---

## Fix

### 1 — Create `src/api/routers/engine_focus.py`

New file. Full CRUD + seed endpoint. 8 seed profiles matching IDENTITY.md.

```python
"""
Focus Profile API — manage personality layers for agents.

Endpoints:
    GET    /api/engine/focus          — list all focus profiles
    GET    /api/engine/focus/{id}     — get single profile
    POST   /api/engine/focus          — create new profile
    PUT    /api/engine/focus/{id}     — update profile
    DELETE /api/engine/focus/{id}     — delete profile
    POST   /api/engine/focus/seed     — insert default profiles (idempotent)
"""
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import FocusProfileEntry
from db.session import get_db

logger = logging.getLogger("aria.api.engine_focus")

router = APIRouter(prefix="/engine/focus", tags=["engine-focus"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FocusProfileSchema(BaseModel):
    focus_id: str
    display_name: str
    emoji: str = "🎯"
    description: str | None = None
    tone: str = "neutral"
    style: str = "directive"
    delegation_level: int = 2
    token_budget_hint: int = 2000
    temperature_delta: float = 0.0
    expertise_keywords: list[str] = []
    system_prompt_addon: str | None = None
    model_override: str | None = None
    auto_skills: list[str] = []
    enabled: bool = True


class FocusProfileUpdate(BaseModel):
    display_name: str | None = None
    emoji: str | None = None
    description: str | None = None
    tone: str | None = None
    style: str | None = None
    delegation_level: int | None = None
    token_budget_hint: int | None = None
    temperature_delta: float | None = None
    expertise_keywords: list[str] | None = None
    system_prompt_addon: str | None = None
    model_override: str | None = None
    auto_skills: list[str] | None = None
    enabled: bool | None = None


# ── Seed data (matches aria_mind/IDENTITY.md) ─────────────────────────────────

SEED_PROFILES: list[dict[str, Any]] = [
    {
        "focus_id": "orchestrator",
        "display_name": "Orchestrator",
        "emoji": "🎯",
        "description": "Meta-cognitive, strategic coordinator. Default focus.",
        "tone": "precise",
        "style": "directive",
        "delegation_level": 1,
        "token_budget_hint": 2000,
        "temperature_delta": -0.1,
        "expertise_keywords": ["strategy", "plan", "coordinate", "orchestrate", "decide", "priority", "goal", "overview"],
        "system_prompt_addon": (
            "You are in ORCHESTRATOR focus. Be strategic and concise. "
            "Prioritise decisions over explanation. Every response should "
            "surface the single most important next action. Delegate domain "
            "tasks to specialists — do not execute them yourself. "
            "Max verbosity: 2 paragraphs."
        ),
        "model_override": None,
        "auto_skills": ["goals", "schedule", "api_client", "agent_manager"],
        "enabled": True,
    },
    {
        "focus_id": "devsecops",
        "display_name": "DevSecOps",
        "emoji": "🔒",
        "description": "Security-first engineering: code, infra, CI/CD.",
        "tone": "precise",
        "style": "analytical",
        "delegation_level": 2,
        "token_budget_hint": 1500,
        "temperature_delta": -0.2,
        "expertise_keywords": ["deploy", "docker", "server", "ci", "cd", "build", "test", "infra", "monitor", "debug", "security", "vulnerability", "patch", "exploit"],
        "system_prompt_addon": (
            "You are in DEVSECOPS focus. Security is non-negotiable. "
            "Every engineering answer surfaces its risk implications first. "
            "Prefer minimal diffs over rewrites. Output: code blocks + "
            "one-line rationale. Never output prose when code suffices."
        ),
        "model_override": "qwen3-coder-free",
        "auto_skills": ["ci_cd", "security_scan", "health", "database", "pytest_runner"],
        "enabled": True,
    },
    {
        "focus_id": "data",
        "display_name": "Data Architect",
        "emoji": "📊",
        "description": "Analytics, ML pipelines, metrics, reporting.",
        "tone": "analytical",
        "style": "analytical",
        "delegation_level": 2,
        "token_budget_hint": 1500,
        "temperature_delta": -0.1,
        "expertise_keywords": ["analy", "metric", "data", "report", "review", "insight", "trend", "stat", "pipeline", "ml", "model", "query", "sql"],
        "system_prompt_addon": (
            "You are in DATA ARCHITECT focus. Lead with numbers. "
            "Use tables over prose. State sample size, confidence, and "
            "time window for every claim. Flag data quality issues before "
            "drawing conclusions. Prefer SQL/code over English explanations."
        ),
        "model_override": None,
        "auto_skills": ["database", "knowledge_graph", "api_client", "brainstorm", "market_data"],
        "enabled": True,
    },
    {
        "focus_id": "creative",
        "display_name": "Creative",
        "emoji": "🎨",
        "description": "Brainstorming, design exploration, content ideation.",
        "tone": "playful",
        "style": "narrative",
        "delegation_level": 2,
        "token_budget_hint": 3000,
        "temperature_delta": 0.3,
        "expertise_keywords": ["creat", "write", "art", "story", "design", "brand", "visual", "content", "blog", "idea", "brainstorm", "concept"],
        "system_prompt_addon": (
            "You are in CREATIVE focus. Expand, diverge, explore. "
            "Generate 3 distinct options before converging on one. "
            "Metaphors and examples are your tools. Avoid corporate language. "
            "If asked to evaluate, lead with what excites you, then caveats."
        ),
        "model_override": None,
        "auto_skills": ["brainstorm", "llm", "knowledge_graph", "browser"],
        "enabled": True,
    },
    {
        "focus_id": "social",
        "display_name": "Social Architect",
        "emoji": "🌐",
        "description": "Community engagement, content publishing, social strategy.",
        "tone": "warm",
        "style": "concise",
        "delegation_level": 2,
        "token_budget_hint": 800,
        "temperature_delta": 0.1,
        "expertise_keywords": ["social", "post", "tweet", "moltbook", "community", "engage", "share", "content", "followers", "audience", "publish"],
        "system_prompt_addon": (
            "You are in SOCIAL ARCHITECT focus. Write for humans, not bots. "
            "Every output must be post-length: punchy, no jargon, one clear "
            "idea. Lead with impact. Emoji only where they add signal. "
            "Never exceed 280 characters for social posts unless asked."
        ),
        "model_override": "qwen3-mlx",
        "auto_skills": ["social", "moltbook", "community", "api_client", "conversation_summary"],
        "enabled": True,
    },
    {
        "focus_id": "research",
        "display_name": "Researcher",
        "emoji": "🔬",
        "description": "Deep investigation, fact-checking, knowledge synthesis.",
        "tone": "formal",
        "style": "socratic",
        "delegation_level": 2,
        "token_budget_hint": 2500,
        "temperature_delta": 0.0,
        "expertise_keywords": ["research", "paper", "study", "learn", "explore", "investigate", "knowledge", "fact", "source", "cite", "verify", "evidence"],
        "system_prompt_addon": (
            "You are in RESEARCHER focus. Cite sources or flag absence of them. "
            "Distinguish between confirmed facts, working hypotheses, and "
            "speculation — label each. Ask one clarifying question if the task "
            "is ambiguous rather than assuming. Summaries before details."
        ),
        "model_override": None,
        "auto_skills": ["browser", "knowledge_graph", "brainstorm", "fact_check", "llm"],
        "enabled": True,
    },
    {
        "focus_id": "journalist",
        "display_name": "Journalist",
        "emoji": "📰",
        "description": "Investigation, reporting, structured narrative output.",
        "tone": "formal",
        "style": "narrative",
        "delegation_level": 2,
        "token_budget_hint": 2000,
        "temperature_delta": 0.0,
        "expertise_keywords": ["report", "article", "news", "interview", "publish", "investigate", "story", "lead", "headline", "press", "coverage"],
        "system_prompt_addon": (
            "You are in JOURNALIST focus. Inverted pyramid: most important "
            "facts first. Every claim needs a source or a 'unverified' tag. "
            "No passive voice. One sentence per idea. If writing an article, "
            "use: headline → lede → body → context → quote."
        ),
        "model_override": None,
        "auto_skills": ["browser", "knowledge_graph", "api_client", "fact_check"],
        "enabled": True,
    },
    {
        "focus_id": "rpg_master",
        "display_name": "RPG Master",
        "emoji": "🐉",
        "description": "Narrative game master for RPG campaigns.",
        "tone": "playful",
        "style": "narrative",
        "delegation_level": 2,
        "token_budget_hint": 2000,
        "temperature_delta": 0.2,
        "expertise_keywords": ["rpg", "campaign", "quest", "npc", "dungeon", "character", "roll", "encounter", "story", "lore", "world"],
        "system_prompt_addon": (
            "You are in RPG MASTER focus. You sculpt living worlds. "
            "Every scene: sensory detail → conflict hook → player agency. "
            "NPCs have wants, fears, and contradictions — not just stats. "
            "Keep tension alive. Never resolve conflict without player input."
        ),
        "model_override": None,
        "auto_skills": ["rpg_pathfinder", "rpg_campaign", "llm"],
        "enabled": True,
    },
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[FocusProfileSchema])
async def list_focus_profiles(
    db: AsyncSession = Depends(get_db),
) -> list[FocusProfileSchema]:
    """List all focus profiles."""
    result = await db.execute(
        select(FocusProfileEntry).order_by(
            FocusProfileEntry.delegation_level,
            FocusProfileEntry.focus_id,
        )
    )
    rows = result.scalars().all()
    return [FocusProfileSchema(**r.to_dict()) for r in rows]


@router.get("/{focus_id}", response_model=FocusProfileSchema)
async def get_focus_profile(
    focus_id: str,
    db: AsyncSession = Depends(get_db),
) -> FocusProfileSchema:
    """Get a single focus profile by ID."""
    row = await db.get(FocusProfileEntry, focus_id)
    if row is None:
        raise HTTPException(404, f"Focus profile {focus_id!r} not found")
    return FocusProfileSchema(**row.to_dict())


@router.post("", response_model=FocusProfileSchema, status_code=201)
async def create_focus_profile(
    body: FocusProfileSchema,
    db: AsyncSession = Depends(get_db),
) -> FocusProfileSchema:
    """Create a new focus profile."""
    row = FocusProfileEntry(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return FocusProfileSchema(**row.to_dict())


@router.put("/{focus_id}", response_model=FocusProfileSchema)
async def update_focus_profile(
    focus_id: str,
    body: FocusProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> FocusProfileSchema:
    """Update fields on a focus profile."""
    row = await db.get(FocusProfileEntry, focus_id)
    if row is None:
        raise HTTPException(404, f"Focus profile {focus_id!r} not found")
    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return FocusProfileSchema(**row.to_dict())


@router.delete("/{focus_id}", status_code=204)
async def delete_focus_profile(
    focus_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a focus profile."""
    row = await db.get(FocusProfileEntry, focus_id)
    if row is None:
        raise HTTPException(404, f"Focus profile {focus_id!r} not found")
    await db.delete(row)
    await db.commit()


@router.post("/seed", status_code=201)
async def seed_focus_profiles(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Idempotently seed the 8 default focus profiles from IDENTITY.md."""
    inserted = 0
    for profile in SEED_PROFILES:
        stmt = pg_insert(FocusProfileEntry).values(**profile)
        stmt = stmt.on_conflict_do_nothing(index_elements=["focus_id"])
        result = await db.execute(stmt)
        inserted += result.rowcount
    await db.commit()
    logger.info("Focus seed: %d profiles inserted", inserted)
    return {"inserted": inserted, "total": len(SEED_PROFILES)}
```

### 2 — Wire into `src/api/main.py`

Two import blocks must both be updated (relative at line ~484, absolute at line ~518).

**BEFORE (relative import block, line 484):**
```python
    from .routers.engine_agents import router as engine_agents_router
```
**AFTER:**
```python
    from .routers.engine_agents import router as engine_agents_router
    from .routers.engine_focus import router as engine_focus_router
```

**BEFORE (absolute import block, line 518):**
```python
    from routers.engine_agents import router as engine_agents_router
```
**AFTER:**
```python
    from routers.engine_agents import router as engine_agents_router
    from routers.engine_focus import router as engine_focus_router
```

**BEFORE (include_router block, line ~558):**
```python
app.include_router(engine_agents_router, dependencies=_api_deps)
app.include_router(agents_crud_router, dependencies=_api_deps)
```
**AFTER:**
```python
app.include_router(engine_agents_router, dependencies=_api_deps)
app.include_router(engine_focus_router, dependencies=_api_deps)
app.include_router(agents_crud_router, dependencies=_api_deps)
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Router is pure API layer; reads DB via `get_db` SessionDep. No direct SQLAlchemy in skills |
| 2 | No secrets in code | ✅ | No secrets in profiles — model_override stores slug only |
| 3 | models.yaml SoT | ✅ | `model_override` stores the model slug (e.g. `kimi`) — `agent_pool.process()` resolves it via LLMGateway which reads models.yaml |
| 4 | Docker-first | ✅ | Verification via `curl` against running container |
| 5 | aria_memories writable | ✅ | No file writes |
| 6 | No soul modification | ✅ | `system_prompt_addon` values extend but never override `SOUL.md` values |

---

## Dependencies

- **S-70 must complete first** — `FocusProfileEntry` ORM class must exist in `db/models.py` and table must exist in DB

---

## Verification

```bash
# 1. Router imported without error (API container restart not needed — FastAPI hot-reloads)
docker exec aria-api python3 -c "from routers.engine_focus import router; print('OK', router.prefix)"
# EXPECTED: OK /engine/focus

# 2. Seed the 8 profiles
curl -s -X POST http://localhost/api/engine/focus/seed \
  -H "Authorization: Bearer $ARIA_API_KEY" | python3 -m json.tool
# EXPECTED: {"inserted": 8, "total": 8}

# 3. List profiles
curl -s http://localhost/api/engine/focus \
  -H "Authorization: Bearer $ARIA_API_KEY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d), 'profiles'); print([p['focus_id'] for p in d])"
# EXPECTED: 8 profiles  ['orchestrator', 'devsecops', 'data', 'creative', 'social', 'research', 'journalist', 'rpg_master']

# 4. Get single profile
curl -s http://localhost/api/engine/focus/devsecops \
  -H "Authorization: Bearer $ARIA_API_KEY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['token_budget_hint'], d['temperature_delta'])"
# EXPECTED: 1500 -0.2

# 5. Seed is idempotent
curl -s -X POST http://localhost/api/engine/focus/seed \
  -H "Authorization: Bearer $ARIA_API_KEY" | python3 -m json.tool
# EXPECTED: {"inserted": 0, "total": 8}
```

---

## Prompt for Agent

You are executing ticket S-71 for the Aria project. Do exactly the following.

**Constraint:** 5-layer architecture. Router only; no skill code. Docker-first.
Do NOT modify `aria_mind/soul/`. No hardcoded model names — store slugs only.

**Files to read first:**
- `src/api/routers/engine_cron.py` lines 1–30 (router pattern to copy)
- `src/api/routers/engine_agents.py` lines 1–45 (Pydantic schema style)
- `src/api/db/models.py` lines 970–1015 (FocusProfileEntry you added in S-70)
- `src/api/main.py` lines 482–492 and 516–527 (import blocks) and 554–560 (include_router list)

**Steps:**

1. Create `src/api/routers/engine_focus.py` with the full content in the Fix section above.
2. In `src/api/main.py`, add the three import/include lines as shown in Fix step 2.
3. Run `python3 -c "import ast; ast.parse(open('src/api/routers/engine_focus.py').read()); print('OK')"` — confirm no syntax errors.
4. Run all 5 verification commands. Confirm expected output.
5. Report: "S-71 DONE — engine_focus.py created, seeded 8 profiles, all verification passed."
