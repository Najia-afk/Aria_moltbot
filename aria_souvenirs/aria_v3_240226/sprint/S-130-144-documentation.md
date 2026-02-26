# Sprint 6: Documentation Tickets

---

## S-130: Rewrite STRUCTURE.md
**Points:** 3 | **Priority:** P2

Remove 14 ghost files, add 13+ missing skills, add 3 missing routers (artifacts, engine_roundtable, rpg), fix engine file list, update template count 22→44, fix test count.

---

## S-131: Update API.md and API_ENDPOINT_INVENTORY.md
**Points:** 3 | **Priority:** P2

Add 3 missing routers, 31 missing endpoints. Fix summary "175+" → actual ~226. Fix router count 28→31. Fix page count 22→44.

---

## S-132: Rewrite aria_memories/README.md
**Points:** 1 | **Priority:** P2

Replace OpenClaw-era content with current memory architecture: surface/medium/deep layers, artifact API, working memory, knowledge graph.

---

## S-133: Fix TEST_COVERAGE_AUDIT False Claims
**Points:** 2 | **Priority:** P2

Regenerate with actual data. Claims "177 routes, 100% coverage" but API inventory lists 22+ untested endpoints.

---

## S-134: Update aria_mind/SKILLS.md Layer Table
**Points:** 2 | **Priority:** P2

Add 13 missing skills: rpg_campaign, rpg_pathfinder, sprint_manager, sentiment_analysis, pattern_recognition, memory_compression, unified_search, conversation_summary, etc.

---

## S-135: Fix All Documentation Contradictions (10 items)
**Points:** 3 | **Priority:** P2

Fix: CHANGELOG test count (677 vs 462), SECURITY.md date (Feb 4 → Feb 21), benchmarks.md Python "3.14.2" → 3.13, AGENTS.md agent count (6 vs 8), TOOLS.md skill count (35 → 43).

---

## S-136: Create RPG System Documentation
**Points:** 3 | **Priority:** P2

Document: rpg.py router (4 endpoints, 432 lines), rpg_campaign + rpg_pathfinder skills, prompts/rpg/ templates, rpg.html dashboard, KG integration.

---

## S-137: Create Analysis/Sentiment System Docs
**Points:** 2 | **Priority:** P2

Document: analysis.py router (16 endpoints), sentiment_analysis + pattern_recognition + memory_compression skills, autoscorer engine.

---

## S-138: Create CONTRIBUTING.md
**Points:** 2 | **Priority:** P2

Development workflow, PR process, testing standards, coding conventions, architecture rules.

---

## S-139: Document 22 New Dashboard Templates
**Points:** 2 | **Priority:** P2

Add all 22 templates to API.md/STRUCTURE.md: activity_visualization, agent_manager, engine_chat, engine_cron, rpg, sentiment, sprint_board, etc.

---

## S-140: Archive Stale AUDIT_REPORT.md
**Points:** 1 | **Priority:** P2

Move to docs/archive/. References deleted src/database/ directory.

---

## S-141: Align Architecture Layer Numbering
**Points:** 1 | **Priority:** P2

ARCHITECTURE.md uses 0-4 (Kernel→Orchestration). docs/architecture.md uses 1-5 (Database→ARIA). Standardize to one scheme.

---

## S-142: Document Engine Modules (telemetry, tool_registry, swarm)
**Points:** 2 | **Priority:** P2

3 engine modules completely undocumented. Add to STRUCTURE.md and create brief module docs.

---

## S-143: Update DEPLOYMENT.md
**Points:** 2 | **Priority:** P2

Fix: DB image name, port mappings, service count (7→14), database user/name references.

---

## S-144: Fix Dict→dict + Add @logged_method
**Points:** 2 | **Priority:** P2

Fix capital Dict in 5 files (goals, hourly_goals, performance, portfolio, social). Add @logged_method to all public skill methods missing it (~15 skills).
