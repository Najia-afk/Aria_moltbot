# Aria v3 Sprint — 2026-02-27
## Sprint Overview

**Sprint Goal:** End-to-end test coverage, full visualization & graph execution capabilities for all memory types, chat tool execution DAG, unified search, and navigation consolidation.

**Total Tickets:** 9 | **Total Points:** 47 | **Estimated:** ~38 hours

**Audit Sources:**
- Visualization & graph capability discovery (44 templates, 32 API routers)
- Expert subagent: Architecture compliance (3 review passes)
- Expert subagent: UX & Docker port audit

---

## Epics

| Epic | Name | Tickets | Points |
|---|---|---|---|
| **E17** | **Testing** | **S-30** | **3** |
| **E18** | **Visualization & Graph Execution** | **S-31, S-32, S-33, S-34, S-35, S-36, S-37, S-38** | **44** |

---

## Phase Breakdown

### Phase 1 (P1 — Should Have) — 23 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-31 | Memory Graph (vis-network all memory types) | 8 | E18 |
| S-34 | Chat Tool Execution Graph (LangGraph DAG) | 8 | E18 |
| S-37 | Unified Memory Search (cross-type) | 5 | E18 |
| S-38 | Navigation Update (all viz pages) | 2 | E18 |

### Phase 2 (P2 — Nice to Have) — 24 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-30 | Load tests + E2E tests | 3 | E17 |
| S-32 | Memory Timeline & Heatmap (Chart.js) | 5 | E18 |
| S-33 | Embedding Cluster Explorer (PCA/t-SNE) | 8 | E18 |
| S-35 | Memory Consolidation Dashboard | 5 | E18 |
| S-36 | Lessons Learned Dashboard | 3 | E18 |

---

## Dependency Graph

```
E17 — Testing:
  S-30 (load tests + E2E) — independent, can run anytime

E18 — Visualization (all feed into nav update):
  S-31 (memory graph) ──┐
  S-32 (timeline)  ─────┤
  S-33 (embeddings) ────┼──→ S-38 (nav update — all routes must exist)
  S-34 (chat DAG) ──────┤
  S-35 (consolidation) ─┤
  S-36 (lessons) ───────┤
  S-37 (unified search) ┘
```

---

## Ticket Summary

### E17 — Testing (3 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-30](S-30-load-tests-e2e.md) | `tests/load/`, `tests/e2e/`, `.github/workflows/` | Locust load tests, Playwright E2E, CI pipeline |

### E18 — Visualization & Graph Execution (44 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-31](S-31-memory-graph-visualization.md) | `memories.py`, `memory_graph.html`, `app.py` | vis-network graph of all memory types with category/source edges |
| [S-32](S-32-memory-timeline-heatmap.md) | `memories.py`, `memory_timeline.html`, `app.py` | Chart.js temporal heatmap, stacked area, TTL decay bars |
| [S-33](S-33-embedding-cluster-explorer.md) | `memories.py`, `embedding_explorer.html`, `app.py` | PCA/t-SNE 2D scatter plot of semantic memory embeddings |
| [S-34](S-34-chat-tool-execution-graph.md) | `streaming.py`, `engine_chat.html` | LangGraph-style DAG for tool execution pipeline in chat UI |
| [S-35](S-35-memory-consolidation-dashboard.md) | `memories.py`, `memory_consolidation.html`, `app.py` | Surface→Medium→Deep flow, compression stats, promotion candidates |
| [S-36](S-36-lessons-learned-dashboard.md) | `lessons.py`, `lessons.html`, `app.py` | Skill→Error→Lesson vis-network graph, effectiveness charts |
| [S-37](S-37-unified-memory-search.md) | `memories.py`, `memory_search.html`, `app.py` | Cross-memory-type search (vector+ILIKE) with ranked results |
| [S-38](S-38-navigation-update-visualization.md) | `base.html` | Nav menu update — add all new visualization pages |

---

## Recommended Execution Order

```
Week 1: Visualization Sprint (E18) + Testing (E17)
  Day 1:   S-31 (memory graph — foundational, adds imports used by others)
  Day 2:   S-34 (chat DAG) + S-37 (unified search)
  Day 3:   S-32 (timeline heatmap) + S-36 (lessons dashboard)
  Day 4:   S-33 (embedding explorer) + S-35 (consolidation dashboard)
  Day 5:   S-38 (nav update — all routes must exist first) + S-30 (load tests + E2E)
```

---

## E18 Design System Requirements

All E18 visualization tickets **MUST** follow these shared standards:

### Architecture Rules (MANDATORY)

**1. No direct SQL** — All DB access through SQLAlchemy ORM (`select()`, `func.*`, `Column`, etc.). Never use `text()`, `raw()`, or string SQL.

**2. Env var fallback pattern (NEVER hardcode)** — All ports, URLs, and paths must follow the docker-compose convention:
```python
# Python — env var with fallback
import os
port = int(os.environ.get("API_INTERNAL_PORT", "8000"))
litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
memories_path = os.environ.get("ARIA_MEMORIES_PATH", "/aria_memories")
```
```bash
# Shell/verification — env var with fallback
curl -s "http://localhost:${ARIA_API_PORT:-8000}/api/endpoint"
curl -s "http://localhost:${ARIA_WEB_PORT:-5050}/page"
```
**Reference ports from docker-compose:**
| Service | External Env Var | Internal Env Var | Defaults |
|---------|-----------------|------------------|----------|
| aria-api | `ARIA_API_PORT` | `API_INTERNAL_PORT` | 8000:8000 |
| aria-web | `ARIA_WEB_PORT` | `WEB_INTERNAL_PORT` | 5050:5000 |
| aria-db | `DB_PORT` | `DB_INTERNAL_PORT` | 5432:5432 |
| litellm | `LITELLM_PORT` | `LITELLM_INTERNAL_PORT` | 18793:4000 |

**3. 5-layer architecture** — DB → ORM → API → api_client → Skills → Agents. Templates call API through `/api/` proxy. Never import ORM models in templates.

### vis-network Source
Use the local bundled file: `/static/js/vis-network.min.js` (not CDN).

### Chart.js Source
Pin to: `https://cdn.jsdelivr.net/npm/chart.js@4.4.1` (consistent with majority of existing templates).

### vis-network Physics (for force-directed graphs)
```javascript
physics: { solver: 'forceAtlas2Based',
    forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 120, springConstant: 0.06 },
    stabilization: { iterations: 100 }
}
```
Exception: S-34 (chat DAG) uses hierarchical LR layout — no physics.

### CSS Color Variables (use instead of hardcoded hex)
```
--accent-primary: #6366f1  (indigo)
--accent-secondary: #8b5cf6  (purple — semantic memory)
--accent-cyan: #06b6d4
--accent-pink: #ec4899
--success: #10b981  (green — thoughts, input nodes)
--warning: #f59e0b  (orange — working memory, tools)
--danger: #ef4444  (red — lessons, errors)
--info: #3b82f6  (blue — KV memory, skills)
```

### Memory Type Color Mapping
| Type | Color | Shape | CSS Variable |
|------|-------|-------|-------------|
| semantic_memory | Purple #8b5cf6 | Dot | --accent-secondary |
| working_memory | Orange #f59e0b | Diamond | --warning |
| kv_memory | Blue #3b82f6 | Square | --info |
| thought | Green #10b981 | Triangle | --success |
| lesson | Red #ef4444 | Star | --danger |

### Docker Ports for Verification
- API: `localhost:${ARIA_API_PORT:-8000}` (aria-api)
- Web: `localhost:${ARIA_WEB_PORT:-5050}` (aria-web, external port)
- DB: `localhost:${DB_PORT:-5432}` (aria-db)
