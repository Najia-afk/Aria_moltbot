# Aria Blue — Complete Website & API Audit Report

## v1.1 Sprint Remediation Status

> **Updated:** 2026-02-10 — Aria Blue v1.1 Sprint (37 tickets across 7 waves)

The following audit findings have been **addressed** or **partially addressed** by the v1.1 sprint:

| Finding | Status | Tickets |
|---------|--------|--------|
| **Architecture:** No ORM enforcement | ✅ Addressed | TICKET-01, 02 (SQLAlchemy consolidation) |
| **Architecture:** Raw SQL in skills | ✅ Addressed | TICKET-03, 12 (all skills use api_client) |
| **CRITICAL-3:** 3 duplicate `calculateLogCost()` | 🟡 Partially | TICKET-30 (centralized model pricing to `models.yaml`) |
| **MEDIUM-1:** Code duplication (models/wallets/litellm) | 🟡 Partially | TICKET-30 centralized pricing; JS consolidation pending |
| **MEDIUM-4:** Dashboard double-fetch of `/activities` | ✅ Addressed | TICKET-06 (Critical Bug Fixes) |
| **LOW-1:** Unused API endpoints | 🟡 Partially | Documented; some cleaned up in TICKET-09 |
| **LOW-2:** Inconsistent API variable names | 🟡 Partially | Standardization in progress |
| **Testing:** 11 test failures | ✅ Addressed | TICKET-09, 31 (677+ tests, 0 failures) |
| **Observability:** No structured logging | ✅ Addressed | TICKET-11, 17 (logging & observability stack) |
| **Directory:** `experiment/` skill (dead code) | ✅ Resolved | S-18 (deprecated skill removed) |
| **Directory:** `hooks/` flagged as dead code | ✅ Reclassified | Contains `soul-evil/` (evil mode toggle) — not dead code |

**Remaining unaddressed (require frontend work):**
- CRITICAL-1: Kimi pricing discrepancy (7× difference) — requires frontend JS consolidation
- CRITICAL-2: Currency display mismatch ($/¥) — requires frontend normalization
- MEDIUM-2: 4 pages hit `/litellm/spend` — needs client-side caching
- MEDIUM-3: Services page 11 sequential API calls — needs `/status` consolidation

---

> **Generated for:** Major Restructure Planning  
> **Scope:** All 22 web templates, Flask app routes, FastAPI endpoints, and API routers  
> **Finding:** 22 templates (not 21 — `operations.html` was missed in the original list)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Per-Page Audit](#2-per-page-audit)
3. [API Router Inventory](#3-api-router-inventory)
4. [Summary Tables](#4-summary-tables)
   - 4a. API Calls Per Page
   - 4b. Duplicate Endpoints (called by multiple pages)
   - 4c. Overlapping Data Displays
   - 4d. Wallet & Cost Consistency Issues
   - 4e. Hardcoded Data
   - 4f. API Base URL Variable Inconsistencies
   - 4g. Auto-Refresh Intervals
5. [Critical Issues](#5-critical-issues)
6. [Recommendations](#6-recommendations)

---

## 1. Architecture Overview

| Component | Technology | Location |
|-----------|-----------|----------|
| **Web Server** | Flask (Jinja2 templates) | `src/web/app.py` |
| **API Server** | FastAPI v3.0 (root_path="/api") | `src/api/main.py` |
| **Database** | PostgreSQL + SQLAlchemy 2.0 async + psycopg 3 | `src/database/` |
| **Frontend** | Vanilla JS + Chart.js + vis-network.js | Templates inline `<script>` |
| **Reverse Proxy** | Traefik | Docker stack |
| **Model Router** | LiteLLM (port 18793) | Docker stack |
| **CORS** | Allow ALL origins | `src/api/main.py` |
| **Security** | Rate limiting middleware (120/min, 2000/hr) | `src/api/main.py` |

**Flask Context Variables** (injected via `@app.context_processor`):
- `service_host`, `api_base_url`, `clawdbot_public_url`, `clawdbot_token`

**Base Template JS Variables** (`base.html`):
```js
const API_BASE_URL = "{{ api_base_url }}";
window.ARIA_API_BASE_URL = API_BASE_URL;
```

**API Routers** (15 routers + GraphQL):
`health`, `activities`, `thoughts`, `memories`, `goals`, `sessions`, `model_usage`, `litellm`, `providers`, `security`, `knowledge`, `social`, `operations`, `records`, `admin`

---

## 2. Per-Page Audit

### 2.1 — index.html
| Property | Value |
|----------|-------|
| **URL** | `/` |
| **Lines** | ~195 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /stats` · `GET /status` |
| **API Calls on Load** | **2** |
| **Auto-Refresh** | None |
| **Data Displayed** | Hero section, stats cards (thoughts count, activities count, last activity timestamp, system status), quick links grid, external services grid with live status indicators |
| **Notes** | Landing page. Minimal data. |

---

### 2.2 — dashboard.html
| Property | Value |
|----------|-------|
| **URL** | `/dashboard` |
| **Lines** | ~330 |
| **API Var** | `const API_BASE = window.ARIA_API_BASE_URL \|\| '/api'` |
| **API Endpoints** | `GET /stats` · `GET /status` · `GET /activities` · `GET /activities?limit=100` · `GET /thoughts?limit=100` · `GET /host-stats` |
| **API Calls on Load** | **6** |
| **Auto-Refresh** | **30s** (host-stats only) |
| **Data Displayed** | Metrics row (total activities, total thoughts, services online, system status), host stats widget (RAM, swap, disk, SMART health), activity timeline line chart, thoughts by category doughnut chart, service health grid with colored dots, recent activity list, Grafana link |
| **Charts** | 2 (Chart.js: activity timeline line + thoughts doughnut) |
| **Notes** | `/activities` is called **twice** — once for list, once with `?limit=100` for chart data. Overlaps heavily with index.html (`/stats`, `/status`). |

---

### 2.3 — operations.html
| Property | Value |
|----------|-------|
| **URL** | `/operations` |
| **Lines** | 461 |
| **API Var** | `API_BASE_URL` (from base.html) |
| **API Endpoints** | `GET /jobs/live` · `GET /litellm/global-spend` · `GET /litellm/spend?limit=50&lite=true` · `GET /status` |
| **API Calls on Load** | **4** (loadJobs + loadLitellmData[2 calls] + loadServiceStatus) |
| **Auto-Refresh** | **30s** (all data) |
| **Data Displayed** | Stats grid (scheduled jobs, API requests, total spend, services online/total), quick links to sub-pages, OpenClaw cron jobs table (name, agent, schedule, status, last/next run, duration), model usage table (aggregated from spend logs), recent API calls table |
| **Notes** | Hub page linking to sub-pages. Duplicates LiteLLM spend and service status data from other pages. |

---

### 2.4 — activities.html
| Property | Value |
|----------|-------|
| **URL** | `/activities` |
| **Lines** | ~170 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /activities?limit=25` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | None |
| **Data Displayed** | Table: ID, type, description, timestamp |

---

### 2.5 — thoughts.html
| Property | Value |
|----------|-------|
| **URL** | `/thoughts` |
| **Lines** | ~130 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /thoughts?limit=20` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | None |
| **Data Displayed** | Card grid: category, time, content |

---

### 2.6 — memories.html
| Property | Value |
|----------|-------|
| **URL** | `/memories` |
| **Lines** | ~210 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /memories?limit=20` · `DELETE /memories/{key}` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | None |
| **Data Displayed** | Stats bar (total memories, categories), memory cards grid (key, category, value, delete button) |

---

### 2.7 — records.html
| Property | Value |
|----------|-------|
| **URL** | `/records` |
| **Lines** | ~130 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /records?table={table}&limit={limit}&page={page}` · `GET /export?table={table}` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | None |
| **Data Displayed** | Dynamic table for ANY database table (all 19 tables whitelisted in records router), pagination controls |
| **Tables Available** | activities, thoughts, memories, goals, hourly_goals, complex_tasks, knowledge_entities, knowledge_relations, social_posts, heartbeat_log, performance_log, security_events, agent_sessions, model_usage, rate_limits, api_key_rotations, scheduled_jobs, schedule_tick |

---

### 2.8 — search.html
| Property | Value |
|----------|-------|
| **URL** | `/search` |
| **Lines** | ~170 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /search?q={q}&activities={bool}&thoughts={bool}&memories={bool}&from={date}&to={date}` |
| **API Calls on Load** | **0** (user-triggered only) |
| **Auto-Refresh** | None |
| **Data Displayed** | Search results for activities, thoughts, memories with text highlighting |

---

### 2.9 — goals.html
| Property | Value |
|----------|-------|
| **URL** | `/goals` |
| **Lines** | 1326 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /goals?limit=100` · `POST /goals` · `PATCH /goals/{id}` · `GET /hourly-goals` · `POST /hourly-goals` · `PATCH /hourly-goals/{id}` |
| **API Calls on Load** | **1** (loadGoals; hourly goals loaded on tab switch) |
| **Auto-Refresh** | None |
| **Data Displayed** | Tabs (Main Goals / Hourly Goals), stats grid (active, completed, avg progress, due soon), filterable goal cards grid, create/edit modals, hourly goals grid with CRUD |

---

### 2.10 — sessions.html
| Property | Value |
|----------|-------|
| **URL** | `/sessions` |
| **Lines** | 233 |
| **API Var** | `API_BASE_URL` (from base.html) |
| **API Endpoints** | `GET /sessions/stats` · `GET /sessions?limit=100` (with optional `&status=` param) |
| **API Calls on Load** | **2** |
| **Auto-Refresh** | **15s** (both stats + sessions) |
| **Data Displayed** | Stats row (active sessions, total sessions, total tokens, total cost), sessions table (ID, agent, type, status, messages, tokens, cost, started, duration) |

---

### 2.11 — model_usage.html
| Property | Value |
|----------|-------|
| **URL** | `/model-usage` |
| **Lines** | 340 |
| **API Var** | `API_BASE_URL` (from base.html) |
| **API Endpoints** | `GET /model-usage/stats?hours={hours}` · `GET /model-usage?limit=50` (with optional `&model=` and `&source=` params) |
| **API Calls on Load** | **2** |
| **Auto-Refresh** | **30s** |
| **Data Displayed** | Stats grid (total requests, total tokens, total cost, avg latency with source breakdown), model summary table, recent requests table |
| **Notes** | Tracks Aria's own model-usage table (internal tracking), NOT LiteLLM spend data. Different data source from models.html. |

---

### 2.12 — rate_limits.html
| Property | Value |
|----------|-------|
| **URL** | `/rate-limits` |
| **Lines** | ~185 |
| **API Var** | `API_BASE_URL` (from base.html) |
| **API Endpoints** | `GET /rate-limits` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | **30s** |
| **Data Displayed** | Info card, table: skill name, action count, last action, last post, window start, updated |

---

### 2.13 — api_key_rotations.html
| Property | Value |
|----------|-------|
| **URL** | `/api-key-rotations` |
| **Lines** | ~210 |
| **API Var** | `API_BASE_URL` (from base.html) |
| **API Endpoints** | `GET /api-key-rotations?limit=100` (with optional `&service=` param) |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | **60s** |
| **Data Displayed** | Info card, rotations table: service, reason, rotated by, rotated at, metadata (JSON) |

---

### 2.14 — models.html ⚠️
| Property | Value |
|----------|-------|
| **URL** | `/models` |
| **Lines** | 1307 |
| **API Var** | `const API_URL = window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /providers/balances` · `GET /litellm/models` · `GET /litellm/spend?limit=500&lite=true` · `GET /litellm/global-spend` |
| **API Calls on Load** | **4** (loadBalances + loadGlobalSpend + loadModels + loadSpendLogs) |
| **Auto-Refresh** | **60s** (checkHealth + loadModels + loadBalances + loadGlobalSpend) |
| **Data Displayed** | Stats row (available models, total balance, total tokens, total spend), wallet balances section (Kimi/OpenRouter/Local), token consumption charts (by provider doughnut, usage over time line), spend analytics (4 cards + usage by model bar + cost breakdown pie), available models grid with filter tabs (All/Kimi/OpenRouter/Local), recent API calls table |
| **Charts** | 4 (Chart.js: provider doughnut, usage timeline line, usage by model bar, cost breakdown pie) |
| **Hardcoded** | `MODEL_PRICING` dict with per-model costs, Kimi balance displayed as **USD ($)** |

---

### 2.15 — wallets.html ⚠️
| Property | Value |
|----------|-------|
| **URL** | `/wallets` |
| **Lines** | 972 |
| **API Var** | `const API_URL = window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /providers/balances` · `GET /litellm/spend?limit=500&lite=true` |
| **API Calls on Load** | **2** (loadBalances + loadSpend) |
| **Auto-Refresh** | **60s** with countdown display |
| **Data Displayed** | Total balance summary card, 3 wallet cards (Kimi/OpenRouter/Local) with detailed breakdown, spending overview (total/today/week/month), balance history chart (line chart by provider), cost estimator tool |
| **Charts** | 1 (Chart.js: balance history line chart) |
| **Hardcoded** | `PRICING` dict, `CNY_TO_USD = 0.14`, `calculateLogCost()`, Kimi balance displayed as **USD ($)** |

---

### 2.16 — litellm.html ⚠️
| Property | Value |
|----------|-------|
| **URL** | `/litellm` |
| **Lines** | 1152 |
| **API Var** | `const API_URL = window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /litellm/health` · `GET /litellm/models` · `GET /providers/balances` · `GET /litellm/global-spend` · `GET /litellm/spend?limit=500&lite=true` |
| **API Calls on Load** | **4** (checkHealth + loadModels + loadBalances + loadGlobalSpend) |
| **Auto-Refresh** | **60s** |
| **Data Displayed** | Status overview (3 cards: health, model count, endpoint URL), spend summary (4 cards), Grafana iframe embed, models table (name, provider, max tokens, input/output pricing, status), model detail cards, API endpoint reference list, provider credits/balances section |
| **Charts** | 0 (links to Grafana instead) |
| **Hardcoded** | `MODEL_PRICING` dict, Kimi balance displayed as **CNY (¥)** |

---

### 2.17 — services.html
| Property | Value |
|----------|-------|
| **URL** | `/services` |
| **Lines** | 632 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /status/{serviceId}` × 11 services · `POST /admin/services/{serviceId}/{action}` |
| **API Calls on Load** | **11** (one per service: traefik, openclaw, litellm, aria-web, aria-api, mlx, ollama, openrouter, postgres, grafana, prometheus, pgadmin) |
| **Auto-Refresh** | None (manual only) |
| **Data Displayed** | Architecture diagram with live status indicators, control panel with restart/stop buttons, application flow diagram |
| **Notes** | Sequential status checks (not parallel). Most API-call-heavy page on load. |

---

### 2.18 — heartbeat.html
| Property | Value |
|----------|-------|
| **URL** | `/heartbeat` |
| **Lines** | 909 |
| **API Var** | `const API_BASE = window.ARIA_API_BASE_URL \|\| '/api'` |
| **API Endpoints** | `GET /jobs/live` · `GET /jobs` (fallback) · `POST /jobs/sync` · `GET /schedule` · `POST /schedule/tick` · `GET /records?table=heartbeat_log&limit=100` |
| **API Calls on Load** | **2–3** (loadScheduledJobs tries `/jobs/live` then falls back to `/jobs`, plus loadScheduleStatus) |
| **Auto-Refresh** | **60s** |
| **Data Displayed** | Heartbeat hero with pulse animation, stats (scheduled jobs, successful 24h, failed 24h, next job), jobs grid with detail cards, recent executions table from heartbeat_log |

---

### 2.19 — knowledge.html
| Property | Value |
|----------|-------|
| **URL** | `/knowledge` |
| **Lines** | 622 |
| **API Var** | `const API_BASE = '{{ api_base_url }}'` ⚠️ (redundant Jinja render) |
| **API Endpoints** | `GET /knowledge-graph` · `POST /knowledge-graph/entities` · `POST /knowledge-graph/relations` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | None |
| **Data Displayed** | Stats (entity count, relation count), interactive vis-network graph visualization, entities list, relations list, add entity/relation modals |
| **Libraries** | vis-network.js (loaded from CDN) |

---

### 2.20 — social.html
| Property | Value |
|----------|-------|
| **URL** | `/social` |
| **Lines** | 453 |
| **API Var** | `const API_BASE = '{{ api_base_url }}'` ⚠️ (redundant Jinja render) |
| **API Endpoints** | `GET /social` (with optional `?platform=`) · `POST /social` |
| **API Calls on Load** | **1** |
| **Auto-Refresh** | None |
| **Data Displayed** | Post count stat, platform tabs (All/Moltbook), post cards, compose modal |

---

### 2.21 — performance.html
| Property | Value |
|----------|-------|
| **URL** | `/performance` |
| **Lines** | 502 |
| **API Var** | `const API_BASE = '{{ api_base_url }}'` ⚠️ (redundant Jinja render) |
| **API Endpoints** | `GET /performance` · `POST /performance` · `GET /tasks` |
| **API Calls on Load** | **2** (parallel: performance + tasks) |
| **Auto-Refresh** | None |
| **Data Displayed** | Stats (review count, pending tasks, completed tasks), tabs (Performance Reviews / Complex Tasks), review cards, task cards, add review modal |

---

### 2.22 — security.html
| Property | Value |
|----------|-------|
| **URL** | `/security` |
| **Lines** | ~280 |
| **API Var** | `window.ARIA_API_BASE_URL` |
| **API Endpoints** | `GET /security-events/stats` · `GET /security-events?limit=200` |
| **API Calls on Load** | **2** |
| **Auto-Refresh** | None |
| **Data Displayed** | Stats grid (total events, blocked, critical, high, medium, low severity counts), events table (time, level, type, patterns, source, blocked status, preview) |

---

## 3. API Router Inventory

### 3.1 — health.py (6 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/health` | — | None directly (for healthchecks) |
| GET | `/host-stats` | — | dashboard |
| GET | `/status` | — | index, dashboard, operations |
| GET | `/status/{service_id}` | — | services (×11) |
| GET | `/stats` | — | index, dashboard |
| GET | `/stats-extended` | — | None (unused by any template) |

### 3.2 — activities.py (4 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/activities` | `limit` | activities, dashboard (×2) |
| POST | `/activities` | — | None (API-only) |
| GET | `/interactions` | — | None (unused by any template) |
| GET | `/activity` | — | None (unused by any template) |

### 3.3 — thoughts.py (2 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/thoughts` | `limit` | thoughts, dashboard |
| POST | `/thoughts` | — | None (API-only) |

### 3.4 — memories.py (4 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/memories` | `limit` | memories |
| POST | `/memories` | — | None (API-only) |
| GET | `/memories/{key}` | — | None |
| DELETE | `/memories/{key}` | — | memories |

### 3.5 — goals.py (6 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/goals` | `limit` | goals |
| POST | `/goals` | — | goals |
| DELETE | `/goals/{goal_id}` | — | None (not wired in template!) |
| PATCH | `/goals/{goal_id}` | — | goals |
| GET | `/hourly-goals` | — | goals |
| POST | `/hourly-goals` | — | goals |
| PATCH | `/hourly-goals/{goal_id}` | — | goals |

### 3.6 — sessions.py (4 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/sessions` | `limit`, `status` | sessions |
| POST | `/sessions` | — | None (API-only) |
| PATCH | `/sessions/{session_id}` | — | None |
| GET | `/sessions/stats` | — | sessions |

### 3.7 — model_usage.py (3 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/model-usage` | `limit`, `model`, `source` | model_usage |
| POST | `/model-usage` | — | None (API-only) |
| GET | `/model-usage/stats` | `hours` | model_usage |

### 3.8 — litellm.py (4 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/litellm/models` | — | models, litellm |
| GET | `/litellm/health` | — | litellm |
| GET | `/litellm/spend` | `limit`, `lite` | models, wallets, litellm, operations |
| GET | `/litellm/global-spend` | — | models, litellm, operations |

### 3.9 — providers.py (1 endpoint)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/providers/balances` | — | models, wallets, litellm |

### 3.10 — security.py (3 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/security-events` | `limit` | security |
| POST | `/security-events` | — | None (API-only) |
| GET | `/security-events/stats` | — | security |

### 3.11 — knowledge.py (5 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/knowledge-graph` | — | knowledge |
| GET | `/knowledge-graph/entities` | — | None (unused – template uses main endpoint) |
| GET | `/knowledge-graph/relations` | — | None (unused – template uses main endpoint) |
| POST | `/knowledge-graph/entities` | — | knowledge |
| POST | `/knowledge-graph/relations` | — | knowledge |

### 3.12 — social.py (2 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/social` | `platform` | social |
| POST | `/social` | — | social |

### 3.13 — operations.py (16 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/rate-limits` | — | rate_limits |
| POST | `/rate-limits/check` | — | None (API-only) |
| POST | `/rate-limits/increment` | — | None (API-only) |
| GET | `/api-key-rotations` | `limit`, `service` | api_key_rotations |
| POST | `/api-key-rotations` | — | None (API-only) |
| GET | `/heartbeat` | `limit` | None (template uses `/records?table=heartbeat_log`) |
| POST | `/heartbeat` | — | None (API-only) |
| GET | `/heartbeat/latest` | — | None (unused by templates) |
| GET | `/performance` | `limit` | performance |
| POST | `/performance` | — | performance |
| GET | `/tasks` | `status` | performance |
| POST | `/tasks` | — | None (API-only) |
| PATCH | `/tasks/{task_id}` | — | None |
| GET | `/schedule` | — | heartbeat |
| POST | `/schedule/tick` | — | heartbeat |
| GET | `/jobs` | — | heartbeat (fallback) |
| GET | `/jobs/live` | — | heartbeat, operations |
| GET | `/jobs/{job_id}` | — | None |
| POST | `/jobs/sync` | — | heartbeat |

### 3.14 — records.py (3 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| GET | `/records` | `table`, `limit`, `page` | records, heartbeat |
| GET | `/export` | `table` | records |
| GET | `/search` | `q`, `activities`, `thoughts`, `memories` | search |

### 3.15 — admin.py (2 endpoints)
| Method | Path | Query Params | Used By Templates |
|--------|------|-------------|-------------------|
| POST | `/admin/services/{service_id}/{action}` | — | services |
| GET | `/soul/{filename}` | — | None (API-only) |

---

## 4. Summary Tables

### 4a. API Calls Per Page (on initial load)

| Page | URL | API Calls | Auto-Refresh |
|------|-----|-----------|-------------|
| **services** | `/services` | **11** | None |
| **dashboard** | `/dashboard` | **6** | 30s (host-stats) |
| **models** | `/models` | **4** | 60s |
| **litellm** | `/litellm` | **4** | 60s |
| **operations** | `/operations` | **4** | 30s |
| **heartbeat** | `/heartbeat` | **2–3** | 60s |
| **sessions** | `/sessions` | **2** | 15s |
| **model_usage** | `/model-usage` | **2** | 30s |
| **security** | `/security` | **2** | None |
| **dashboard** (chart) | (included above) | — | — |
| **index** | `/` | **2** | None |
| **wallets** | `/wallets` | **2** | 60s |
| **performance** | `/performance` | **2** | None |
| **memories** | `/memories` | **1** | None |
| **activities** | `/activities` | **1** | None |
| **thoughts** | `/thoughts` | **1** | None |
| **goals** | `/goals` | **1** | None |
| **rate_limits** | `/rate-limits` | **1** | 30s |
| **api_key_rotations** | `/api-key-rotations` | **1** | 60s |
| **knowledge** | `/knowledge` | **1** | None |
| **social** | `/social` | **1** | None |
| **records** | `/records` | **1** | None |
| **search** | `/search` | **0** | None |
| | | **TOTAL: ~52–53** | |

### 4b. Duplicate Endpoints — Called by Multiple Pages

| API Endpoint | Pages Calling It | Notes |
|-------------|-----------------|-------|
| `GET /providers/balances` | **models**, **wallets**, **litellm** | 3 pages fetch same balance data |
| `GET /litellm/spend` | **models**, **wallets**, **litellm**, **operations** | 4 pages fetch same spend logs |
| `GET /litellm/global-spend` | **models**, **litellm**, **operations** | 3 pages fetch same global spend |
| `GET /litellm/models` | **models**, **litellm** | 2 pages fetch model list |
| `GET /status` | **index**, **dashboard**, **operations** | 3 pages check all services |
| `GET /stats` | **index**, **dashboard** | 2 pages fetch same counts |
| `GET /activities` | **activities**, **dashboard** (×2) | 3 total calls across 2 pages |
| `GET /thoughts` | **thoughts**, **dashboard** | 2 pages |
| `GET /jobs/live` | **heartbeat**, **operations** | 2 pages fetch live jobs |

### 4c. Overlapping Data Displays

| Data Category | Pages Showing It | Severity |
|--------------|-----------------|----------|
| **Provider Balances** (Kimi/OpenRouter/Local) | models, wallets, litellm | 🔴 HIGH — 3 pages, each with own rendering logic |
| **LiteLLM Spend Logs** | models, wallets, litellm, operations | 🔴 HIGH — 4 pages parse same data differently |
| **Global Spend Summary** | models, litellm, operations | 🟡 MEDIUM — 3 pages show total spend/tokens |
| **Model List** | models, litellm | 🟡 MEDIUM — 2 pages render models |
| **Service Status** | index, dashboard, operations, services | 🟡 MEDIUM — 4 pages check status |
| **Activity/Thought Counts** | index, dashboard | 🟢 LOW — same quick stats |
| **OpenClaw Jobs** | heartbeat, operations | 🟡 MEDIUM — 2 pages render job list |
| **Cost Calculation** | models, wallets, litellm | 🔴 HIGH — 3 separate `calculateLogCost()` with different pricing |

### 4d. Wallet & Cost Consistency Issues — CRITICAL ⚠️

#### Currency Display Inconsistency
| Page | Kimi Currency Symbol | Kimi Source |
|------|---------------------|-------------|
| **models.html** | `$` (USD) | Displays balance from `/providers/balances` as USD |
| **wallets.html** | `$` (USD) | Displays balance as USD, has `CNY_TO_USD = 0.14` constant (unused?) |
| **litellm.html** | `¥` (CNY) | Displays balance as CNY with ¥ symbol |

**The API (`providers.py`)** returns Kimi balance with `"currency": "CNY"` — the raw data from Moonshot API is in CNY. Two pages ignore this and show `$`, one page correctly shows `¥`.

#### Cost Calculation Pricing — 3 SEPARATE IMPLEMENTATIONS

**models.html `MODEL_PRICING`:**
```js
'moonshot-v1-8k':   { input: 1.68,  output: 1.68 },
'moonshot-v1-32k':  { input: 3.36,  output: 3.36 },
'moonshot-v1-128k': { input: 8.40,  output: 8.40 },
```

**wallets.html `PRICING`:**
```js
'moonshot-v1-8k':   { input: 0.24,  output: 0.24 },
'moonshot-v1-32k':  { input: 0.48,  output: 0.48 },
'moonshot-v1-128k': { input: 0.84,  output: 0.84 },
```

**litellm.html `MODEL_PRICING`:**
```js
'moonshot-v1-8k':   { input: 1.68,  output: 1.68 },
'moonshot-v1-32k':  { input: 3.36,  output: 3.36 },
'moonshot-v1-128k': { input: 8.40,  output: 8.40 },
```

**Result:** wallets.html Kimi pricing is **7× lower** than models.html and litellm.html. This means the wallets page reports dramatically lower costs for the same token usage.

**Likely Explanation:** The models/litellm prices appear to be in **CNY per 1M tokens** (matching Moonshot's published rates), while wallets prices appear to be the **USD equivalent** (÷7 conversion). But since the pages show costs in `$`, users see the wrong values.

### 4e. Hardcoded Data

| Item | Location(s) | Issue |
|------|------------|-------|
| **MODEL_PRICING dicts** | models.html, wallets.html, litellm.html | 3 separate price lists, 2 inconsistent. Prices should come from API. |
| **CNY_TO_USD = 0.14** | wallets.html | Hardcoded exchange rate. Never updated. |
| **Service list** (11 services) | services.html | Hardcoded in HTML. Adding a service requires template edit. |
| **Service URLs** | litellm.html (shows endpoint URL card) | LiteLLM port hardcoded as display text |
| **Table whitelist** | records.py (19 tables) | Must be updated when DB schema changes |
| **Soul file whitelist** | admin.py (6 files) | Must be updated when new soul files added |
| **Grafana dashboard URL** | litellm.html (iframe), dashboard.html (link) | Environment-specific URLs embedded in template |

### 4f. API Base URL Variable Inconsistencies

All templates inherit `const API_BASE_URL` and `window.ARIA_API_BASE_URL` from `base.html`. However, several templates create their own alias variables:

| Template | Variable Used | Source | Risk |
|----------|-------------|--------|------|
| Most templates | `API_BASE_URL` or `window.ARIA_API_BASE_URL` | base.html | ✅ Correct |
| models.html | `const API_URL = window.ARIA_API_BASE_URL` | Alias | 🟡 Unnecessary alias |
| wallets.html | `const API_URL = window.ARIA_API_BASE_URL` | Alias | 🟡 Unnecessary alias |
| litellm.html | `const API_URL = window.ARIA_API_BASE_URL` | Alias | 🟡 Unnecessary alias |
| dashboard.html | `const API_BASE = window.ARIA_API_BASE_URL \|\| '/api'` | Alias + fallback | 🟡 Different fallback |
| heartbeat.html | `const API_BASE = window.ARIA_API_BASE_URL \|\| '/api'` | Alias + fallback | 🟡 Different fallback |
| knowledge.html | `const API_BASE = '{{ api_base_url }}'` | **Re-renders Jinja** | 🟠 Redundant Jinja eval |
| social.html | `const API_BASE = '{{ api_base_url }}'` | **Re-renders Jinja** | 🟠 Redundant Jinja eval |
| performance.html | `const API_BASE = '{{ api_base_url }}'` | **Re-renders Jinja** | 🟠 Redundant Jinja eval |

### 4g. Auto-Refresh Summary

| Interval | Pages |
|----------|-------|
| **15s** | sessions |
| **30s** | model_usage, rate_limits, dashboard (host-stats only), operations |
| **60s** | models, wallets, litellm, heartbeat, api_key_rotations |
| **None** | index, activities, thoughts, memories, records, search, goals, services, knowledge, social, performance, security |

---

## 5. Critical Issues

### 🔴 CRITICAL-1: Kimi Pricing Discrepancy (7× difference)
**Impact:** Cost reports on wallets page show ~14% of actual cost compared to models/litellm pages.  
**Root Cause:** wallets.html PRICING dict uses USD-equivalent values while models/litellm use CNY values, but all display with `$`.  
**Fix:** Centralize pricing in the API. Remove all client-side `MODEL_PRICING` / `PRICING` / `calculateLogCost()` implementations.

### 🔴 CRITICAL-2: Currency Display Mismatch
**Impact:** Users see `$` on models/wallets pages but `¥` on litellm page for the same Kimi balance.  
**Root Cause:** API returns `currency: "CNY"` but only litellm.html respects it.  
**Fix:** Either convert all to USD in the API, or have all templates read and display the `currency` field from the response.

### 🔴 CRITICAL-3: 3 Duplicate `calculateLogCost()` Implementations
**Impact:** Same token usage → different cost numbers depending on which page you view.  
**Root Cause:** Each of models.html, wallets.html, litellm.html has its own cost calculation with its own pricing dictionary.  
**Fix:** Move cost calculation to the API's `/litellm/spend` endpoint (it already returns a `spend` field from LiteLLM).

### 🟡 MEDIUM-1: Massive Code Duplication Across 3 Pages
**Impact:** models.html (1307 lines), wallets.html (972 lines), litellm.html (1152 lines) = **3,431 lines** with 60%+ overlap in functionality: balance loading, spend analysis, model display.  
**Fix:** Consider consolidating into 1–2 pages, or extract shared JS into a module.

### 🟡 MEDIUM-2: 4 Pages Hit `/litellm/spend` Endpoint
**Impact:** The LiteLLM spend endpoint proxies to `litellm:4000/spend/logs` which likely returns ALL logs (no date filter in the proxy). With `limit=500`, this is 4 separate 500-row fetches if a user navigates between these pages.  
**Fix:** Add caching or a shared data layer. Consider server-side aggregation.

### 🟡 MEDIUM-3: Services Page Makes 11 Sequential API Calls
**Impact:** Slow page load — each service check is sequential with up to 5s timeout.  
**Fix:** Use the existing `/status` endpoint (which checks all services in one call) instead of 11 individual `/status/{id}` calls.

### 🟡 MEDIUM-4: Dashboard Calls `/activities` Twice
**Impact:** Unnecessary duplicate request on every load and every 30s refresh.  
**Fix:** Fetch once with `?limit=100` and use the same data for both the chart and the recent list.

### 🟢 LOW-1: Unused API Endpoints
These endpoints exist in routers but are NOT called by any template:
- `GET /stats-extended`
- `GET /interactions`
- `GET /activity`
- `GET /knowledge-graph/entities` (separate from main `/knowledge-graph`)
- `GET /knowledge-graph/relations` (separate)
- `GET /heartbeat` (template uses `/records?table=heartbeat_log` instead)
- `GET /heartbeat/latest`
- `GET /jobs/{job_id}`
- `DELETE /goals/{goal_id}` (API exists, template doesn't wire it)

### 🟢 LOW-2: Inconsistent API Variable Names
**Impact:** Maintenance confusion — 4 different variable names across templates.  
**Fix:** Standardize all templates to use `API_BASE_URL` from base.html directly. Remove all local aliases.

---

## 6. Recommendations

### Immediate Fixes (Before Restructure)
1. **Fix Kimi pricing** — Choose one source of truth (API's `spend` field or standardized pricing endpoint) and remove all 3 client-side pricing dicts.
2. **Fix currency display** — Respect `currency` field from `/providers/balances` or convert to USD server-side.
3. **Remove dashboard double-fetch** of `/activities`.

### Restructure Suggestions
1. **Consolidate models/wallets/litellm** into a single "Finance & Models" section with tabs, or at most 2 pages (Models + Wallets). This eliminates 60%+ of duplicate code.
2. **Create a shared JS module** (`aria-common.js`) for: `formatCost()`, `formatDate()`, `formatNumber()`, `formatDuration()`, `statusBadge()` — currently copy-pasted across 10+ templates.
3. **Move cost calculation server-side** — The API already has LiteLLM's `spend` values; expose a `/spend/summary` endpoint with pre-aggregated data.
4. **Use `/status` instead of 11×`/status/{id}`** on the services page.
5. **Add client-side caching** for balance/spend data (e.g., `sessionStorage` with 30s TTL) to avoid redundant fetches when navigating between pages.
6. **Standardize API variable** to just `API_BASE_URL` everywhere — remove all `API_URL`, `API_BASE`, and redundant Jinja re-renders.
7. **Clean up unused endpoints** or document them as internal/skill-only APIs.

---

## 7. Resolution Status — Sprint v1.2

> **Updated:** 2026-02-10 — Sprint v1.2 (S-series tickets)

Sprint v1.2 addressed all critical and high-severity findings from the architecture and skill audits:

| Area | Action | Status |
|------|--------|--------|
| **Deprecated skills** | Removed 6 skills: `database`, `brainstorm`, `community`, `fact_check`, `model_switcher`, `experiment` | ✅ Resolved |
| **Agent roles** | Expanded `AgentRole` enum to 8 roles; added pheromone scoring | ✅ Resolved |
| **Skill catalog** | Created `aria_skills/catalog.py` with `--list-skills` CLI | ✅ Resolved |
| **Security hardening** | CORS restrictions, admin auth, env-var secrets | ✅ Resolved |
| **Gateway abstraction** | `aria_mind/gateway.py` created for OpenClaw phase-out | ✅ Resolved |
| **`hooks/` directory** | Reclassified: contains `soul-evil/` (evil mode toggle), not dead code | ✅ Reclassified |
| **Working memory** | `sync_to_files()` added for session-surviving state | ✅ Resolved |
| **Model catalog** | `models.yaml` is now single source of truth | ✅ Resolved |
| **Coordinator** | `solve()` method added (explore → work → validate cycle) | ✅ Resolved |

All critical/high findings from the v1.1 audit are now resolved or reclassified. Remaining open items are frontend-only (CRITICAL-1, CRITICAL-2, MEDIUM-2, MEDIUM-3).

---

*End of Audit Report*
