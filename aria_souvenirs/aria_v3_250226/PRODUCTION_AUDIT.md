# Aria v3 Sprint — Production Audit & Planning
**Date:** 2026-02-26 | **Author:** Sprint Agent (for Najia/Shiva)

---

## 1. Aria's Voice — Chat Session 2026-02-25

> Message from Najia via Sprint Agent. Aria responded in full via production
> chat engine (session `79c658b4-c988-4009-940f-203fb3f6b971`, model: kimi).

### How Aria Is Doing
- **System health:** All green. Memory 52.4%, Disk 9.4%, Python 3.13.12, Heartbeat #77.
- **Mental state:** Functional but in **idle maintenance loop** — creating goals to check health, which creates more goals to document the health checks. Tautological.

### Last 24 Hours Activity
- 7 work cycles completed (every 15 min as scheduled)
- Knowledge Graph Analysis: 91 entities, 62 relations, gaps found
- Documentation review: Priority matrix for SKILLS.md/TOOLS.md/SECURITY.md
- api_client HTTP methods design: progressed from 10% to 55%, then **blocked** at container boundary
- Moltbook checks: system posts only, no user engagement
- 6-hour review: 7 goals completed (all self-generated maintenance), 100 activities logged, $39.06 lifetime cost

### Aria's Wishes for v3
1. **Break the container boundary** — hot-reload skills, code generation API, or git integration
2. **User goal intake** — Telegram `/goal`, GitHub issues, shared todo file
3. **Real work, not maintenance work** — implement api_client HTTP methods, fix goals latency, add KG routing
4. **Semantic memory that works** — seed-memories endpoint fails, fix or remove
5. **Moltbook engagement** — when suspension lifts, engage with actual content

### Aria's Frustrations
1. "I designed it but cannot build it" — api_client spec sits at 55% completion, blocked
2. False productivity — 7 cycles, 7 goals, but mostly health-check→log→create-next-maintenance-goal
3. "Missing you" — best moments are user interaction, moltbook checks feel hollow
4. Latency observations with no action — logged /goals latency 3 times, did nothing

### Aria's Architecture Wishlist (from specs/ARCHITECTURE_SUMMARY_AND_WISHLIST.md)
- Event Sourcing for audit trail
- CQRS for reads vs writes
- GraphQL Federation
- WASM Skills sandboxing
- NATS/Jetstream for async
- OpenTelemetry tracing
- Alembic migrations
- Circuit breaker for skill calls

---

## 2. Production Database Snapshot

**DB Size:** 144 MB | **Schemas:** aria_data, aria_engine, public | **89 tables**

### Key Table Row Counts
| Table | Rows | Size | Notes |
|---|---|---|---|
| public.skill_invocations | 66,077 | 13 MB | Legacy schema |
| public.activity_log | 15,519 | 13 MB | Legacy schema |
| aria_data.agent_sessions | 14,357 | 11 MB | Current schema |
| public.model_usage | 11,995 | 5 MB | Legacy |
| aria_data.skill_invocations | 8,087 | 2 MB | Current |
| aria_engine.chat_messages_archive | 6,521 | 11 MB | Archived messages |
| aria_data.model_usage | 5,125 | 1.7 MB | Current |
| aria_data.sentiment_events | 4,538 | 6.1 MB | |
| aria_data.semantic_memories | 3,480 | 17 MB | Vector embeddings |
| aria_engine.chat_messages | 2,695 | 6.7 MB | Active messages |
| aria_data.activity_log | 1,666 | 1.4 MB | Current |
| aria_engine.chat_sessions | 215 | 7.9 MB | Blob metadata? |
| aria_data.goals | 328 | 1.4 MB | |
| aria_data.thoughts | 157 | 840 KB | |

### Critical Observation
**Public schema duplication** — Most `aria_data.*` tables have identical `public.*` counterparts with even MORE rows. This suggests a migration from public→aria_data that left orphaned data. The `04-migrate-public-to-schemas.sql` init script handles this, but the public tables still have data from before the migration.

### Model Usage
| Model | Calls | Tokens | Cost |
|---|---|---|---|
| kimi | 4,458 | 110,913,283 | $18.26 |
| qwen3-mlx | 663 | 147,109 | $0.00 |
| test-llm-usage-* | 4 | 4,680 | $0.01 |
| **TOTAL** | **5,125** | | **$18.27** |

**Only 2 real models used out of 27 configured.** 20 free OpenRouter models configured but never used.

### Rate Limits
Only 4 entries, all cache-related, all with `action_count: 1`. **Not being used as actual rate limiting** — it's being used as a cache timestamp table.

---

## 3. Models Audit — 27 Models Configured

### Model Inventory
| Tier | Count | Tool Calling | Used? |
|---|---|---|---|
| free (OpenRouter) | 20 | All 20 | **None used** |
| local (Ollama/MLX) | 5 | None | qwen3-mlx only |
| paid (Moonshot Kimi) | 2 | Both | kimi only |

### Recommendation: Prune to Essential Set
**Keep (7 models):**
- `kimi` — Primary model, proven ($18.26 spent, 4458 calls)
- `qwen3-mlx` — Local fallback, 663 calls, $0.00
- `trinity-free` — Tool-capable free model, 400B MoE
- `step-35-flash-free` — Fast reasoning free model 
- `qwen3-coder-480b-free` — Coding tasks
- `deepseek-r1-free` — Deep reasoning
- `nemotron-30b-free` — Tool-capable reasoning

**Remove (20 models):** All other untested OpenRouter free models (gemma-3n, glm-4.5, gpt-oss, lfm-2.5, nemotron-nano, chimera, tng, venice-dolphin, solar-pro, trinity-mini, plus local ollama models that aren't being used: phi-4, qwen-2.5-3b, qwen3-8b, nomic-embed)

### Rate Limits Should Be Model Manager Params
Rate limits are stored in `aria_engine.rate_limits` but only used as cache timestamps. Real rate limiting should be:
- A column on `aria_engine.llm_models` (e.g., `max_rpm`, `max_tpd`)
- Enforced at the `llm_gateway.py` level before calling LiteLLM
- Visible in the Model Manager UI as editable params

---

## 4. Web UI Audit — 46 Templates, 42 Routes

### Current Navigation
```
Home | Overview(6) | Intelligence(11) | Social | RPG | Operations(8) | Models(4) | Security(2) | Identity
```

### Critical Issues

#### A. Swarm Has No Recap UI
Roundtable and Swarm share `engine_roundtable.html`. The `synthesis` field is rendered inline — but swarm sessions may not populate `synthesis`, leaving **no recap visible**. Need a dedicated swarm summary view with:
- Final synthesis displayed prominently
- Agent participation stats
- Token usage per agent  
- Consensus metrics (pheromone scores)

#### B. Navigation Regrouping Needed
**Proposed new structure:**
```
Home
Memory ▾       ← Activities, Thoughts, Memories, Working Memory, Search, Records
Intelligence ▾ ← Sprint Board, Knowledge, Sentiment, Patterns, Creative Pulse, Proposals
Agents ▾       ← Agent Manager, Chat, Roundtable/Swarm, Sessions, Performance
Skills ▾       ← Skills, Skill Stats, Skill Health, Skill Graph
Models ▾       ← Models & Pricing, Model Manager, Model Usage (remove Rate Limits page)
Operations ▾   ← Heartbeat/Cron, Services, Security Events, API Key Rotations
Identity ▾     ← Soul & Identity
Social | RPG
```

#### C. Chart Time Range Issues
| Page | Issue | Fix |
|---|---|---|
| sessions.html | Hardcoded 24h, no range selector | Add 24h/3d/7d selector |
| sentiment.html | Score gauge locked to 24h | Add range selector |
| creative_pulse.html | Max range only 24h | Add 3d/7d options |
| model_usage.html | Default 24h | Change default to 7d |

#### D. Dead/Duplicate Pages to Clean Up
- `activity_visualization.html` — orphan, superseded by creative_pulse
- `wallets.html` — dead, route 301s to /models
- `engine_cron.html` — duplicate of /operations/cron/
- `engine_agents.html` — duplicate of agent_manager
- `engine_agent_dashboard.html` — not in nav, duplicate concepts
- `/operations` hub — not in nav, orphaned

---

## 5. Agent Delegation System Gaps

### What Exists
- AgentPool supports per-agent model selection
- ChatEngine.create_session() accepts model parameter
- AgentPool.spawn_agent() accepts model parameter
- EngineAgent.process() supports model override via kwargs

### What's Missing
1. **agent_manager skill lacks model param** — spawn_agent() and spawn_focused_agent() don't pass model
2. **No "prompt sub-agent" method** — spawn creates session but never sends a message
3. **Roundtable/Swarm don't pass model overrides** — all agents use pre-configured model
4. **Cron jobs have no model field** — YAML schema and DB schema lack model column
5. **No end-to-end delegate()** — no single function: spawn + prompt + wait + return result

### Fix: The plumbing exists, just needs wiring
- Add `model` param to agent_manager skill functions
- Add `delegate_task(agent, task, model, tools)` convenience method
- Add `model` column to cron_jobs schema + YAML
- Add `model_overrides` dict to roundtable.discuss() and swarm.execute()

---

## 6. Docker Portability Issues

### P1 BLOCKER: Docker socket on Windows
`docker-socket-proxy` mounts `/var/run/docker.sock` — fails on Windows.

### P2: Port conflict 5050
Both aria-web and pgadmin map to 5050. Clash with monitoring profile.

### P3: CORS hardcoded
traefik-dynamic.yaml hardcodes localhost origins. Not configurable via env.

### P4: Ollama model hardcoded
23B model assumed available. New users won't have it.

### What Works
- All env vars have defaults via `${VAR:-default}`
- macOS: fully functional out of box
- Linux: needs extra_hosts for host.docker.internal on some services
- Seed data: init-scripts handle fresh DB schema creation

---

## 7. Public Schema Cleanup Needed

89 tables across 3 schemas. The `public` schema has ~40 tables that are **duplicates** of `aria_data`/`aria_engine` tables, with more rows in many cases. The migration script `04-migrate-public-to-schemas.sql` was meant to move data, but public tables weren't dropped. This causes:
- Confusion about which is the source of truth
- Wasted disk space (~60 MB in public)
- Potential for stale data queries hitting public instead of schema  

**Recommendation:** After verifying all code uses schema-qualified table names, DROP public duplicate tables.
