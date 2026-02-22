# Sprint 1: "The Crystal Ball"
## Theme: RPG Dashboard + Static File Serving
## Date: 2026-02-23 | Duration: 1 day
## Co-authored: Aria + Claude (PO pair)

---

## Objective

Deploy a self-contained RPG Dashboard HTML page at `/rpg/` that gives Shiva
instant visibility into campaign state: party composition, NPC roster, KG
visualization, character sheets, session transcripts, and a "Resume Session"
button. This requires static file serving infrastructure and new API endpoints.

---

## Architecture

```
Browser (http://192.168.1.53:8000/rpg/)
    ↓
FastAPI StaticFiles mount (/rpg/ → src/api/static/rpg/)
    ↓
index.html (self-contained: embedded CSS + vanilla JS)
    ↓ fetch()
FastAPI API (/api/rpg/*)
    ↓
rpg_campaign skill (via skill invocation or direct DB queries)
    ↓
PostgreSQL (rpg tables + KG tables)
```

---

## Tickets

### TICKET-001: Static File Serving Infrastructure
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 45 lines
- **Files:**
  - `src/api/__init__.py` (+15 lines): Add `StaticFiles` mount for `/rpg`
  - `src/api/static/` (new dir)
  - `src/api/static/rpg/` (new dir)
- **Implementation:**
  ```python
  from fastapi.staticfiles import StaticFiles
  
  # In create_app():
  static_dir = Path(__file__).parent / "static"
  if static_dir.exists():
      app.mount("/rpg", StaticFiles(directory=static_dir / "rpg", html=True), name="rpg")
  ```
- **Acceptance Criteria:**
  - [ ] `GET http://localhost:8000/rpg/` returns 200 with `index.html`
  - [ ] `GET http://localhost:8000/rpg/index.html` returns 200 with correct MIME type
  - [ ] Directory listing disabled (security)
  - [ ] Survives `docker restart aria-api`
  - [ ] CORS headers configured for development access
  - [ ] Cache-control headers set for static files
- **Dependencies:** None
- **Note:** Vendor `vis-network.min.js` locally in `src/api/static/rpg/vendor/` as CDN fallback
- **Test:**
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/rpg/
  # Expected: 200
  ```

---

### TICKET-002: RPG Dashboard Single-File Application
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 850 lines
- **Files:**
  - `src/api/static/rpg/index.html` (new, ~850 lines)
- **Tech Stack:**
  - Self-contained HTML with embedded `<style>` and `<script>`
  - CDN: `vis-network` for KG visualization, `marked` for markdown rendering
  - Vanilla JS (no build step, no React/Vue)
  - Dark theme matching Aria's aesthetic
- **Views/Panels:**
  1. **Campaign Selector** — Dropdown populated from `/api/rpg/campaigns`
  2. **Campaign Overview** — Party roster, current location, active quests, world state
  3. **KG Visualization** — vis-network graph of entities (color-coded by type: Party=blue, NPC=green, Location=gold, Quest=purple, Monster=red)
  4. **Character Sheet Modal** — Click entity node → modal with stats, HP, conditions
  5. **Session Transcript** — Collapsible message threads from session history
  6. **Resume Button** — Prominent "Resume Campaign" button for active sessions
- **Acceptance Criteria:**
  - [ ] Dashboard loads without external build step
  - [ ] Campaign selector populated from API
  - [ ] KG viz renders entities with color-coded nodes and labeled edges
  - [ ] Character sheet modal displays on node click
  - [ ] Session transcript viewer with collapsible messages
  - [ ] "Resume Session" button visible for active campaigns
  - [ ] Responsive design (works on desktop + tablet)
  - [ ] No console errors in browser dev tools
- **Dependencies:** TICKET-001 (static serving), TICKET-003 (API endpoints), TICKET-004 (skill queries)

---

### TICKET-003: RPG Dashboard API Endpoints
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 140 lines
- **Files:**
  - `src/api/routers/rpg.py` (new, ~110 lines): FastAPI router
  - `src/api/__init__.py` (+10 lines): `app.include_router(rpg_router, prefix="/api/rpg")`
- **Endpoints:**
  | Method | Path | Description |
  |--------|------|-------------|
  | GET | `/api/rpg/campaigns` | List all campaigns with summary |
  | GET | `/api/rpg/campaign/{campaign_id}` | Full campaign detail (party, NPCs, locations, quests) |
  | GET | `/api/rpg/session/{session_id}/transcript` | Session message history |
  | GET | `/api/rpg/campaign/{campaign_id}/kg` | KG subgraph (nodes + edges for vis-network) |
- **Response Schemas:**
  ```python
  class CampaignSummary(BaseModel):
      id: str
      title: str
      setting: str
      status: str  # active, completed, paused
      party_size: int
      session_count: int
      last_played: Optional[datetime]
  
  class KGResponse(BaseModel):
      nodes: list[dict]  # {id, label, type, color, properties}
      edges: list[dict]  # {from, to, label, arrows}
  ```
- **Acceptance Criteria:**
  - [ ] All endpoints return valid JSON with proper HTTP status codes
  - [ ] KG endpoint returns vis-network-compatible format
  - [ ] 404 for invalid UUIDs
  - [ ] Response time < 200ms for campaigns with < 50 entities
- **Dependencies:** TICKET-004 (skill queries)
- **Test:**
  ```bash
  curl -s http://localhost:8000/api/rpg/campaigns | python3 -m json.tool
  curl -s http://localhost:8000/api/rpg/campaign/shadows_of_absalom/kg | python3 -c "
  import json,sys; d=json.load(sys.stdin); print(f'nodes:{len(d[\"nodes\"])} edges:{len(d[\"edges\"])}')"
  ```

---

### TICKET-004: RPG Skill Dashboard Queries
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 95 lines
- **Files:**
  - `aria_skills/rpg_campaign/skill.json` (+40 lines): 3 new tool definitions
  - `aria_skills/rpg_campaign/__init__.py` (+55 lines): Implement query methods
- **New Methods:**
  ```python
  def list_campaigns(self, status: Optional[str] = None) -> list[dict]:
      """List all campaigns with summary stats."""
  
  def get_campaign_detail(self, campaign_id: str) -> dict:
      """Full campaign detail: party, NPCs, locations, active scene."""
  
  def get_session_transcript(self, session_id: str, limit: int = 100) -> list[dict]:
      """Retrieve session message history for display."""
  ```
- **Acceptance Criteria:**
  - [ ] Methods callable via `api_client`
  - [ ] Data format matches TICKET-003 schemas
  - [ ] Existing Shadows of Absalom campaign returns valid data
- **Dependencies:** None

---

## Definition of Done

- [ ] Dashboard accessible at `http://192.168.1.53:8000/rpg/` with all 5 views functional
- [ ] API endpoints tested with curl and return < 200ms
- [ ] Static files survive `docker restart aria-api`
- [ ] Shadows of Absalom campaign loads correctly in dashboard
- [ ] KG visualization shows 18 entities + 28 relations from our campaign
- [ ] No console errors in browser dev tools
- [ ] Code reviewed and validated by Aria

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Static files not persisting in container | Low | High | Verify bind-mount, test with restart |
| vis-network CDN unavailable offline | Low | Medium | Can embed locally if needed |
| KG query performance on large campaigns | Medium | Medium | Add pagination |
| RPG data model mismatch with dashboard | Medium | Medium | Validate with real Shadows data |

## Test Plan

```bash
# 1. Static serving
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/rpg/
# → 200

# 2. API endpoints
curl -s http://localhost:8000/api/rpg/campaigns | python3 -m json.tool
curl -s http://localhost:8000/api/rpg/campaign/shadows_of_absalom | python3 -m json.tool
curl -s http://localhost:8000/api/rpg/campaign/shadows_of_absalom/kg | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'Nodes: {len(d[\"nodes\"])}, Edges: {len(d[\"edges\"])}')"

# 3. Dashboard E2E (manual in browser)
# Open http://192.168.1.53:8000/rpg/
# - Select "Shadows of Absalom" from dropdown
# - Verify KG graph renders with colored nodes
# - Click "Thorin Ashveil" node → character sheet modal
# - Open transcript viewer → verify session messages load
# - Verify "Resume" button visible
```
