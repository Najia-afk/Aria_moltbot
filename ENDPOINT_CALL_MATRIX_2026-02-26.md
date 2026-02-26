# Endpoint Call Matrix — 2026-02-26

## Summary

- date: 2026-02-26
- route_count: 237
- call_count: 64
- template_calls: 7
- test_calls: 23
- script_calls: 34
- unresolved_literal_api_calls: 0

## Runtime Validation (Live)

| Check | Path | Expected | Result | Status |
|---|---|---|---|---|
| Health endpoint | `GET /api/health` | 200 | 200 | PASS |
| Protected endpoint without key (direct API) | `POST /api/engine/chat/sessions` | 401 | 401 | PASS |
| Protected endpoint with key (direct API) | `POST /api/engine/chat/sessions` | 201 | 201 | PASS |
| Swarm sync launch | `POST /api/engine/roundtable/swarm` | 201 | 201 | PASS |
| Swarm async launch | `POST /api/engine/roundtable/swarm/async` | 202 | 202 | PASS |
| Aria loop (direct API) | `POST /api/engine/chat/sessions/{id}/messages` | 200 + reply | 200 + reply | PASS |
| Mac→Web proxy API POST | `http://127.0.0.1:55559/api/engine/chat/sessions` | 201 | 201 | PASS |
| Mac→Traefik HTTP API POST | `http://127.0.0.1:33218/api/engine/chat/sessions` | 201 | 201 | PASS |
| Mac→Traefik HTTPS API POST | `https://127.0.0.1:17779/api/engine/chat/sessions` | 201 | 201 | PASS |
| Mac→Traefik HTTPS Aria message | `https://127.0.0.1:17779/api/engine/chat/sessions/{id}/messages` | 200 + reply | 200 + reply | PASS |

Reference runtime artifact: `aria_souvenirs/docs/runtime_smoke_2026-02-26.json`.

## Unresolved Literal /api Calls

- None

## Full Matrix

| Kind | File | Line | Method | Call Path | Route | Auth | Match |
|---|---|---:|---|---|---|---|---|
| script | scripts/benchmark_models.py | 113 | POST | {expr}/v1/chat/completions |  | unresolved | none |
| script | scripts/check_rpg_tools.py | 11 | GET | /engine/agents | /engine/agents | api_key | exact |
| script | scripts/check_rpg_tools.py | 25 | GET | /engine/tools |  | unresolved | none |
| script | scripts/check_rpg_tools.py | 56 | GET | /engine/roundtable | /engine/roundtable | api_key | exact |
| script | scripts/generate_skill_graph.py | 58 | DELETE | {expr}/knowledge-graph/auto-generated |  | unresolved | none |
| script | scripts/generate_skill_graph.py | 72 | POST | {expr}/knowledge-graph/entities |  | unresolved | none |
| script | scripts/generate_skill_graph.py | 88 | POST | {expr}/knowledge-graph/relations |  | unresolved | none |
| script | scripts/retitle_sessions.py | 41 | GET | {expr}/api/engine/sessions |  | unresolved | none |
| script | scripts/retitle_sessions.py | 62 | GET | {expr}/api/engine/sessions/{expr}/messages |  | unresolved | none |
| script | scripts/retitle_sessions.py | 87 | PATCH | {expr}/api/engine/sessions/{expr}/title |  | unresolved | none |
| script | scripts/retitle_sessions.py | 95 | PATCH | {expr}/api/engine/sessions/{expr}/title |  | unresolved | none |
| script | scripts/rpg_send.py | 24 | POST | /engine/chat/sessions | /engine/chat/sessions | api_key | exact |
| script | scripts/rpg_send.py | 48 | GET | /engine/chat/sessions/{expr} | /engine/chat/sessions/{session_id} | api_key | param |
| script | scripts/rpg_send.py | 63 | POST | /engine/chat/sessions/{expr}/messages | /engine/chat/sessions/{session_id}/messages | api_key | param |
| script | scripts/rpg_session.py | 19 | POST | /engine/chat/sessions | /engine/chat/sessions | api_key | exact |
| script | scripts/rpg_session.py | 36 | POST | /engine/chat/sessions/{expr}/messages | /engine/chat/sessions/{session_id}/messages | api_key | param |
| script | scripts/rpg_structured_test.py | 68 | GET | name |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 68 | GET | function |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 69 | GET | arguments |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 69 | GET | function |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 198 | GET | name |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 198 | GET | function |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 241 | GET | name |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 241 | GET | function |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 261 | GET | name |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 261 | GET | function |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 298 | POST | {expr}/engine/roundtable/async |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 311 | GET | {expr}/engine/roundtable/status/{expr} |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 394 | GET | name |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 394 | GET | function |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 438 | GET | name |  | unresolved | none |
| script | scripts/rpg_structured_test.py | 438 | GET | function |  | unresolved | none |
| script | scripts/test_all.py | 75 | GET | {expr}/models/db |  | unresolved | none |
| script | scripts/test_all.py | 94 | GET | {expr}/agents/db |  | unresolved | none |
| template | src/web/templates/engine_agent_dashboard.html | 57 | GET | /api/engine/agents/metrics | /engine/agents/metrics | api_key | exact |
| template | src/web/templates/engine_agents_mgmt.html | 500 | GET | /api/models/available | /models/available | api_key | exact |
| template | src/web/templates/engine_chat.html | 1388 | GET | /api/models/available | /models/available | api_key | exact |
| template | src/web/templates/engine_chat.html | 1537 | GET | /api/engine/agents | /engine/agents | api_key | exact |
| template | src/web/templates/engine_chat.html | 2219 | POST | /api/engine/chat/sessions | /engine/chat/sessions | api_key | exact |
| template | src/web/templates/sessions.html | 408 | GET | /api/engine/sessions | /engine/sessions | api_key | exact |
| template | src/web/templates/sessions.html | 598 | DELETE | /api/engine/sessions/ghosts | /engine/sessions/ghosts | api_key | exact |
| test | tests/e2e/conftest.py | 23 | GET | {expr}/api/health |  | unresolved | none |
| test | tests/test_artifacts_router.py | 49 | POST | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 64 | POST | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 76 | POST | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 87 | POST | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 104 | GET | /artifacts/logs/test.log | /artifacts/{category}/{filename:path} | api_key | param |
| test | tests/test_artifacts_router.py | 115 | GET | /artifacts/logs/missing.txt | /artifacts/{category}/{filename:path} | api_key | param |
| test | tests/test_artifacts_router.py | 129 | GET | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 144 | GET | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 152 | GET | /artifacts | /artifacts | api_key | exact |
| test | tests/test_artifacts_router.py | 166 | DELETE | /artifacts/drafts/draft.md | /artifacts/{category}/{filename:path} | api_key | param |
| test | tests/test_artifacts_router.py | 175 | DELETE | /artifacts/drafts/nope.md | /artifacts/{category}/{filename:path} | api_key | param |
| test | tests/test_engine_roundtable_router.py | 129 | POST | /engine/roundtable | /engine/roundtable | api_key | exact |
| test | tests/test_engine_roundtable_router.py | 143 | POST | /engine/roundtable | /engine/roundtable | api_key | exact |
| test | tests/test_engine_roundtable_router.py | 152 | POST | /engine/roundtable | /engine/roundtable | api_key | exact |
| test | tests/test_engine_roundtable_router.py | 164 | GET | /engine/roundtable | /engine/roundtable | api_key | exact |
| test | tests/test_engine_roundtable_router.py | 178 | GET | /engine/roundtable/rt-001 | /engine/roundtable/{session_id} | api_key | param |
| test | tests/test_engine_roundtable_router.py | 187 | GET | /engine/roundtable/nonexistent | /engine/roundtable/{session_id} | api_key | param |
| test | tests/test_engine_roundtable_router.py | 201 | GET | /engine/roundtable/status/abc123 | /engine/roundtable/status/{key} | api_key | param |
| test | tests/test_engine_roundtable_router.py | 207 | GET | /engine/roundtable/status/nonexistent | /engine/roundtable/status/{key} | api_key | param |
| test | tests/test_engine_roundtable_router.py | 217 | DELETE | /engine/roundtable/rt-001 | /engine/roundtable/{session_id} | api_key | param |
| test | tests/test_websocket.py | 82 | POST | /engine/chat/sessions | /engine/chat/sessions | api_key | exact |
| test | tests/test_websocket.py | 115 | DELETE | /engine/chat/sessions/{expr} | /engine/chat/sessions/{session_id} | api_key | param |
