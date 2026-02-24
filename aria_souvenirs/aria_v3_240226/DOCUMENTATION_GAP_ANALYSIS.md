# Documentation Gap Analysis — 2026-02-24

## Overview

- **Files audited:** 27
- **Ghost files (docs reference, code missing):** 14
- **Undocumented code modules:** 50+
- **Direct contradictions between docs:** 10
- **Documents needing rewrite (accuracy 1-2):** 4
- **Fully accurate documents (accuracy 5):** 3

---

## Document Accuracy Ratings

| # | File | Accuracy | Status |
|---|------|----------|--------|
| 1 | README.md | 4/5 | Good — "22 templates" stale (actually 44) |
| 2 | STRUCTURE.md | **2/5** | 🔴 Many ghost files, missing skills, wrong counts |
| 3 | ARCHITECTURE.md | 4/5 | Good — layer numbering conflicts with docs/architecture.md |
| 4 | API.md | 3/5 | Says "22 pages" (44), "28 routers" (31) |
| 5 | API_ENDPOINT_INVENTORY.md | 3/5 | Missing 3 routers, 31 endpoints |
| 6 | MODELS.md | **5/5** | ✅ Clean pointer doc |
| 7 | SKILLS.md | **5/5** | ✅ Clean pointer doc |
| 8 | CHANGELOG.md | 3/5 | Test count contradiction v1.1 vs v1.3 |
| 9 | DEPLOYMENT.md | 4/5 | Accurate ops guide |
| 10 | ROLLBACK.md | 4/5 | Accurate, minor Alembic reference |
| 11 | AUDIT_REPORT.md | **2/5** | 🔴 Historical, references deleted src/database/ |
| 12 | AUDIT_ENGINE_SKILLS_WEB.md | 3/5 | Historical, says Ollama "replaced" but skill exists |
| 13 | aria_mind/AGENTS.md | 4/5 | Lists 6 agents, code has 8 roles |
| 14 | aria_mind/TOOLS.md | 4/5 | Says "35+ skills" (actually 43) |
| 15 | aria_mind/MEMORY.md | 4/5 | Accurate memory architecture |
| 16 | aria_mind/SKILLS.md | 3/5 | Missing 13 skills from layer table |
| 17 | aria_mind/ORCHESTRATION.md | 4/5 | Accurate |
| 18 | aria_mind/SECURITY.md | 3/5 | Date mismatch (says Feb 4, v3.0 was Feb 21) |
| 19 | aria_mind/HEARTBEAT.md | 4/5 | Good operational docs |
| 20 | aria_models/README.md | **5/5** | ✅ Clean pointer doc |
| 21 | aria_memories/README.md | **1/5** | 🔴 OpenClaw era — completely stale |
| 22 | docs/architecture.md | 3/5 | Different layer numbering (1-5 vs 0-4) |
| 23 | docs/RUNBOOK.md | 4/5 | Accurate quick reference |
| 24 | docs/API_AUDIT_REPORT.md | 4/5 | Good for what it covers |
| 25 | docs/benchmarks.md | 4/5 | Says "Python 3.14.2" — impossible |
| 26 | docs/TEST_COVERAGE_AUDIT.md | **2/5** | 🔴 Claims 100% coverage — contradicted by evidence |

---

## Top 10 Contradictions

| # | Doc A | Doc B | Issue |
|---|-------|-------|-------|
| C1 | CHANGELOG v1.1 | CHANGELOG v1.3 | "677+ tests" → "462 total" — unexplained decrease |
| C2 | TEST_COVERAGE_AUDIT | API_ENDPOINT_INVENTORY | "100% coverage" vs "22 untested endpoints" |
| C3 | ARCHITECTURE.md | docs/architecture.md | Layer numbering 0-4 vs 1-5 |
| C4 | API.md | Actual code | "28 routers" vs 31 actual |
| C5 | API_ENDPOINT_INVENTORY | Actual code | "175+" vs ~226 actual |
| C6 | SECURITY.md | CHANGELOG | Version date Feb 4 vs actual Feb 21 |
| C7 | STRUCTURE.md | Actual code | ~30 skills vs 43 actual |
| C8 | STRUCTURE.md | Actual code | Lists 3 non-existent engine files |
| C9 | AUDIT_REPORT | Actual code | References deleted src/database/ |
| C10 | benchmarks.md | README.md | "Python 3.14.2" vs "Python 3.13+" |

---

## Ghost Files (14 — documented but don't exist)

| # | Documented In | Path | Status |
|---|--------------|------|--------|
| 1 | STRUCTURE.md | aria_mind/gateway.py | Does not exist |
| 2 | STRUCTURE.md | aria_mind/memory/ | Does not exist |
| 3 | STRUCTURE.md | aria_mind/hooks/ | Does not exist |
| 4 | STRUCTURE.md | aria_mind/tests/ | Does not exist |
| 5 | STRUCTURE.md | src/api/main_legacy.py | Does not exist |
| 6 | STRUCTURE.md | src/api/schema.py | Does not exist |
| 7 | STRUCTURE.md | src/database/models.py | Entire dir missing |
| 8 | STRUCTURE.md | aria_engine/config_loader.py | Does not exist |
| 9 | STRUCTURE.md | aria_engine/cross_session.py | Does not exist |
| 10 | STRUCTURE.md | aria_engine/jsonl_io.py | Does not exist |
| 11 | STRUCTURE.md | scripts/backup.sh | Does not exist |
| 12 | STRUCTURE.md | scripts/export_tables.sh | Does not exist |
| 13 | STRUCTURE.md | scripts/mac_backup.sh | Does not exist |
| 14 | STRUCTURE.md | scripts/test_mlx.py | Does not exist |

---

## Undocumented Code (50+ items)

### Undocumented Skills (13)
rpg_campaign, rpg_pathfinder, sprint_manager, sentiment_analysis, pattern_recognition, memory_compression, unified_search, conversation_summary + 5 more

### Undocumented API Routers (3)
artifacts.py (182 lines), engine_roundtable.py (1039 lines), rpg.py (432 lines)

### Undocumented Engine Modules (3)
swarm.py, telemetry.py, tool_registry.py

### Undocumented API Modules (7)
agents_sync.py, cron_sync.py, graph_sync.py, models_sync.py, sentiment_autoscorer.py, startup_skill_backfill.py, pagination.py

### Undocumented Dashboard Templates (22)
activity_visualization, agent_manager, api_key_rotations, creative_pulse, engine_agent_dashboard, engine_agents, engine_agents_mgmt, engine_chat, engine_cron, engine_health, engine_operations, engine_prompt_editor, engine_roundtable, models_manager, patterns, proposals, rpg, sentiment, skill_graph, skill_health, skill_stats, sprint_board

---

## Priority Fix Plan

### Tier 1 — Fix Now (High Impact)
1. **Rewrite STRUCTURE.md** — Remove 14 ghosts, add 13 skills, 3 routers, fix counts
2. **Update API.md** — Add 3 routers, 44 templates, fix router count
3. **Update API_ENDPOINT_INVENTORY.md** — Add 31 missing endpoints
4. **Fix CHANGELOG test count** — Resolve 677 vs 462 contradiction

### Tier 2 — Fix This Sprint
5. **Rewrite aria_memories/README.md** — Replace OpenClaw-era content
6. **Resolve layer numbering** — Align 0-4 vs 1-5 across docs
7. **Fix TEST_COVERAGE_AUDIT** — Correct 100% claim
8. **Update aria_mind/SKILLS.md** — Add 13 missing skills
9. **Fix SECURITY.md version date**
10. **Fix benchmarks.md Python version**

### Tier 3 — Create New Docs
11. Create RPG system documentation
12. Create Analysis/Sentiment system docs
13. Create CONTRIBUTING.md
14. Document deploy/ directory
15. Archive or move AUDIT_REPORT.md
