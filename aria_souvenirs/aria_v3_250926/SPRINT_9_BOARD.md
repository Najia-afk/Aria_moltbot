# Sprint 9 — Swarm Architecture Audit & Production Verification
**Sprint:** 9
**Created:** 2026-09-25 (same day as Sprint 8 — continuation, not a new day)
**Total Points:** 23
**Theme:** Use a parallel subagent swarm to review the whole codebase + docs, fix what it found, then verify the fixes by watching real production logs — which surfaced two more real bugs the swarm never saw.

---

## Board

| ID | Title | Priority | Pts | Status | Assignee |
|----|-------|----------|-----|--------|----------|
| SP9-01 | Swarm audit: architecture, security, skills, engine, mind, docs, tests | P0 | 3 | ✅ Done | Copilot (7 subagents) |
| SP9-02 | Fix admin token timing-unsafe comparison | P1 | 1 | ✅ Done | Copilot |
| SP9-03 | Fix deprecated `asyncio.get_event_loop()` (breaks on Python 3.14) | P1 | 1 | ✅ Done | Copilot |
| SP9-04 | Fix unprotected dict mutation in memory_cache.py | P1 | 1 | ✅ Done | Copilot |
| SP9-05 | Remove stale unregistered duplicate rpg_campaign skill | P2 | 1 | ✅ Done | Copilot |
| SP9-06 | Add missing `status` field to 45 skill.json manifests | P2 | 2 | ✅ Done | Copilot |
| SP9-07 | Fix stale doc drift (STRUCTURE.md, DEPLOYMENT.md, aria_models/README.md, API.md, CHANGELOG.md) | P2 | 2 | ✅ Done | Copilot |
| SP9-08 | Fix L1→L3 layering inversion (api_client importing knowledge_graph) | P1 | 3 | ✅ Done | Copilot |
| SP9-09 | Fix memeothy credential path (was outside aria_memories, wasn't even a mounted volume) | P1 | 2 | ✅ Done | Copilot |
| SP9-10 | Fix pre-existing test_model_switcher.py hardcoded-model test bug | P2 | 1 | ✅ Done | Copilot |
| SP9-11 | Fix context-budget bypass — trinity's real 1M contextWindow silently disabled compaction | P0 | 3 | ✅ Done | Copilot |
| SP9-12 | Fix unsafe fallback — sentiment_tiny (0.5B/32K) was the catch-all for failed agentic requests | P0 | 2 | ✅ Done | Copilot |
| SP9-13 | Suppress noisy per-request litellm/Pydantic serializer warning | P3 | 1 | ✅ Done | Copilot |
| SP9-14 | Extend mobile-UI audit past the chat page to all 52 templates | P1 | 3 | ✅ Done | Copilot |

---

## SP9-01 · Swarm audit
**Priority:** P0 · **Points:** 3 · **Status:** ✅ Done

Ran 7 parallel Explore subagents: architecture layering, OWASP security, aria_skills catalog (44 skills), aria_engine reliability, aria_mind, docs-vs-code drift, test suite health. One subagent (test suite) **claimed** to run pytest but only predicted results without actually executing anything — caught this and ran it myself: 175/175 passed at that point, confirming the swarm's other findings were reviewed against a real baseline, not just their say-so. This is now a standing lesson: subagent claims of "I ran X" must be spot-verified, not trusted blindly.

## SP9-08 · L1→L3 layering inversion
**Priority:** P1 · **Points:** 3 · **Status:** ✅ Done

**Problem:** `api_client` (L1, the foundational skill every other skill depends on) imported `aria_skills.knowledge_graph.cache` (L3) seven times for cache invalidation — inverting the intended one-way dependency direction.

**Root cause:** The cache module (`LRUCache`/`KGCacheManager`) is a generic, thread-safe TTL cache with zero coupling to KG-specific logic. Its own docstring already said "shared by api_client, kernel router, and KG skill" — it was always meant to live at the shared layer, just implemented in the wrong package.

**Fix:** `git mv aria_skills/knowledge_graph/cache.py aria_skills/api_client/cache.py` (history preserved). Updated all 7 sites in `api_client/__init__.py`, `knowledge_graph/__init__.py` (now correctly L3→L1), plus 9 sites in `src/api/routers/knowledge.py` and the test file.

**Verification:** Live end-to-end check against `/api/knowledge-graph/entities` after redeploy — real data returned, cache still functioning.

## SP9-11 · Context-budget bypass (found via live log review, not the swarm)
**Priority:** P0 · **Points:** 3 · **Status:** ✅ Done

**Problem:** A cron session logged `in=395726 out=1481 cost=0.000000 latency=175293ms` — 395K input tokens and 175 seconds for a single request, despite `chat_engine.py` logging "Context budget applied ... max_prompt=150000" at session start.

**Root cause:** `_get_model_token_limits()` falls back to a model's raw `contextWindow` as its hard token-budget limit whenever `safe_prompt_tokens` isn't set. Earlier today, fixing the dead `trinity` model correctly set `contextWindow: 1000000` (nemotron's real capacity) — but that same field doubling as the budget-enforcement ceiling meant compaction never engaged until 1M tokens, 6.6x past the system's own stated 150K target.

**Fix:** Added `safe_prompt_tokens: 120000` to `trinity` in `models.yaml` (matches `kimi`'s existing pattern of a real, sane operating ceiling below its raw window).

## SP9-12 · Unsafe fallback (found investigating SP9-11)
**Priority:** P0 · **Points:** 2 · **Status:** ✅ Done

**Problem:** The same slow session's logs showed the retry-on-failure path landed on `sentiment_tiny` — a 0.5B local model with a 32K context window and `tasks: [sentiment]` only — for a full agentic tool-calling request with 8 tools. That model can't even fit the prompt, let alone reason about it or call tools meaningfully.

**Root cause:** `kimi` (paid) is deliberately excluded from `routing.fallbacks` for cost control, and `qwen3.5_mlx` was removed earlier today for RAM reasons — which left `sentiment_tiny` as the *only* remaining entry in the general fallback chain, despite never being fit for that role. Fallback selection in `llm_gateway.py` is completely task-blind — it just walks the chain in order regardless of suitability.

**Fix:** Removed `sentiment_tiny`'s `fallback_order`/`priority` so it's excluded from `routing.fallbacks` (still reachable directly via `tasks: [sentiment]`). `routing.fallbacks` now correctly resolves to `[trinity]` only — if trinity fails, the request now fails loudly with a clear error instead of silently degrading to a nonsensical truncated response from an unsuitable model.

**Note:** This means there is currently **no real fallback** for chat if trinity is down — carried to Sprint 10 as SP10-01 (a second free-model fallback), since a fail-loud error is safer than the previous silent-garbage behavior but isn't the ideal end state either.

## SP9-14 · Extended mobile-UI audit
**Priority:** P1 · **Points:** 3 · **Status:** ✅ Done

Scripted a check across all 52 templates for the same bug classes fixed in `engine_chat.html` earlier (missing `100dvh` fallback, sub-16px input font triggering iOS zoom). Found and fixed:
- 6 more full-height pages missing the dvh fallback: `engine_prompt_editor`, `knowledge`, `memory_graph`, `rpg`, `skill_graph`, `soul`.
- 1 more sub-16px `<select>` in `memory_timeline.html`.

**Not fixed — flagged, not blindly changed:** 17 templates flagged as "no mobile media query at all" by the script. Many of these are admin/data-heavy pages (agent_manager, security, services, etc.) that may already be adequately handled by `base.css`'s global responsive rules — or may not be. Deciding which without visual inspection risks doing more harm than good. Carried to Sprint 10 as SP10-02.

---

## Carried to Sprint 10

- **SP10-01 (P1):** Add a second free-model fallback behind trinity so chat has real resilience again, not just fail-loud (was previously masked by an unsafe fallback to sentiment_tiny — see SP9-12).
- **SP10-02 (P2):** Manually visually review the 17 templates flagged with no mobile-specific CSS at all, and fix only the ones that actually look broken on a phone.
- **SP10-03 (P1):** Manual phone/Tailscale visual QA of the chat UI (still not done — no browser-to-host-network access in this session for the sandboxed check; the shared-tab checks that worked were desktop-viewport only in practice).
- **SP10-04 (P2):** `api_client` skill's cache-invalidation try/except blocks swallow all exceptions silently (`except Exception: pass`) — should at least debug-log.
- **SP10-05 (P3):** Write real unit tests for `aria_mind` (cognition.py, memory.py, security.py, heartbeat.py — 0% coverage) and `aria_agents` (base.py, context.py, coordinator.py, loader.py, scoring.py — 0% coverage). This is genuinely substantial work, not a quick fix — scope it as its own sprint rather than squeezing it in.
- **SP10-06 (P3):** aria_skills manifests: `input_guard/skill.json` intentionally omits `status` — confirm intent and document, or add it for consistency.
