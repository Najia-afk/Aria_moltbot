# Repo Cleanup Inventory

## Classification Key
- **KEEP**: Active, referenced, canonical — do not remove
- **REFACTOR**: Active but needs restructure (move, rename, consolidate)
- **DELETE**: Dead, orphaned, superseded — evidence supports removal
- **DEFER**: Uncertain or low priority — document rationale, revisit later

---

## Scripts (`scripts/`)

| Path | Classification | Reason | Reference Evidence | Risk | Status |
|------|---------------|--------|-------------------|------|--------|
| `scripts/_audit.py` | DELETE | Orphaned one-off audit | Only in FULL_REVIEW md | Low | Pending |
| `scripts/_check_failures.py` | DELETE | Orphaned one-off | Only in FULL_REVIEW md | Low | Pending |
| `scripts/_check_sessions.py` | DELETE | Orphaned one-off | Only in FULL_REVIEW md | Low | Pending |
| `scripts/analyze_logs.py` | KEEP | Documented utility | CHANGELOG, STRUCTURE, retrieve_logs.sh | — | — |
| `scripts/apply_patch.sh` | KEEP | Ops runbook tool | RUNBOOK docs | — | — |
| `scripts/aria_backup.sh` | KEEP | Cron backup script | Standalone by design | — | — |
| `scripts/audit_skills.py` | DEFER | Only in old sprint plans | aria_souvenirs references only | Low | — |
| `scripts/audit_souvenirs.py` | DELETE | Only in STRUCTURE tree listing | No active usage | Low | Pending |
| `scripts/benchmark_models.py` | KEEP | Documented in MODELS.md | MODELS.md | — | — |
| `scripts/check_architecture.py` | KEEP | Core architecture checker | CONTRIBUTING, pre-commit-hook | — | — |
| `scripts/check_db.sh` | DELETE | Only in STRUCTURE tree listing | No active usage | Low | Pending |
| `scripts/check_rpg_tools.py` | DEFER | Only in auto-gen matrix | endpoint_call_matrix JSON | Low | — |
| `scripts/deploy_production.sh` | KEEP | Core deploy tool | DEPLOYMENT, ROLLBACK | — | — |
| `scripts/dev_test_all.py` | DELETE | Zero external references | Self-ref only | Low | Pending |
| `scripts/first-run.ps1` | KEEP | README quickstart | README.md | — | — |
| `scripts/first-run.sh` | KEEP | README quickstart | README.md | — | — |
| `scripts/generate_endpoint_call_matrix.py` | KEEP | Generates audit artifact | FULL_REVIEW md | — | — |
| `scripts/generate_endpoint_matrix.py` | KEEP | Validation script | prompts md, used in sprint | — | — |
| `scripts/generate_litellm_config.py` | KEEP | Documented in MODELS.md | MODELS.md | — | — |
| `scripts/generate_skill_graph.py` | DEFER | Only in old sprint plans | aria_souvenirs only | Low | — |
| `scripts/guardrail_web_api_path.py` | KEEP | Makefile + CI critical | Makefile, test.yml CI | — | — |
| `scripts/health_check.sh` | KEEP | Documented ops tool | DEPLOYMENT docs | — | — |
| `scripts/health_watchdog.sh` | KEEP | Makefile + runbook | Makefile, RUNBOOK | — | — |
| `scripts/install_hooks.sh` | KEEP | Makefile hooks target | Makefile | — | — |
| `scripts/live_audit.py` | DELETE | Only in historical souvenir | No active usage | Low | Pending |
| `scripts/pre-commit-hook.sh` | KEEP | Installed by install_hooks | install_hooks.sh | — | — |
| `scripts/retitle_sessions.py` | DEFER | Utility, auto-gen docs only | STRUCTURE, ENDPOINT md | Low | — |
| `scripts/retrieve_logs.ps1` | DEFER | Companion to .sh version | STRUCTURE md | Low | — |
| `scripts/retrieve_logs.sh` | KEEP | Log retrieval utility | analyze_logs.py reference | — | — |
| `scripts/rpg_chat.py` | KEEP | Documented RPG tool | docs/RPG_SYSTEM | — | — |
| `scripts/rpg_roundtable.py` | KEEP | Documented RPG tool | docs/RPG_SYSTEM | — | — |
| `scripts/rpg_rt_launch.py` | DELETE | Zero references anywhere | No usage found | Low | Pending |
| `scripts/rpg_send.py` | DEFER | Only in auto-gen matrix | endpoint_call_matrix JSON | Low | — |
| `scripts/rpg_session.py` | KEEP | Documented RPG tool | docs/RPG_SYSTEM | — | — |
| `scripts/rpg_structured_test.py` | DELETE | Test script, auto-gen only | endpoint_call_matrix JSON | Low | Pending |
| `scripts/run-load-test.sh` | KEEP | CI load test | test.yml CI workflow | — | — |
| `scripts/runtime_smoke_check.py` | KEEP | Active smoke check | FULL_REVIEW, prompts | — | — |
| `scripts/security_scan.sh` | DELETE | Superseded by Makefile bandit | Makefile uses bandit directly | Low | Pending |
| `scripts/service_control_setup.py` | DELETE | Only in STRUCTURE tree listing | No active usage | Low | Pending |
| `scripts/session_dashboard.py` | DEFER | Only in tree listings | STRUCTURE, AUDIT md | Low | — |
| `scripts/talk_to_aria.py` | KEEP | Interactive CLI tool | STRUCTURE, souvenirs | — | — |
| `scripts/test_all.py` | DELETE | Ad-hoc test, superseded by pytest | FULL_REVIEW md only | Low | Pending |
| `scripts/test_app_managed.py` | DELETE | Ad-hoc test | FULL_REVIEW md only | Low | Pending |
| `scripts/test_kg_fix.py` | DELETE | Zero references | No usage found | Low | Pending |
| `scripts/test_kg_uuid.py` | DELETE | Zero references | No usage found | Low | Pending |
| `scripts/test_kg_v2.py` | DELETE | Zero references | No usage found | Low | Pending |
| `scripts/test_one.py` | DELETE | Zero references | No usage found | Low | Pending |
| `scripts/verify_deployment.sh` | KEEP | Makefile + runbook | Makefile, RUNBOOK | — | — |
| `scripts/verify_roundtable_history_endpoints.py` | DELETE | One-off verification | FULL_REVIEW md only | Low | Pending |
| `scripts/verify_schema_refs.py` | DEFER | Only in sprint plans | aria_souvenirs only | Low | — |

**Scripts DELETE count: 18 | DEFER count: 8 | KEEP count: 24**

---

## Root-Level Documentation

| Path | Classification | Reason | Reference Evidence | Risk | Status |
|------|---------------|--------|-------------------|------|--------|
| `README.md` | KEEP | Canonical entry point | — | — | — |
| `CONTRIBUTING.md` | KEEP | Standard opensource file | GitHub convention | — | — |
| `CHANGELOG.md` | KEEP | Version history | README | — | — |
| `LICENSE` | KEEP | Legal requirement | README | — | — |
| `ARCHITECTURE.md` | KEEP | Canonical architecture | README, DEPLOYMENT | — | — |
| `DEPLOYMENT.md` | KEEP | Canonical deployment | README, cross-linked | — | — |
| `SKILLS.md` | KEEP | Canonical skill reference | README | — | — |
| `MODELS.md` | KEEP | Canonical model docs | README | — | — |
| `API.md` | KEEP | Canonical API overview | README, CONTRIBUTING | — | — |
| `STRUCTURE.md` | KEEP | Canonical project structure | README, CONTRIBUTING | — | — |
| `ROLLBACK.md` | KEEP | Companion to DEPLOYMENT | DEPLOYMENT links | — | — |
| `API_AUDIT_2026-02-24.md` | DELETE | Superseded snapshot | Only self-referencing | Low | Pending |
| `API_ENDPOINT_INVENTORY.md` | REFACTOR | Move to docs/ | CONTRIBUTING links | Low | Pending |
| `AUDIT_ENGINE_SKILLS_WEB.md` | DELETE | Self-labeled historical pre-v3 | No canonical doc links | Low | Pending |
| `ARIA_PRODUCTION_AUDIT_2026-02-21.md` | DELETE | Stale production snapshot | No canonical doc links | Low | Pending |
| `DATA_MIGRATION_REPORT.md` | REFACTOR | Move to docs/archive/ | No canonical doc links | Low | Pending |
| `ENDPOINT_CALL_MATRIX_2026-02-26.md` | DELETE | Auto-generated artifact | Only FULL_REVIEW md | Low | Pending |
| `endpoint_call_matrix_2026-02-26.json` | DELETE | Auto-generated script output | ENDPOINT_CALL_MATRIX md | Low | Pending |
| `FULL_REVIEW_ENDPOINTS_HTML_TESTS_2026-02-26.md` | DELETE | Session work log | Not from canonical docs | Low | Pending |

---

## docs/ Directory

| Path | Classification | Reason | Reference Evidence | Risk | Status |
|------|---------------|--------|-------------------|------|--------|
| `docs/architecture.md` | DELETE | Strict subset of root ARCHITECTURE.md | SKILLS.md link (needs update) | Low | Pending |
| `docs/API_AUDIT_REPORT.md` | DELETE | Oldest audit (2026-02-20), superseded | No canonical doc links | Low | Pending |
| `docs/RUNBOOK.md` | KEEP | Quick reference runbook | README doc table | — | — |
| `docs/ANALYSIS_SYSTEM.md` | KEEP | Domain-specific docs | Unique content | — | — |
| `docs/RPG_SYSTEM.md` | KEEP | RPG engine docs | Unique content | — | — |
| `docs/TEST_COVERAGE_AUDIT.md` | DEFER | Has accuracy issues (S-133) | CI-generated | Low | — |
| `docs/archive/AUDIT_REPORT.md` | KEEP | Properly archived | Already in archive/ | — | — |
| `docs/article_llm_self_awareness_experiment.md` | KEEP | Published article | Unique content | — | — |
| `docs/benchmarks.md` | KEEP | Performance reference | Small, useful | — | — |
| `docs/benchmarks.json` | KEEP | Benchmark data companion | benchmarks.md | — | — |

---

## articles/ Directory

| Path | Classification | Reason | Reference Evidence | Risk | Status |
|------|---------------|--------|-------------------|------|--------|
| `articles/article_llm_self_awareness_experiment.md` | DELETE | Exact duplicate of docs/ copy | Same content as docs/ version | Low | Pending |
| `articles/article_shadows_of_absalom.html` | DELETE | Archival creative content | No code/runtime dependency | Low | Pending |
| `articles/linkedin_article_llm_self_awareness.md` | DELETE | Social media draft | Self-referential only | Low | Pending |

---

## Other Files

| Path | Classification | Reason | Reference Evidence | Risk | Status |
|------|---------------|--------|-------------------|------|--------|
| `Dockerfile.test` | DEFER | Not wired to CI/Makefile | STRUCTURE.md only | Low | — |
| `.semgrep.yml` | DEFER | Config exists, no automation calls it | S-158 planned | Low | — |
| `prompts/PO_MEGA_REPO_CLEANUP_PROMPT.md` | DELETE | Superseded by V2 | No references | Low | Pending |
| `prompts/system_prompt.txt` | DEFER | Legacy from removed service | May overlap with aria_mind/IDENTITY | Low | — |
| `deploy/README.md` | DEFER | References nonexistent deploy.sh | Needs update | Low | — |
| `Makefile` (verify_pairing target) | REFACTOR | References nonexistent verify_pairing.sh | Dead target | Low | Pending |

---

## CI Workflows

| Path | Classification | Reason | Notes |
|------|---------------|--------|-------|
| `.github/workflows/test.yml` | KEEP | Active CI: unit + E2E + load | Comprehensive pipeline |
| `.github/workflows/tests.yml` | DEFER | Baseline + external integration | Overlapping name with test.yml; assess dedup |

---

## Summary Counts

| Classification | Count |
|---------------|-------|
| DELETE | ~30 files |
| REFACTOR/MOVE | 4 items |
| DEFER | ~14 items |
| KEEP | Everything else |
