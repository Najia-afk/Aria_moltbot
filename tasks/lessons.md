# Lessons

## General
- Do not use SSH or remote commands unless explicitly requested; prefer local scripts that the user can run on the server.
- Avoid writing secrets or tokens into repo files; prompt for them at runtime or keep them unset by default.
- When refactoring skills, verify file content after edits to avoid duplicated blocks and syntax errors; re-read the file before running tests.

## Sprint Planning (v1.2 — 2026-02-10)
- **Read EVERYTHING before acting.** Full codebase read (200+ files) via parallel subagents is the fastest way. Never plan from summary alone.
- **Parallel subagents work well** for codebase ingestion. 6 subagents reading different directories simultaneously gives full context in minutes.
- **Filename consistency matters.** When a master index references ticket filenames, verify the actual filenames on disk match. Found 5 mismatches in first pass.
- **Dependencies between tickets must be explicit.** If S-17 reads fields that S-16 creates, that's a dependency — write it on the ticket header. Found 8 undocumented dependencies in first cross-review.
- **Watch for ticket overlaps.** S-10/S-11 (both touching DB credentials) and S-13/S-15 (both touching six_hour_review) had overlapping scope. Add cross-reference notes defining ownership boundaries.
- **Epic priority ≠ ticket priority.** An E2 (P0) epic can contain P2 tickets. Note this in sprint overview to avoid confusion during execution.
- **Verification sections are mandatory.** 20/35 tickets were created without explicit verification steps. Every ticket needs testable commands.
- **PO/Scrum prompt lives in prompts/.** Reusable sprint prompt template at `prompts/PO_SCRUM_SPRINT.md` — copy-paste to start any sprint session.

## Architecture
- **5-layer rule:** DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA. No exceptions.
- **9 skills bypass api_client** as of v1.1 — must be migrated (S-08).
- **models.yaml is single source of truth.** Found 3 places with hardcoded model names (S-09).
- **aria_memories/ is the ONLY writable path** for Aria. Code directories are read-only.
- **Container mounts matter.** Verify docker-compose volumes mount aria_memories as rw before assuming file writes work.

## Bugs & Patterns
- **import os missing** in input_guard — always check imports after refactoring.
- **SkillConfig.settings is a dict**, not an object with attributes. Use `config.settings.get()` not `config.settings.attr`.
- **Cron 6-field vs 5-field format** caused massive over-firing. Always validate cron expressions.
- **Empty registries from constructors:** `PipelineExecutor(SkillRegistry())` creates a fresh empty registry instead of using the shared one. Pass the existing registry instance.

## Sprint v1.2 Execution (2025)
- **Swarm execution works.** 44 tickets across 9 epics completed autonomously via parallel subagent dispatch. Tickets grouped into dependency waves avoid blocking.
- **Deprecated code removal (S-18) must happen before init cleanup (S-19).** Removing imports of deleted skills first prevents ImportError cascades.
- **Duplicate index=True + standalone Index() is common.** S-36 found 3 instances. Always check before adding standalone indexes whether inline `index=True` exists.
- **Raw SQL→ORM migration requires reading actual code first.** Ticket diffs may reference stale line numbers. Always read-then-edit.
- **Frontend tickets are independent once routes exist.** S-39/S-40/S-41 ran in parallel with zero conflicts because they touch separate templates and routes.
- **ForeignKey constraints need orphan cleanup first.** S-42 migration DELETEs orphan rows before adding FK to avoid constraint violations on existing data.
- **GIN indexes require pg_trgm extension.** Must `CREATE EXTENSION IF NOT EXISTS pg_trgm` before creating trigram indexes (S-44).
- **Brain→API communication via shared DB table.** SkillStatusRecord pattern (S-40) — brain writes, API reads — is the correct cross-container data sharing approach.
- **AA+ ticket format with Constraints table is essential.** Tickets without explicit constraint evaluation led to architecture violations in v1.1. The full template (Problem, Root Cause, Fix, Constraints, Dependencies, Verification, Prompt) is now the standard.
- **Gateway abstraction (S-31) enables future LLM provider swaps.** GatewayInterface ABC + OpenClawGateway isolates vendor-specific logic.
