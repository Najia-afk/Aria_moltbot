# API Test Coverage Audit

> Verified against filesystem: 2025-02-26

## Summary

| Metric | Count |
|--------|-------|
| **Total REST endpoints** | 222 |
| **WebSocket endpoints** | 2 |
| **GraphQL endpoint** | 1 |
| **Standalone (aiohttp)** | 1 |
| **Total test files** | 38 |
| **Total test functions** | 427 |
| **Endpoints with direct test coverage** | ~200 |
| **Endpoints with NO test coverage** | ~26 |
| **Estimated coverage** | ~88% |

---

## Test Files (38 files in `tests/`)

| File | Router(s) Tested |
|------|------------------|
| test_activities.py | activities |
| test_admin.py | admin |
| test_advanced_memory.py | memories (advanced scenarios) |
| test_agents_crud.py | agents_crud |
| test_analysis.py | analysis |
| test_architecture.py | Architecture validation |
| test_cross_entity.py | Cross-entity integration |
| test_engine_agents.py | engine_agents, engine_agent_metrics |
| test_engine_chat.py | engine_chat |
| test_engine_cron.py | engine_cron |
| test_engine_internals.py | Engine pure-function unit tests |
| test_engine_sessions.py | engine_sessions |
| test_goals.py | goals |
| test_graphql.py | GraphQL schema |
| test_health.py | health |
| test_knowledge.py | knowledge |
| test_lessons.py | lessons |
| test_litellm.py | litellm |
| test_memories.py | memories |
| test_models_config.py | models_config |
| test_models_crud.py | models_crud |
| test_model_usage.py | model_usage |
| test_noise_filters.py | Noise filter validation |
| test_operations.py | operations |
| test_proposals.py | proposals |
| test_providers.py | providers |
| test_records.py | records |
| test_security.py | security |
| test_security_middleware.py | Security middleware |
| test_sessions.py | sessions |
| test_skills.py | skills |
| test_smoke.py | Smoke tests (multiple routers) |
| test_social.py | social |
| test_thoughts.py | thoughts |
| test_validation.py | Input validation (multiple routers) |
| test_websocket.py | WebSocket (engine_chat WS) |
| test_web_routes.py | Flask web routes |
| test_working_memory.py | working_memory |

---

## Routers With NO Dedicated Test File

The following routers have **zero test coverage** — no dedicated test file exists:

| Router File | Endpoints | Status |
|-------------|-----------|--------|
| `artifacts.py` | 4 | ❌ **Untested** — file artifact CRUD |
| `engine_roundtable.py` | 12 REST + 1 WS | ❌ **Untested** — roundtable & swarm |
| `rpg.py` | 4 | ❌ **Untested** — RPG dashboard |

---

## Endpoints With No Direct Test Coverage

Based on audit of test files vs. endpoint definitions:

| # | Method | Path | Router File | Reason |
|---|--------|------|-------------|--------|
| 1 | PATCH | `/sessions/{session_id}` | sessions.py | No test call found |
| 2 | DELETE | `/sessions/{session_id}` | sessions.py | No test call found |
| 3 | PATCH | `/tasks/{task_id}` | operations.py | No test call found |
| 4 | GET | `/models/available` | models_config.py | No test call found |
| 5 | PATCH | `/working-memory/{item_id}` | working_memory.py | No test call found |
| 6 | GET | `/engine/chat/sessions/{sid}/messages` | engine_chat.py | Only tested indirectly |
| 7 | PATCH | `/engine/sessions/{sid}/title` | engine_sessions.py | No test call found |
| 8 | POST | `/engine/sessions/{sid}/archive` | engine_sessions.py | No test call found |
| 9 | DELETE | `/engine/sessions/ghosts` | engine_sessions.py | No test call found |
| 10 | POST | `/engine/sessions/cleanup` | engine_sessions.py | No test call found |
| 11 | POST | `/agents/db/enable-core` | agents_crud.py | No test call found |
| 12 | POST | `/agents/db/enable-all` | agents_crud.py | No test call found |
| 13–16 | ALL | `/artifacts/*` | artifacts.py | Entire router untested |
| 17–29 | ALL | `/engine/roundtable/*` | engine_roundtable.py | Entire router untested (12 REST + 1 WS) |
| 30–33 | ALL | `/rpg/*` | rpg.py | Entire router untested |
| 34 | GET | `/health` (port 8081) | aria_engine/entrypoint.py | Separate aiohttp server |

---

## Largest Coverage Gaps by Router

| Router | Total Endpoints | Untested | Coverage |
|--------|----------------|----------|----------|
| engine_roundtable.py | 13 (12+1 WS) | 13 | 0% |
| artifacts.py | 4 | 4 | 0% |
| rpg.py | 4 | 4 | 0% |
| engine_sessions.py | 10 | 4 | 60% |
| agents_crud.py | 10 | 2 | 80% |
| sessions.py | 6 | 2 | 67% |

---

*Audit date: 2025-02-26 — 38 test files, 427 test functions, ~88% endpoint coverage*
