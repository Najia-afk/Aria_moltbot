# Repo Cleanup Sprint Plan

## Sprint Objective
Perform a production-safe repository cleanup/refactor sprint under **Strict Production Mode** — removing dead assets, consolidating duplicates, improving documentation coherence, and preserving runtime behavior. All changes are evidence-backed with full auditability.

## Hard Exclusions
- `aria_memories/**` — NO modifications
- `aria_souvenirs/**` — NO modifications

## Mode
**Strict Production Mode** (Section 4.1)

## Assumptions
- Docker stack is the primary runtime (stacks/brain/docker-compose.yml)
- aria-api (FastAPI), aria-web (Flask), aria-engine (Python), litellm are critical services
- Tests run via pytest (in Docker and CI)
- Makefile is the developer entrypoint for common tasks
- CI runs via `.github/workflows/test.yml` and `.github/workflows/tests.yml`

## Current Unknowns
- Whether `Dockerfile.test` was ever used (not wired to CI/Makefile) — DEFER
- Whether `.semgrep.yml` will be wired to CI (S-158 planned but not implemented) — DEFER
- Whether `prompts/system_prompt.txt` content is still relevant — DEFER

---

## Epics

### Epic 1: Wave 1 — Safe Prune (P1)
High-confidence deletions of orphaned/stale files. Zero runtime risk.

| Story | Title | Priority | Status |
|-------|-------|----------|--------|
| S-01 | Delete orphaned scripts (16 files) | P1 | Not Started |
| S-02 | Delete stale root-level audit/snapshot docs (6 files + 1 JSON) | P1 | Not Started |
| S-03 | Delete duplicate docs/architecture.md | P1 | Not Started |
| S-04 | Delete stale docs/API_AUDIT_REPORT.md | P1 | Not Started |
| S-05 | Delete articles/ directory (3 files, dupes/archival) | P1 | Not Started |
| S-06 | Delete superseded prompts/PO_MEGA_REPO_CLEANUP_PROMPT.md | P1 | Not Started |
| S-07 | Fix Makefile ghost reference (verify_pairing.sh) | P1 | Not Started |

### Epic 2: Wave 2 — Structural Refactor (P2)
Move misplaced files, consolidate references.

| Story | Title | Priority | Status |
|-------|-------|----------|--------|
| S-08 | Move API_ENDPOINT_INVENTORY.md to docs/ | P2 | Not Started |
| S-09 | Move DATA_MIGRATION_REPORT.md to docs/archive/ | P2 | Not Started |
| S-10 | Fix SKILLS.md link: docs/architecture.md → ARCHITECTURE.md | P2 | Not Started |
| S-11 | Deduplicate CI workflows (test.yml vs tests.yml) | P2 | Not Started |

### Epic 3: Wave 3 — Stability Validation (P2)
Run smoke checks and validate no regressions.

| Story | Title | Priority | Status |
|-------|-------|----------|--------|
| S-12 | Run endpoint matrix generation | P2 | Not Started |
| S-13 | Run runtime smoke check | P2 | Not Started |
| S-14 | Run pytest suite (local) | P2 | Not Started |

### Epic 4: Wave 4 — Documentation Truth-Sync (P3)
Ensure docs reflect reality.

| Story | Title | Priority | Status |
|-------|-------|----------|--------|
| S-15 | Update STRUCTURE.md to reflect file removals | P3 | Not Started |
| S-16 | Update README.md doc table (add missing doc links) | P3 | Not Started |

---

## Wave Plan

| Wave | Scope | Risk Ceiling | Validation Gate | Exit Condition |
|------|-------|--------------|-----------------|----------------|
| 1 | Safe prune (scripts, docs, articles) | Low | `generate_endpoint_matrix.py` passes, no import errors | No regression in touched scope |
| 2 | Structural refactor (file moves, link fixes) | Low-Medium | Cross-reference integrity | Behavior parity maintained |
| 3 | Stability validation | Medium | smoke + pytest pass | Critical paths green |
| 4 | Docs truth-sync | Low | Manual doc link check | No contradictions in core docs |

---

## Status Timeline

| Date | Event |
|------|-------|
| 2026-02-26 | Sprint initiated, inventory complete |
| 2026-02-26 | Wave 1 execution |
| 2026-02-26 | Wave 2 execution |
| 2026-02-26 | Wave 3 validation |
| 2026-02-26 | Wave 4 docs sync |
| 2026-02-26 | GO/NO-GO decision |
