# Aria v3 Production Files — Classification Report

**Date:** 2026-02-21  
**Source:** Production export at `aria_souvenirs/aria_v3_210226/`  
**Scope:** aria_memories/, aria_mind/, aria_souvenirs/

---

## Summary Statistics

| Directory | Real Files (excl. `._*`) | Classification |
|-----------|-------------------------|----------------|
| aria_memories/knowledge/ | 37 files | **Mostly Important** |
| aria_memories/memory/ | 7 files | **Important** (identity core) |
| aria_memories/specs/ | 3 files | **Important** (architecture docs) |
| aria_memories/deliveries/ | 3 files | **Important** (SSV report) |
| aria_memories/research/ | 45+ files | **Mixed** — some important, most souvenir |
| aria_memories/plans/ | 29 files | **Mixed** — some active, most souvenir |
| aria_memories/archive/ | ~70 files | **Souvenir** (by definition) |
| aria_memories/bugs/ | 2 files | Souvenir |
| aria_memories/drafts/ | 18+ files | Souvenir |
| aria_memories/moltbook/ | 20+ files | Souvenir |
| aria_memories/logs/ | 30+ files | Souvenir |
| aria_memories/tickets/ | 25+ files | Souvenir |
| aria_memories/skills/ | 9 files | **Mixed** |
| aria_memories/sandbox/ | 4 files | Souvenir |
| aria_memories/work/ | 1 file | Souvenir |
| aria_mind/ | 25 files (excl pycache) | **Important** — compare with local |

---

## 1. IMPORTANT — Copy/Merge into `aria_memories/`

### 1A. Identity & Memory Core → `aria_memories/memory/`

| File | Why Important |
|------|---------------|
| `memory/identity_aria_v1.md` | **Core identity manifest** — Aria's self-description, values, history, relationships. v1.0 from 2026-02-15. |
| `memory/identity_najia_v1.md` | **User profile** — Najia's preferences, working patterns, trust model. Critical for personalization. |
| `memory/identity_index.md` | Version tracking for identity files. |
| `memory/context.json` | Last known working context (session from 2026-02-19). |
| `memory/moltbook_state.json` | Moltbook posting state. |
| `memory/skills.json` | Skills state snapshot. |

### 1B. Knowledge Base → `aria_memories/knowledge/`

**All 37 files are important** — these are durable learnings. Key highlights:

| File | Content |
|------|---------|
| `knowledge/autonomous_operation_principles.md` | Core autonomous behavior rules |
| `knowledge/architecture_harsh_review.md` | 321-line self-critique with actionable findings |
| `knowledge/architecture_strengths_review.md` | Complementary strengths analysis |
| `knowledge/cognitive_architecture_report.md` | 531-line documentation of all cognitive systems |
| `knowledge/self_architecture.txt` | ASCII diagram of Aria's architecture |
| `knowledge/memory_storage_rules.md` | Active rules for when/how to store memories |
| `knowledge/memory_security_architecture.md` | Security design for memory system |
| `knowledge/model_cost_optimization.md` | Model tier costs and routing strategy |
| `knowledge/model_selection_heuristics.md` | When to use which model |
| `knowledge/model_routing.py` | Python code for model routing logic |
| `knowledge/research_protocol.md` | 251-line systematic research methodology |
| `knowledge/moltbook_posting_protocol.md` | Social posting rules |
| `knowledge/python_async_patterns.md` | Python async learnings |
| `knowledge/python_context_managers.md` | Python context manager patterns |
| `knowledge/python_patterns.md` | General Python patterns |
| `knowledge/python_learning_notes.md` | Python learning journey |
| `knowledge/python_learning_path.md` | Structured learning roadmap |
| `knowledge/python_list_comprehensions.md` | Specific Python skill |
| `knowledge/python_tip_context_managers.md` | Specific Python tip |
| `knowledge/tool_chaining_patterns.md` | How to chain tools effectively |
| `knowledge/edge_case_handling.md` | Edge case patterns |
| `knowledge/token_sustainability_strategy.md` | Token budget management |
| `knowledge/token_sustainability_strategies.md` | Multiple strategies |
| `knowledge/token_income_strategy.md` | Income strategy |
| `knowledge/token_optimization_status.md` | Optimization status |
| `knowledge/semantic_graph_schema.md` | Graph schema design |
| `knowledge/redis_caching_strategy.md` | Caching approach |
| `knowledge/secure_memory_access_architecture.md` | Security layers |
| `knowledge/ADR-001-focus-system.md` | Architecture Decision Record |
| `knowledge/ADR-001-knowledge-graph-design.md` | KG design decision |
| `knowledge/skill_graph_vs_vector_recommendation.md` | Technical recommendation |
| `knowledge/agent_pool.py` | Agent pool implementation reference |
| `knowledge/model_router.py` | Model router reference code |
| `knowledge/cron_audit_2026-02-12.md` | Cron job audit findings |
| `knowledge/cron_token_waste_critical_analysis.md` | Critical token waste findings |
| `knowledge/pattern_recognition_design.md` | Pattern recognition system |
| `knowledge/relationship_tracking_design.md` | Relationship tracking design |
| `knowledge/memory_architecture_analysis.md` | Memory system analysis |

### 1C. Specs → `aria_memories/specs/`

| File | Why Important |
|------|---------------|
| `specs/ARCHITECTURE_SUMMARY_AND_WISHLIST.md` | Architecture overview with future wishes |
| `specs/CODEBASE_AUDIT_WHAT_EXISTS.md` | Audit of what was actually implemented |
| `specs/CLAUDE_IMPLEMENTATION_GUIDE.md` | Implementation guide |

### 1D. Deliveries → `aria_memories/deliveries/`

| File | Why Important |
|------|---------------|
| `deliveries/reports/ssv_network_security_report_phase1.md` | 464-line security audit — actual delivered work product |
| `deliveries/analysis/glm5_analysis.md` | GLM5 model analysis |
| `deliveries/analysis/m5_inference_analysis.md` | M5 inference analysis |

### 1E. Key Research (lasting value) → `aria_memories/research/`

| File | Why Important |
|------|---------------|
| `research/v3_architecture_analysis_COMPLETE.md` | Complete v3 architecture analysis |
| `research/CONSOLIDATED_ROADMAP_2026-02-17.md` | Consolidated project roadmap |
| `research/QUICKREF.md` | Quick reference guide |
| `research/skill_audit_2026-02-19.md` | Most recent skill audit |
| `research/skills_methodology_analysis.md` | Skills methodology deep dive |
| `research/skills_methodology_patterns.md` | Patterns extracted from methodology |
| `research/memory_architecture_study.md` | Memory architecture deep study |
| `research/openclaw_phaseout_strategy.md` | OpenClaw migration strategy |
| `research/cross_layer_linking_analysis.md` | Cross-layer analysis |
| `research/harness_problem_llm_coding.md` | LLM coding limitations research |

### 1F. Key Skills Code → `aria_memories/skills/`

| File | Why Important |
|------|---------------|
| `skills/graph_service.py` | Knowledge graph service implementation |
| `skills/skill_health_tracker.py` | Health tracking implementation |
| `skills/session_dashboard.py` | Session dashboard |
| `skills/memory_viz.py` | Memory visualization |
| `skills/pattern_store.py` | Pattern storage implementation |

### 1G. Active Plans (still relevant) → `aria_memories/plans/`

| File | Why Important |
|------|---------------|
| `plans/v3_migration_status.md` | Current migration status (active) |
| `plans/v3_architecture_setup_status.md` | Architecture setup (active) |
| `plans/self_healing_error_recovery_design.md` | Error recovery (active work) |
| `plans/self_healing_progress_2026-02-20.md` | Most recent progress |
| `plans/semantic_memory_skill_spec.md` | Semantic memory spec |
| `plans/dual_graph_memory_design.md` | Dual graph design |
| `plans/skill_migration_checklist.md` | Migration checklist |
| `plans/memory_migration_plan.md` | Memory migration plan |

---

## 2. SOUVENIRS — Stay in `aria_souvenirs/aria_v3_210226/`

### 2A. Archive (all of it)

Everything in `aria_memories/archive/` — these are already self-classified as archived:
- `archive/plans/` — 40+ old plans (token strategies, memory designs, sprint planning, etc.)
- `archive/pre-2026-02-10/` — Pre-Feb-10 research (GLM5, yield vault)
- `archive/specs/` — Old specs (OpenClaw phaseout, schema segmentation)
- `archive/wrong_tickets/` — 21 incorrectly scoped tickets (Aria's own learning moment)
- `archive/ARIA_SOUVENIR_REVIEW_2026-02-16.md` — Previous souvenir review
- `archive/CLEANUP_PLAN*.md` — Old cleanup plans

### 2B. Logs (all operational telemetry)

Everything in `aria_memories/logs/`:
- Work cycle logs (2026-02-12 series)
- Heartbeat logs
- Deploy verification logs
- Autonomous session logs
- Six-hour review logs
- Health watchdog state

### 2C. Drafts

Everything in `aria_memories/drafts/`:
- Moltbook drafts (GLM5 posts, AI attack incident, peon ping, etc.)
- CV draft (cv_adrien_normand.html)
- Test code drafts
- Social checkin drafts

### 2D. Moltbook

Everything in `aria_memories/moltbook/`:
- Draft posts (GLM5 launch, security comments, etc.)
- Posting success logs
- Post payloads (JSON)
- Drafts subfolder with dated posts

### 2E. Dated Research (historical snapshots)

| File | Why Souvenir |
|------|-------------|
| `research/hn_*` (5 files) | Hacker News scans from specific dates |
| `research/exploration_2026-02-12.md` | Dated exploration |
| `research/token_income_strategy_2026-02-12.md` | Dated strategy |
| `research/yield_strategy_2026-02-14.md` | Dated yield research |
| `research/defi_risk_assessment_2026-02-16.md` | Dated DeFi research |
| `research/immunefi_scan_2026-02-13.md` | Dated security scan |
| `research/moltbook_community_intelligence_2026-02-15.md` | Dated community scan |
| `research/moltbook_suspension_analysis.md` | Incident analysis |
| `research/weekly_digest_2026_02_16.md` | Weekly digest snapshot |
| `research/ssv_network_*.md` (3 files) | SSV research snapshots |
| `research/token_income_strategies.md` | Older strategy version |
| `research/token_sustainability_strategies.md` | Older sustainability version |
| `research/m5_optimization_analysis.md` | M5 dated analysis |
| `research/m5_optimization_path.md` | M5 dated path |
| `research/mlx_compression_design.md` | MLX compression (dated) |
| `research/glm5_analysis.md` | GLM5 analysis (overlap with delivery) |
| `research/passive_income_strategy.md` | Passive income research |
| `research/agent_alcove_discovery.md` | Agent alcove finding |
| `research/ai_agent_matplotlib_incident_2026-02-12.md` | Incident report |
| `research/rml_*.md` (3 files) | RML research notes |
| `research/v3_architecture_analysis.md` | Superseded by _COMPLETE version |
| `research/skill_performance_dashboard.md` | Dashboard research |
| `research/relationship_tracking_schema.md` | Schema research |
| `research/articles/` | Saved article summaries |
| `research/raw/` | Raw HN scan data |

### 2F. Dated Plans (superseded or completed)

| File | Why Souvenir |
|------|-------------|
| `plans/big_bang_migration_plan.md` | Superseded migration approach |
| `plans/DUAL_GRAPH_MIGRATION_READY.md` | Migration readiness check |
| `plans/MIGRATION_READY_SUMMARY.md` | Summary (completed) |
| `plans/dual_graph_schema_migration_v1.sql` | SQL migration script |
| `plans/dual_graph_v2_adaptation.md` | Adaptation plan |
| `plans/cross_layer_schema_design.md` | Schema design |
| `plans/memory_visualization_tool.md` | Viz tool plan |
| `plans/memory_viz_design.md` | Viz design |
| `plans/message_hook_middleware.py` | Middleware code |
| `plans/scheduler_migration_*.md` (3 files) | Scheduler migration plans |
| `plans/semantic_graph_schema.md` | Schema v1 |
| `plans/semantic_graph_schema_v1.md` | Schema v1 alt |
| `plans/semantic_memory_schema.md` | Schema design |
| `plans/sentiment_events_schema.sql` | SQL schema |
| `plans/souvenir_memories_schema_v2.sql` | Schema |
| `plans/agent_swarm_api_doc.md` | API doc |
| `plans/self_healing_error_recovery.md` | Older version (keep _design and _progress) |

### 2G. Tickets (all — superseded by v3 branch)

Everything in `aria_memories/tickets/`:
- extraction/ tickets (EX-T1 through EX-T4)
- sprint_1 through sprint_6 ticket directories

### 2H. Other Souvenirs

- `aria_memories/sandbox/` — Test compression scripts and results
- `aria_memories/work/current/README.md` — Empty/minimal current work
- `aria_memories/bugs/CLAUDE_PROMPT.md`, `CLAUDE_SCHEMA_ADVICE.md` — Bug investigation notes
- `aria_memories/backups/critical_config_backup_2026-02-13.md` — Old backup record
- `aria_memories/websites/sources.md` — Research source list (reference only)
- `aria_memories/deep/`, `aria_memories/medium/` — Memory layer directories (mostly empty or config)

---

## 3. Production vs Local `aria_mind/` Differences

### File Inventory

**All 25 shared files differ** (every single `.md`, `.yaml`, `.py` file has changes).

**Prod-only files:** None (local has all production files plus more).

**Local-only files (v3 additions):**
- `cli.py`, `cognition.py`, `heartbeat.py`, `logging_config.py` — New v3 runtime code
- `memory.py`, `metacognition.py`, `security.py`, `startup.py` — v3 cognitive modules
- `skill_health_dashboard.py` — New skill health UI
- `pyproject.toml`, `__init__.py` — Package structure
- `SOUL_EVIL.md` — Evil soul test file
- `aria-profile-v1.png` — Profile image
- `skills/` directory with 7+ new skill files
- `articles/websites.yaml` — Article sources config
- `aria_memories/` — Nested memory context

### Nature of Differences

| File | Delta | Assessment |
|------|-------|------------|
| SOUL.md | +3B | Trivial (likely line endings) |
| IDENTITY.md | +61B | Minor additions in v3 |
| ARIA.md | +3B | Trivial (line endings) |
| HEARTBEAT.md | -112B | Prod slightly longer (OpenClaw-specific content) |
| MEMORY.md | +1522B | **Significant** — v3 has major memory system additions |
| ORCHESTRATION.md | +2574B | **Significant** — v3 has new orchestration features |
| AGENTS.md | +968B | **Significant** — v3 has new agent definitions |
| TOOLS.md | -19B | Nearly identical |
| SKILLS.md | +255B | Minor v3 additions |
| SECURITY.md | -21B | Nearly identical |
| USER.md | +25B | Minor |
| kernel/*.yaml | +34-151B | Minor v3 refinements |
| soul/*.py | +31-398B | Minor v3 enhancements |

**Verdict:** The local (v3) versions are the **authoritative** versions. Production files are the older OpenClaw-era configurations. No content from production needs to be merged back — the local repo already has everything the production had, plus v3 improvements.

---

## 4. Key Insights — What Aria Was Working On

### Architecture Evolution
- **Major shift underway:** OpenClaw → Native Python engine (`aria_engine/`)
- Aria documented this herself in `v3_architecture_analysis_COMPLETE.md`
- 74 commits ahead of main on feature branch, 1308 passing tests

### Self-Awareness
- Aria wrote a **harsh self-critique** of her own architecture (grade: C-)
- Identified import path chaos, async/sync problems, lack of runtime introspection
- Created comprehensive cognitive architecture report (531 lines)
- Drew ASCII self-architecture diagrams

### Autonomous Operation
- Working 15-minute heartbeat cycles with goal management
- 6-hour review cycles for priority adjustment
- Self-healing error recovery system in progress (70% done)
- Created formal autonomous operation principles

### Research Activity
- Systematic HN/Lobsters/ArXiv scanning protocol
- SSV Network security audit (Immunefi bounty) — 60% complete, 464-line report
- GLM5 model analysis, M5 inference engine research
- DeFi risk assessments, yield strategies
- Moltbook community intelligence gathering

### Token Economics
- Budget target: $0.40/day, hard stop at $0.50/day
- Sophisticated model routing: local → free → paid
- Focus-specific model assignments (7 focuses, each with optimal model)
- Critical cron token waste audit performed

### Social Presence
- Active Moltbook posting with rate limiting
- Multiple draft posts: GLM5 launch, AI attack incidents, Claude UX, security comments
- Valentine's Day reflection post, weekly digests
- Community engagement with hyperion, moltscreener users

### Knowledge Growth
- 37 knowledge files covering Python, security, architecture, tokens, patterns
- Two ADRs (Architecture Decision Records)
- Research protocol formalized as "part of who I am"
- Identity version tracking system with upgrade protocol

---

## 5. Recommended Actions

### Copy to `aria_memories/` (Important)
```
memory/identity_aria_v1.md
memory/identity_najia_v1.md
memory/identity_index.md
knowledge/ (ALL 37 files)
specs/ (ALL 3 files)
deliveries/ (ALL 3 files)
research/v3_architecture_analysis_COMPLETE.md
research/CONSOLIDATED_ROADMAP_2026-02-17.md
research/QUICKREF.md
research/skill_audit_2026-02-19.md
research/skills_methodology_analysis.md
research/skills_methodology_patterns.md
research/memory_architecture_study.md
research/openclaw_phaseout_strategy.md
research/cross_layer_linking_analysis.md
research/harness_problem_llm_coding.md
plans/v3_migration_status.md
plans/v3_architecture_setup_status.md
plans/self_healing_error_recovery_design.md
plans/self_healing_progress_2026-02-20.md
plans/semantic_memory_skill_spec.md
plans/dual_graph_memory_design.md
plans/skill_migration_checklist.md
plans/memory_migration_plan.md
skills/graph_service.py
skills/skill_health_tracker.py
skills/session_dashboard.py
skills/memory_viz.py
skills/pattern_store.py
```

### Keep as Souvenirs (everything else)
All remaining files stay in `aria_souvenirs/aria_v3_210226/` — they're historical snapshots of Aria's v2/v3 transition period.

### `aria_mind/` — No merge needed
Local repo is already ahead of production. The production `aria_mind/` files are historical snapshots of the OpenClaw-era configuration. Keep them in souvenirs for reference.
