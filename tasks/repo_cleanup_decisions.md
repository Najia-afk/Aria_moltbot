# Repo Cleanup Decisions Log

## Decision Format
Each decision includes: ID, Context, Chosen Action, Alternatives Considered, Consequences.

---

## DEC-001: Mode Selection
- **Context**: Three modes available (Strict, Aggressive, Conservative)
- **Chosen Action**: Strict Production Mode
- **Alternatives**: Aggressive (more deletions, less review), Conservative (minimal changes)
- **Consequences**: Methodical approach with full evidence gates; slightly slower but production-safe

## DEC-002: Orphaned Scripts Deletion Strategy
- **Context**: 18 scripts identified with zero or near-zero external references
- **Chosen Action**: Delete in a single batch (Wave 1), since all are Low risk and share the same evidence pattern
- **Alternatives**: Delete one-by-one with individual validation; Defer all to next sprint
- **Consequences**: Significant noise reduction in scripts/; must verify none are imported by tests

## DEC-003: Historical Audit Docs
- **Context**: 6 timestamped audit/review docs at root level (2026-02-20 through 2026-02-26), totaling ~2500 lines
- **Chosen Action**: Delete all — they are point-in-time snapshots superseded by current canonical docs
- **Alternatives**: Move to docs/archive/; Keep as historical record
- **Consequences**: Root directory decluttered; any unrealized findings should be captured as issues before deletion

## DEC-004: docs/architecture.md vs ARCHITECTURE.md
- **Context**: docs/architecture.md (125 lines) is a strict subset of root ARCHITECTURE.md (300 lines)
- **Chosen Action**: Delete docs/architecture.md, update SKILLS.md link to point to root ARCHITECTURE.md
- **Alternatives**: Keep both; merge any unique content
- **Consequences**: Single canonical architecture doc; one link needs updating in SKILLS.md

## DEC-005: articles/ Directory
- **Context**: 3 files — 1 exact duplicate of docs/ copy, 1 HTML creative content, 1 LinkedIn draft
- **Chosen Action**: Delete entire articles/ directory
- **Alternatives**: Move to aria_souvenirs/; Keep as creative archive
- **Consequences**: Root decluttered; creative content can be re-added to aria_souvenirs if desired

## DEC-006: API_ENDPOINT_INVENTORY.md Location
- **Context**: 628-line endpoint reference at root, should be in docs/
- **Chosen Action**: Move to docs/API_ENDPOINT_INVENTORY.md, update CONTRIBUTING.md reference
- **Alternatives**: Keep at root; merge into API.md
- **Consequences**: Cleaner root; minor cross-ref update needed

## DEC-007: DATA_MIGRATION_REPORT.md
- **Context**: One-time v3→v4 migration report at root, 337 lines
- **Chosen Action**: Move to docs/archive/DATA_MIGRATION_REPORT.md
- **Alternatives**: Delete entirely; keep at root
- **Consequences**: Historical record preserved in appropriate location

## DEC-008: Makefile Ghost Target
- **Context**: `verify-pairing` target references `./scripts/verify_pairing.sh` which doesn't exist
- **Chosen Action**: Remove the dead Makefile target
- **Alternatives**: Create the missing script; comment out the target
- **Consequences**: Makefile only references existing files

## DEC-009: CI Workflow Deduplication
- **Context**: Two CI files with overlapping names: `test.yml` (unit+E2E+load) and `tests.yml` (baseline+external)
- **Chosen Action**: DEFER — both serve different purposes despite similar names
- **Alternatives**: Merge into single workflow; rename for clarity
- **Consequences**: No change in this sprint; add to follow-up backlog
