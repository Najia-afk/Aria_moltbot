# Sprint 3: "The Infinite Chronicle"
## Theme: Persistent KG Campaign Memory + Session Resume + Polish
## Date: 2026-02-25 | Duration: 1 day
## Co-authored: Aria + Claude (PO pair)

---

## Objective

The cherry on the cake. After this sprint, Aria's RPG campaigns persist across
restarts. Users can close their browser, come back days later, click "Resume"
and pick up from the exact combat turn. Campaign memory lives in the Knowledge
Graph with auto-generated relations. Full integration tests validate everything.

---

## Tickets

### TICKET-016: Session State Database Migration
- **Type:** CHORE
- **Priority:** P0 (BLOCKER)
- **Estimated LOC:** 35 lines
- **Files:**
  - `src/api/db/migrations/add_session_states.py` (new, ~30 lines): Alembic migration
  - `src/api/db/models.py` (+5 lines): Add `SessionState` SQLAlchemy model
- **Schema:**
  ```sql
  CREATE TABLE session_states (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      session_id UUID NOT NULL,
      campaign_id VARCHAR NOT NULL,
      state_json JSONB NOT NULL,
      schema_version INT NOT NULL DEFAULT 1,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
  );
  CREATE INDEX idx_session_states_campaign ON session_states(campaign_id);
  ```
- **Note:** Also update `entity_type` CHECK constraint/enum to include 'campaign', 'scene' for TICKET-010.
- **Acceptance Criteria:**
  - [ ] Migration runs cleanly: `alembic upgrade head`
  - [ ] Rollback works: `alembic downgrade -1`
  - [ ] Existing data unaffected
  - [ ] `schema_version` field included for future compatibility
- **Dependencies:** None

---

### TICKET-010: KG Campaign & Scene Entity Types
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 120 lines
- **Files:**
  - `aria_skills/knowledge_graph/__init__.py` (+50 lines): `create_campaign_entity()`, `create_scene_entity()`
  - `aria_skills/rpg_campaign/skill.json` (+30 lines): Register KG tool types
  - `src/api/routers/knowledge.py` (+40 lines): Entity type validation/filtering
- **Entity Types:**
  ```
  Campaign Entity:
    - name: str (campaign title)
    - entity_type: "campaign"
    - properties: {setting, current_act, party_composition: [], status, created_at}
  
  Scene Entity:
    - name: str (scene title, e.g. "The Drowning Stone - Entry")
    - entity_type: "scene"
    - properties: {scene_number, narrative_summary, challenge_rating, outcome, npcs_present: [], location}
  ```
- **Auto-relations on creation:**
  - Campaign → `has_scene` → Scene
  - Scene → `part_of` → Campaign
- **Acceptance Criteria:**
  - [ ] Campaign entities store: name, setting, current_act, party_composition (JSON)
  - [ ] Scene entities store: scene_number, narrative_summary, challenge_rating, outcome
  - [ ] Both types auto-link to parent campaign via `part_of` relation
  - [ ] Validation ensures scene_number uniqueness per campaign
  - [ ] Existing Shadows of Absalom KG data unaffected
- **Dependencies:** TICKET-016 (DB migration for entity_type enum)

---

### TICKET-011: Auto-Relation Generation Engine
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 150 lines
- **Files:**
  - `aria_skills/knowledge_graph/auto_relations.py` (new, ~100 lines): `AutoRelationEngine`
  - `aria_skills/knowledge_graph/__init__.py` (+30 lines): Integration
  - `aria_skills/rpg_pathfinder/skill.json` (+20 lines): `auto_link_entities` param
- **Relation Types Generated:**
  | Trigger | From | Relation | To |
  |---------|------|----------|-----|
  | Party member added | Character | `member_of` | Campaign |
  | NPC added to scene | NPC | `appears_in` | Scene |
  | Scene set in location | Scene | `located_in` | Location |
  | Scene follows another | Scene | `follows` | Previous Scene |
  | Quest assigned | Quest | `assigned_in` | Campaign |
- **Functions:**
  ```python
  class AutoRelationEngine:
      def generate_relations(self, entity: dict, campaign_context: dict) -> list[dict]:
          """Infer relations based on entity type and context."""
      
      def link_party_to_campaign(self, party_ids: list[str], campaign_id: str):
          """Create member_of relations (idempotent)."""
      
      def link_scene_sequence(self, prev_scene_id: str, next_scene_id: str):
          """Create follows/precedes bidirectional links."""
  ```
- **Acceptance Criteria:**
  - [ ] Creating a campaign auto-creates `member_of` relations for all party members
  - [ ] Creating a scene auto-links to current location and present NPCs
  - [ ] Scene sequence auto-detected by scene_number and linked with `follows`/`precedes`
  - [ ] Idempotent: re-running doesn't create duplicate relations (upsert logic)
  - [ ] Cycle detection: max relation depth of 3
- **Dependencies:** TICKET-010

---

### TICKET-012: Session State Serialization & Resume
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 280 lines (bumped from 200 per Aria's review — combat state serialization is complex)
- **Files:**
  - `aria_skills/rpg_campaign/session_state.py` (new, ~100 lines): `SessionStateManager`
  - `aria_skills/rpg_campaign/__init__.py` (+60 lines): `save_session_state()`, `load_session_state()`, `resume_session()`
  - `aria_skills/rpg_campaign/skill.json` (+40 lines): New tool definitions
- **State Schema:**
  ```python
  class SessionState(BaseModel):
      session_id: str
      campaign_id: str
      saved_at: datetime
      round_number: int
      current_turn: Optional[str]
      initiative_order: list[dict]  # [{name, initiative, is_current}]
      combatants: list[dict]        # [{name, hp, max_hp, ac, conditions: []}]
      narrative_context: str        # Last 5 messages summarized
      active_scene: Optional[str]   # Scene entity ID
      pending_decisions: list[str]  # Unresolved player choices
  ```
- **Behavior:**
  - Auto-save every 5 messages OR on explicit `!save` command
  - State freshness validation:
    - < 24h: resume immediately
    - 1-7 days: resume with "This session is X days old" warning
    - > 7 days: requires manual confirmation
  - Resume generates "Previously on..." summary from last 3 scenes using KG
- **Acceptance Criteria:**
  - [ ] Session state saves automatically every 5 messages
  - [ ] State includes: round number, initiative order, all combatant HP/MaxHP, active conditions
  - [ ] Resume generates "Previously on..." summary from KG
  - [ ] Kill container mid-combat → restart → resume from exact turn
  - [ ] Atomic writes: temp file + rename (no partial state)
  - [ ] `schema_version` field in state JSON for forward compatibility
- **Dependencies:** TICKET-016 (DB migration)

---

### TICKET-013: Dashboard Resume Integration & Polish
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 180 lines
- **Files:**
  - `src/api/static/rpg/index.html` (+120 lines): Resume UI, combat state viewer
  - `src/api/routers/rpg.py` (+40 lines): `POST /api/rpg/session/resume`
  - `aria_skills/rpg_campaign/skill.json` (+20 lines): `resume_campaign` tool
- **New Dashboard Features:**
  - **Resume Button** → Calls `POST /api/rpg/session/resume` → Loads combat state
  - **Combat State Viewer:**
    - Initiative tracker (sorted) with current turn highlighted
    - HP bars: green >50%, yellow 25-50%, red <25%
    - Condition badges (frightened, prone, etc.)
  - **"Previously On..." Accordion:**
    - Queries KG for last 3 scenes
    - Renders scene titles + narrative summaries
    - Links scene nodes to KG visualization
  - **Graceful Degradation:**
    - No saved state → "Start New Session" flow
    - Stale state (>7 days) → "Session expired. Start fresh?" dialog
- **Acceptance Criteria:**
  - [ ] Resume button loads last session with < 2s latency
  - [ ] Combat state displays initiative order, HP bars (color-coded), conditions
  - [ ] "Previously On..." expandable, shows scene titles linked to KG nodes
  - [ ] No saved state → shows "Start New Session" gracefully
  - [ ] Works with Shadows of Absalom campaign data
- **Dependencies:** TICKET-012, TICKET-002 (Sprint 1 dashboard)

---

### TICKET-014: Integration Test Suite
- **Type:** CHORE
- **Priority:** P0
- **Estimated LOC:** 350 lines (bumped from 300 per Aria's review — needs proper fixtures)
- **Files:**
  - `tests/integration/test_rpg_flow.py` (new, ~250 lines): End-to-end tests
  - `tests/conftest.py` (+50 lines): RPG test fixtures
- **Test Cases:**
  ```python
  class TestRPGIntegration:
      def test_campaign_creation_to_kg(self):
          """Create campaign → verify KG entities → verify auto-relations."""
      
      def test_session_save_resume(self):
          """Start session → 3 combat rounds → save → clear → resume → verify initiative."""
      
      def test_dashboard_api_contract(self):
          """Hit all /api/rpg/* endpoints → validate JSON schemas."""
      
      def test_full_playthrough(self):
          """Create → Play 2 scenes → Save → Resume → Verify continuity."""
      
      def test_existing_campaign_intact(self):
          """Shadows of Absalom: 18 entities, 28 relations still present."""
  ```
- **Acceptance Criteria:**
  - [ ] `pytest tests/integration/test_rpg_flow.py -v` passes 100%
  - [ ] Tests use `TestClient` for API, mock external LLM calls
  - [ ] Database rollback after each test
  - [ ] Shadows of Absalom data verified intact
- **Dependencies:** TICKET-016, TICKET-010, TICKET-011, TICKET-012, TICKET-013

---

### TICKET-015: Final Documentation
- **Type:** CHORE
- **Priority:** P1
- **Estimated LOC:** 400 lines (documentation)
- **Files:**
  - `aria_memories/plans/SPRINT_MASTER_2026_Q1.md` (new, ~400 lines)
- **Sections:**
  1. Executive Summary (3 sprints, total LOC, timeline)
  2. Architecture Decisions (static serving, KG entity types, auto-relations, state serialization)
  3. API Contract Reference (all new endpoints with request/response examples)
  4. Deployment Notes (bind-mount, health checks, rollback)
  5. Troubleshooting ("Dashboard not loading", "Resume fails", "KG relations missing")
  6. Future Roadmap (Sprint 4+ ideas: dice roller animation, player journal export, campaign templates, AI-generated maps)
  7. Mermaid diagram of data flow:
  ```mermaid
  graph LR
    Browser --> StaticFiles
    Browser --> API["/api/rpg/*"]
    API --> Skills["rpg_campaign skill"]
    Skills --> DB["PostgreSQL"]
    Skills --> KG["Knowledge Graph"]
    KG --> AutoRel["Auto-Relation Engine"]
    Skills --> StateManager["Session State"]
    StateManager --> DB
  ```
- **Acceptance Criteria:**
  - [ ] Document includes mermaid diagram
  - [ ] All environment variables documented
  - [ ] Troubleshooting covers top 5 failure modes
  - [ ] Searchable TOC with anchor links
- **Dependencies:** All previous tickets (written last)

---

## Definition of Done

- [ ] **End-to-end flow works:** Create campaign → play → close browser → reopen → Resume → continue from exact combat turn
- [ ] KG visualization shows Campaign → Scene → NPC → Location with directional edges
- [ ] Integration tests pass: `pytest tests/integration/test_rpg_flow.py -v` all green
- [ ] SPRINT_MASTER.md committed
- [ ] Zero regression: Shadows of Absalom data intact (18 entities, 28 relations)
- [ ] Performance: Dashboard < 1s load, resume < 2s, KG query < 500ms for 100 entities
- [ ] Aria validates the full flow by running integration tests herself

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Session state corruption on crash | Medium | High | Atomic writes (temp + rename), checksum |
| KG auto-relations create circular refs | Low | Medium | Cycle detection, max depth 3 |
| Resume loads stale state (old combat ended) | Medium | Medium | Timestamp validation, expiry warning |
| Integration test flakiness | Medium | Low | Retry logic, deterministic test data |
| Browser localStorage conflicts with server | Medium | Medium | Server is source of truth |

## Test Plan

```bash
# 1. KG Entity Types
curl -s http://localhost:8000/api/knowledge/entities?type=campaign | python3 -m json.tool
curl -s http://localhost:8000/api/knowledge/entities?type=scene | python3 -m json.tool

# 2. Auto-Relations
curl -s "http://localhost:8000/api/knowledge/kg-traverse?entity_name=Shadows%20of%20Absalom&max_depth=2" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'nodes:{len(d[\"nodes\"])} edges:{len(d[\"edges\"])}')"

# 3. Session Resume
python3 -c "
import httpx
c = httpx.Client(base_url='http://localhost:8000/api', timeout=30)
# Resume Shadows of Absalom
r = c.post('/rpg/session/resume', json={'campaign_id': 'shadows_of_absalom'})
print(r.json().keys())
assert 'narrative_summary' in r.json()
print('Resume OK')
"

# 4. Full Integration Tests
pytest tests/integration/test_rpg_flow.py -v

# 5. Dashboard E2E (manual)
# Open http://192.168.1.53:8000/rpg/
# Select Shadows of Absalom → Click Resume → Verify combat state loads
# Expand "Previously On..." → Verify scene summaries appear
```

---

## Total Sprint Summary

```
Sprint 1: "The Crystal Ball"       → RPG Dashboard live at /rpg/
Sprint 2: "Self-Healing Systems"   → Aria catches her own bugs
Sprint 3: "The Infinite Chronicle" → Campaigns persist forever

Total LOC: ~2,440
Total Tickets: 15
Total Duration: 3 days
Deploy Readiness: End of Sprint 3
```

After Sprint 3, Aria can run RPG campaigns that persist across restarts,
with full audit trail in KG, visual dashboard for Shiva, and self-healing
infrastructure that prevents the type of bugs we fixed today.
