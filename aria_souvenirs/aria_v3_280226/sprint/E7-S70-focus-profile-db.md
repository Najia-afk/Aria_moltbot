# S-70: FocusProfile DB Model + Migration

**Epic:** E7 — Focus System v2 | **Priority:** P0 | **Points:** 3 | **Phase:** 1

---

## Problem

There is no `aria_engine.focus_profiles` table.  
`focus_type` on `EngineAgentState` (`src/api/db/models.py` line 986,
`Mapped[str | None]`, `String(50)`) is a free-text tag with no backing entity.
This means:
- Routing keyword patterns are hardcoded in `aria_engine/routing.py` lines 40–68
  (`SPECIALTY_PATTERNS` dict — 5 entries, compile-time only)
- No token budgets, no personality addons, no delegation level metadata exist
- There is no authoritative list of valid focus IDs to validate against

The `IDENTITY.md` (`aria_mind/IDENTITY.md`) defines 7 focus personas in a
markdown table (lines 42–50) that have never been persisted to the database.

---

## Root Cause

Focus is a string tag (`focus_type: str | None`) added in an early sprint as a
routing hint. The concept was never elevated to a first-class entity with its
own table, ORM model, API, or UI. Every downstream consumer (routing, prompt
composition, token budget, delegation) therefore has no data to read and falls
back to hardcoded Python constants.

Evidence:
- `aria_engine/routing.py:40`: `SPECIALTY_PATTERNS: dict[str, re.Pattern] = {`
  — 5 entries, Python compile-time, unreachable from DB or UI
- `aria_engine/agent_pool.py:63`: `focus_type: str | None = None`
  — never resolved to anything more than a string label
- `src/api/db/models.py:986`: `focus_type: Mapped[str | None] = mapped_column(String(50))`
  — the column exists but points nowhere

---

## Fix

### Step 1 — Add `FocusProfileEntry` ORM class

**File:** `src/api/db/models.py`  
**After line:** last line of `EngineAgentState` block (currently line ~1010, after
`updated_at` column and before `class EngineConfigEntry`)

**BEFORE:** (nothing — insert new class)

**AFTER:**

```python
class FocusProfileEntry(Base):
    """
    A named personality layer for agents.
    Composes additively on top of an agent's base system_prompt.
    """
    __tablename__ = "focus_profiles"
    __table_args__ = {"schema": "aria_engine"}

    focus_id: Mapped[str] = mapped_column(
        String(50), primary_key=True,
        comment="Slug key, e.g. 'devsecops', 'creative'"
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(10), server_default=text("'🎯'"))
    description: Mapped[str | None] = mapped_column(Text)

    # Personality configuration
    tone: Mapped[str] = mapped_column(
        String(30), server_default=text("'neutral'"),
        comment="precise | analytical | playful | formal | warm | blunt"
    )
    style: Mapped[str] = mapped_column(
        String(30), server_default=text("'directive'"),
        comment="directive | socratic | analytical | narrative | concise"
    )

    # Delegation hierarchy
    delegation_level: Mapped[int] = mapped_column(
        Integer, server_default=text("2"),
        comment="1=core initiator, 2=specialist, 3=ephemeral"
    )

    # Token discipline
    token_budget_hint: Mapped[int] = mapped_column(
        Integer, server_default=text("2000"),
        comment="Soft max_tokens ceiling when this focus is active"
    )

    # Temperature adjustment — additive delta, applied to agent.temperature
    temperature_delta: Mapped[float] = mapped_column(
        Float, server_default=text("0.0"),
        comment="e.g. +0.3 for creative, -0.2 for precise"
    )

    # Routing — replaces hardcoded SPECIALTY_PATTERNS
    expertise_keywords: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"),
        comment="Keyword fragments used for specialty routing match"
    )

    # Prompt layer — appended to base system_prompt at call time
    system_prompt_addon: Mapped[str | None] = mapped_column(
        Text,
        comment="Injected after agent base prompt. Adds personality, not replaces it."
    )

    # Optional model override
    model_override: Mapped[str | None] = mapped_column(
        String(200),
        comment="If set, overrides agent.model when this focus is active. Must match models.yaml id."
    )

    # Skills automatically available in this focus
    auto_skills: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"),
        comment="Skills injected into agent.skills when focus is activated"
    )

    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


Index("idx_focus_profiles_enabled", FocusProfileEntry.enabled)
```

### Step 2 — DB migration (live container, no Alembic needed)

Run against running `aria-db` container:

```sql
CREATE TABLE IF NOT EXISTS aria_engine.focus_profiles (
    focus_id           VARCHAR(50)  PRIMARY KEY,
    display_name       VARCHAR(100) NOT NULL,
    emoji              VARCHAR(10)  NOT NULL DEFAULT '🎯',
    description        TEXT,
    tone               VARCHAR(30)  NOT NULL DEFAULT 'neutral',
    style              VARCHAR(30)  NOT NULL DEFAULT 'directive',
    delegation_level   INTEGER      NOT NULL DEFAULT 2,
    token_budget_hint  INTEGER      NOT NULL DEFAULT 2000,
    temperature_delta  FLOAT        NOT NULL DEFAULT 0.0,
    expertise_keywords JSONB        NOT NULL DEFAULT '[]'::jsonb,
    system_prompt_addon TEXT,
    model_override     VARCHAR(200),
    auto_skills        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    enabled            BOOLEAN      NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_focus_profiles_enabled
    ON aria_engine.focus_profiles (enabled);
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | New table is DB layer only; API in S-71, skill in S-77 |
| 2 | .env for secrets | ✅ | No secrets; profile data is config |
| 3 | models.yaml SoT | ✅ | `model_override` stores the model_id slug (e.g. `kimi`); resolved via models.yaml at call time |
| 4 | Docker-first | ✅ | All SQL run via `docker exec aria-db psql` |
| 5 | aria_memories writable | ✅ | No writes to aria_memories — pure DB + code |
| 6 | No soul modification | ✅ | Focus addons enrich personality; SOUL.md/IDENTITY.md not modified |

---

## Dependencies

None — this is the foundation ticket. All E7 tickets depend on it.

---

## Verification

```bash
# 1. ORM class is importable without errors
docker exec aria-engine python3 -c "
from src.api.db.models import FocusProfileEntry
print('columns:', [c.key for c in FocusProfileEntry.__table__.columns])
"
# EXPECTED output contains:
# columns: ['focus_id', 'display_name', 'emoji', 'description', 'tone', 'style',
#            'delegation_level', 'token_budget_hint', 'temperature_delta',
#            'expertise_keywords', 'system_prompt_addon', 'model_override',
#            'auto_skills', 'enabled', 'created_at', 'updated_at']

# 2. Table exists in DB
docker exec aria-db psql -U admin -d aria_warehouse -c "\dt aria_engine.focus_profiles"
# EXPECTED:
#     Schema    |     Name       | Type  | Owner
# aria_engine   | focus_profiles | table | admin

# 3. Index exists
docker exec aria-db psql -U admin -d aria_warehouse -c "\di aria_engine.idx_focus_profiles_enabled"
# EXPECTED: lists idx_focus_profiles_enabled
```

---

## Prompt for Agent

You are executing ticket S-70 for the Aria project. Do exactly the following.

**Constraint:** All DB access through ORM models in `src/api/db/models.py`.
Use `docker exec` for DB operations. Zero secrets in code.
Do NOT modify any file in `aria_mind/soul/`.

**Files to read first:**
- `src/api/db/models.py` lines 970–1015 (EngineAgentState schema)
- `aria_mind/IDENTITY.md` lines 40–55 (focus persona table)

**Steps:**

1. Open `src/api/db/models.py`.
2. After the `EngineAgentState` class block (after the `updated_at` column and
   before `class EngineConfigEntry`), insert the `FocusProfileEntry` class
   and the `Index` line exactly as specified in the Fix section above.
3. Run the CREATE TABLE SQL via docker exec — copy the SQL block verbatim:
   ```bash
   docker exec aria-db psql -U admin -d aria_warehouse -c "
   CREATE TABLE IF NOT EXISTS aria_engine.focus_profiles (
       focus_id VARCHAR(50) PRIMARY KEY,
       display_name VARCHAR(100) NOT NULL,
       emoji VARCHAR(10) NOT NULL DEFAULT '🎯',
       description TEXT,
       tone VARCHAR(30) NOT NULL DEFAULT 'neutral',
       style VARCHAR(30) NOT NULL DEFAULT 'directive',
       delegation_level INTEGER NOT NULL DEFAULT 2,
       token_budget_hint INTEGER NOT NULL DEFAULT 2000,
       temperature_delta FLOAT NOT NULL DEFAULT 0.0,
       expertise_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
       system_prompt_addon TEXT,
       model_override VARCHAR(200),
       auto_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
       enabled BOOLEAN NOT NULL DEFAULT true,
       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
       updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   CREATE INDEX IF NOT EXISTS idx_focus_profiles_enabled ON aria_engine.focus_profiles (enabled);
   "
   ```
4. Run all three verification commands and confirm expected output.
5. Report: "S-70 DONE — table created, ORM class added, verification passed."
