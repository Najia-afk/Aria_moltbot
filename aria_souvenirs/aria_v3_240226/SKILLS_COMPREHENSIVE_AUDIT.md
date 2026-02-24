# Skills Comprehensive Audit — 2026-02-24

## Overview

- **Total skill directories:** 42 (40 code + _template + __pycache__)
- **Active & registered:** 38
- **Deprecated/superseded:** 2 (database, llm)
- **In-memory stubs:** 2 (data_pipeline, portfolio)
- **BaseSkill compliance:** 100%
- **Registry compliance:** 100%
- **skill.json coverage:** 100%
- **Skills with tests:** ~6 (API-level only)
- **Skills without tests:** ~28

---

## Complete Inventory

| # | Skill | Layer | Status | Issues |
|---|-------|-------|--------|--------|
| 1 | api_client | L1 | ✅ Active | Gateway — core dependency |
| 2 | input_guard | L0 | ✅ Active | MEDIUM: creates independent httpx client |
| 3 | health | L2 | ✅ Active | Clean |
| 4 | litellm | L2 | ✅ Active | Missing @logged_method on some methods |
| 5 | moonshot | L2 | ✅ Active | Clean |
| 6 | ollama | L2 | ✅ Active | Clean |
| 7 | session_manager | L2 | ✅ Active | MEDIUM: direct filesystem reads |
| 8 | model_switcher | L2 | ✅ Active | HIGH: imports from aria_engine, missing from __init__.py |
| 9 | working_memory | L2 | ✅ Active | Uses _client directly |
| 10 | brainstorm | L3 | ✅ Active | In-memory only, no persistence |
| 11 | ci_cd | L3 | ✅ Active | Partial — no actual GitHub API integration |
| 12 | community | L3 | ✅ Active | In-memory only, no persistence |
| 13 | conversation_summary | L3 | ✅ Active | HIGH: direct httpx to LiteLLM, hardcoded API key |
| 14 | data_pipeline | L3 | ⚠️ Stub | In-memory only, TODO TICKET-12 |
| 15 | database | L1 | 🔴 Deprecated | Should be deleted |
| 16 | experiment | L3 | ✅ Active | JSONL file persistence, bypasses api_client |
| 17 | fact_check | L3 | ⚠️ Partial | Regex-only extraction, no LLM verification |
| 18 | knowledge_graph | L3 | ✅ Active | Uses _client directly, missing @logged_method |
| 19 | market_data | L3 | ✅ Active | Missing @logged_method |
| 20 | memeothy | L3 | ✅ Active | MEDIUM: plaintext credential storage |
| 21 | memory_compression | L3 | ✅ Active | Clean |
| 22 | moltbook | L3 | ✅ Active | Uses _client directly |
| 23 | pattern_recognition | L3 | ✅ Active | Clean |
| 24 | portfolio | L3 | ⚠️ Stub | In-memory only, TODO TICKET-12 |
| 25 | pytest_runner | L3 | ✅ Active | HIGH: no input sanitization → command injection |
| 26 | research | L3 | ✅ Active | Clean |
| 27 | rpg_campaign | L3 | ✅ Active | MEDIUM: path traversal via campaign_id |
| 28 | rpg_pathfinder | L3 | ✅ Active | MEDIUM: path traversal via campaign_id |
| 29 | sandbox | L3 | ✅ Active | HIGH: code injection via f-string interpolation |
| 30 | security_scan | L3 | ✅ Active | Pattern-only, no real CVE scanning |
| 31 | sentiment_analysis | L3 | ✅ Active | Clean |
| 32 | social | L3 | ✅ Active | MEDIUM: fallback httpx clients |
| 33 | sprint_manager | L3 | ✅ Active | Uses _client directly |
| 34 | telegram | L3 | ✅ Active | Clean |
| 35 | unified_search | L3 | ✅ Active | Clean |
| 36 | goals | L4 | ✅ Active | Uses _client directly, Dict type issue |
| 37 | hourly_goals | L4 | ✅ Active | Uses _client directly, Dict type issue |
| 38 | performance | L4 | ✅ Active | Uses _client directly, Dict type issue |
| 39 | schedule | L4 | ✅ Active | Uses _client directly |
| 40 | agent_manager | L4 | ✅ Active | Uses _client directly |
| 41 | pipeline_skill | L4 | ✅ Active | Name mismatch (dir vs .name) |
| 42 | llm | L2 | 🔴 Superseded | Duplicates moonshot + ollama, should delete |

---

## Architecture Violations

### Cross-Layer (5)

| Skill | Violation | Severity |
|-------|-----------|----------|
| model_switcher (L2) | Imports `aria_engine.thinking` (engine > skill layer) | HIGH |
| conversation_summary (L3) | Direct httpx to LiteLLM proxy, bypasses api_client | HIGH |
| input_guard (L0) | Independent httpx client for security events | MEDIUM |
| session_manager (L2) | Direct filesystem reads + independent httpx | MEDIUM |
| social (L3) | Fallback httpx clients to multiple URLs | MEDIUM |

### Private Member Access (11 skills)

agent_manager, goals, hourly_goals, knowledge_graph, performance, schedule, sprint_manager, working_memory, moltbook — all access `self._api._client` directly.

**Fix:** Create public `api_client` methods for all common operations.

---

## Security Concerns

### HIGH (P0)

| Skill | Issue | Risk |
|-------|-------|------|
| sandbox | f-string interpolation in write_file/read_file | Code injection |
| pytest_runner | Unsanitized path/markers/keywords in subprocess | Command injection |
| conversation_summary | Hardcoded `sk-aria-internal` API key | Credential leak |

### MEDIUM (P1)

| Skill | Issue | Risk |
|-------|-------|------|
| memeothy | Plaintext credentials at ~/.config/molt/credentials.json | Credential exposure |
| rpg_campaign / rpg_pathfinder | No campaign_id sanitization | Path traversal |
| experiment | Direct JSONL filesystem writes | Data integrity |
| session_manager | Agent name-based filesystem reads | Path traversal |

---

## Skills Requiring Action

### Delete
- `llm/` — superseded by moonshot/ and ollama/, causes double-registration
- `database/` — deprecated, should be removed

### Fix Security (P0)
- `sandbox` — sanitize write_file/read_file (shlex.quote or base64)
- `pytest_runner` — validate path allowlist, sanitize markers/keywords
- `conversation_summary` — remove hardcoded key, route through litellm skill

### Fix Architecture (P1)
- `model_switcher` — remove aria_engine import, move logic to skill layer
- `input_guard` — route security events through api_client
- `session_manager` — route all data through api_client
- `social` — remove fallback httpx clients
- All 11 `_client`-accessing skills — create public api_client methods

### Add Persistence (P2)
- `data_pipeline` — implement API persistence (TICKET-12)
- `portfolio` — implement API persistence (TICKET-12)
- `brainstorm` — add optional persistence
- `community` — add persistence

### Fix Code Quality (P2)
- Fix `Dict` → `dict` in 5 files (goals, hourly_goals, performance, portfolio, social)
- Add `model_switcher` to `__init__.py` imports
- Add `@logged_method()` to all public skill methods consistently
