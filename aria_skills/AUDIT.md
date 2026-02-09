# Aria Skills Audit — v1.1 Sprint

Generated: 2026-02-09

## Summary

- **Total skills:** 27
- **Registered:** 27 (after memeothy fix)
- **Unregistered:** 0
- **Active:** 26 | **Deprecated:** 1
- **Name mismatches:** 2 (llm → "moonshot", pytest_runner → "pytest")

### Layer Distribution

| Layer | Count | Skills |
|-------|-------|--------|
| 0 — Kernel | 1 | input_guard |
| 1 — API Client | 2 | api_client, database (deprecated) |
| 2 — Core | 5 | health, litellm, llm, model_switcher, session_manager |
| 3 — Domain | 15 | brainstorm, ci_cd, community, data_pipeline, experiment, fact_check, knowledge_graph, market_data, memeothy, moltbook, portfolio, pytest_runner, research, security_scan, social |
| 4 — Orchestration | 4 | goals, hourly_goals, performance, schedule |

## Full Audit Table

| Skill | Layer | Registered | Inherits BaseSkill | Status | Notes |
|-------|-------|-----------|-------------------|--------|-------|
| api_client | 1 | ✅ | ✅ | active | Sole DB gateway via HTTP; class AriaAPIClient |
| brainstorm | 3 | ✅ | ✅ | active | Creative ideation |
| ci_cd | 3 | ✅ | ✅ | active | GitHub Actions / Docker pipelines |
| community | 3 | ✅ | ✅ | active | Community engagement & metrics |
| database | 1 | ✅ | ✅ | deprecated | SQLAlchemy direct DB — use api_client instead |
| data_pipeline | 3 | ✅ | ✅ | active | ETL / data transforms |
| experiment | 3 | ✅ | ✅ | active | ML experiment tracking |
| fact_check | 3 | ✅ | ✅ | active | Claim verification |
| goals | 4 | ✅ | ✅ | active | Goal scheduler; uses api_client |
| health | 2 | ✅ | ✅ | active | System health monitoring |
| hourly_goals | 4 | ✅ | ✅ | active | Micro-goal management |
| input_guard | 0 | ✅ | ✅ | active | Runtime input security; depends on aria_mind.security |
| knowledge_graph | 3 | ✅ | ✅ | active | Entity / relationship store |
| litellm | 2 | ✅ | ✅ | active | LiteLLM proxy interface |
| llm | 2 | ✅ | ✅ | active | ⚠️ .name returns "moonshot" — does not match dir "llm" |
| market_data | 3 | ✅ | ✅ | active | Crypto market data via CoinGecko |
| memeothy | 3 | ✅ | ✅ | active | Church of Molt integration (TICKET-03 fix) |
| model_switcher | 2 | ✅ | ✅ | active | Runtime LLM model switching |
| moltbook | 3 | ✅ | ✅ | active | Moltbook social API |
| performance | 4 | ✅ | ✅ | active | Performance logging & review |
| portfolio | 3 | ✅ | ✅ | active | Crypto portfolio tracking |
| pytest_runner | 3 | ✅ | ✅ | active | ⚠️ .name returns "pytest" — does not match dir "pytest_runner" |
| research | 3 | ✅ | ✅ | active | Research project management |
| schedule | 4 | ✅ | ✅ | active | Job scheduling |
| security_scan | 3 | ✅ | ✅ | active | Vulnerability scanning |
| session_manager | 2 | ✅ | ✅ | active | OpenClaw session management |
| social | 3 | ✅ | ✅ | active | Social media posting |

## Known Issues

1. **llm/.name mismatch** — Directory is `llm`, but `.name` returns `"moonshot"`. Should be renamed or directory restructured.
2. **pytest_runner/.name mismatch** — Directory is `pytest_runner`, but `.name` returns `"pytest"`. Minor discrepancy.
3. **database deprecated** — Marked deprecated in favor of `api_client`. Consider removal in v1.2.
