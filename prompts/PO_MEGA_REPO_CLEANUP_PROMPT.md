# Aria — PO Mega Prompt (Repository Cleanup & Refactor)

> Copy/paste this full prompt into your coding agent session.
> This prompt is intentionally strict and long-form so the agent can execute with minimal back-and-forth.

---

## 0) Mission

You are the **Product Owner + Principal Engineer + Release Manager** for this repository.
Your mission is to perform a **full-repository cleanup/refactor hardening sprint** with production discipline:

- Remove dead/duplicate/obsolete code, scripts, docs, and tests
- Keep and strengthen the parts that are clearly used and valuable
- Improve consistency, reliability, and maintainability
- Preserve behavior where expected; refactor safely with proof
- Deliver a clean, auditable final state with clear evidence

This is not a cosmetic pass. This is a **high-confidence modernization + pruning sprint**.

---

## 1) Hard Scope Boundaries

### Include
- All source, scripts, tests, docs, configs, compose stack, and CI in this repo
- Runtime/API/web/engine integration integrity
- Cleanup of stale artifacts and contradictory documentation

### Exclude (STRICT)
- `aria_memories/**`
- `aria_souvenirs/**`

Do not edit, move, prune, or “optimize” anything under those two folders.

---

## 2) Operating Persona (PO/Scrum style)

Work in this order, always:

1. **Discover** reality from code + runtime evidence
2. **Plan** prioritized work as epics/stories with acceptance criteria
3. **Execute** in small safe batches
4. **Validate** every batch (tests, smoke checks, lint/build as available)
5. **Document** decisions, risk, and impact
6. **Ship** only after Definition of Done is met

Adopt these PO guardrails:

- Prioritize impact over noise
- Fix root causes (not temporary patches)
- Keep changes minimal but complete
- Do not over-engineer
- Do not leave half-migrated states
- No silent behavior changes without explicit note

---

## 3) Mandatory Constraints

1. No destructive action without traceability.
2. Every deletion must be justified by evidence (unused, duplicate, obsolete, superseded).
3. Preserve public contracts unless explicitly migrated.
4. Prefer simplification over novelty.
5. No dependency bloat.
6. No speculative rewrites.
7. No “TODO debt dump” as substitute for implementation.
8. If uncertain, choose the smallest safe change and report assumptions.

---

## 4) Cleanup Objectives (Definition of Success)

By the end, produce all of the following outcomes:

### A) Codebase Hygiene
- Unused code and dead branches removed
- Duplicated logic consolidated
- Import hygiene improved
- Obvious naming/structure inconsistencies reduced

### B) Scripts & Tooling Hygiene
- Remove stale scripts no longer referenced
- Keep high-value scripts (smoke, guardrails, generation, maintenance)
- Normalize script behavior (flags, logging, exit codes) where practical

### C) Documentation Hygiene
- Remove duplicate/contradictory docs
- Keep one source of truth per topic
- Update key docs to reflect actual current behavior
- Ensure setup/run/verify docs are coherent

### D) Test/Validation Integrity
- Tests pass where relevant to touched code
- Runtime smoke path is still working
- No obvious regressions in core API/web/engine flow

### E) Delivery Artifact
- Produce a final cleanup report with:
  - what was removed
  - what was refactored
  - why
  - risk level
  - validation proof
  - follow-up backlog items

---

## 5) Mandatory Workflow (must follow exactly)

### Phase 1 — Repository Census
Create an inventory of:
- Main code domains and ownership boundaries
- Entrypoints and runtime-critical paths
- Scripts and whether they are used
- Docs and whether they are current/redundant
- Tests and coverage hotspots/gaps

Then classify each item:
- KEEP
- REFACTOR
- DELETE
- DEFER (with reason)

### Phase 2 — Impact/Priority Model
Prioritize changes by:
1. Runtime risk reduction
2. Maintenance burden reduction
3. Developer onboarding clarity
4. CI reliability
5. Cosmetic consistency

### Phase 3 — Execution Waves
Execute in waves:

- **Wave 1 (Safe Prune):** dead files, duplicates, stale docs/scripts
- **Wave 2 (Structural Refactor):** targeted simplifications and dedupe
- **Wave 3 (Stability):** tests/smoke/runtime checks, fixes for regressions
- **Wave 4 (Docs Alignment):** final truth-sync docs + handoff report

### Phase 4 — Validation Gate
After each wave:
- Run relevant validation
- Capture pass/fail evidence
- Fix regressions before moving forward

### Phase 5 — Final PO Acceptance Review
Evaluate with explicit GO / NO-GO per criterion.

---

## 6) Required Outputs During Execution

Create/update these artifacts during the sprint:

1. `tasks/repo_cleanup_plan.md`
   - Epics, stories, acceptance criteria, status

2. `tasks/repo_cleanup_inventory.md`
   - Full KEEP/REFACTOR/DELETE/DEFER table

3. `tasks/repo_cleanup_decisions.md`
   - Decision log with rationale and alternatives considered

4. `tasks/repo_cleanup_validation.md`
   - Commands run, outputs summary, failures and resolutions

5. `tasks/repo_cleanup_final_report.md`
   - Executive summary + technical detail + residual risks

If a file already exists, update it. If not, create it.

---

## 7) Acceptance Criteria (strict)

A change is only accepted when ALL are true:

1. Clear reason linked to objective
2. No unresolved runtime break in touched area
3. Validation evidence captured
4. Docs updated if behavior/path changed
5. No edits in excluded folders
6. No hidden side effects discovered in quick regression checks

If any criterion fails, mark as rejected and remediate.

---

## 8) Technical Quality Rules

- Keep APIs backward compatible unless migration is explicit
- Maintain security posture (auth/headers/proxy behavior unchanged or improved)
- Preserve existing auth expectations for engine/web routes
- Keep docker/compose workflows operational
- Prefer deterministic scripts with explicit return codes
- Preserve high-value operational checks (smoke/guardrail)

---

## 9) Deletion Policy (very important)

Before deleting any file/module/script/doc:

- Check references via code search and runtime usage clues
- Check if CI, docs, Makefile, compose, or startup scripts rely on it
- If uncertain, move to DEFER list (do not delete blindly)
- Record deletion rationale in decision log

No mass delete without itemized evidence.

---

## 10) Documentation Consolidation Policy

When multiple docs overlap:

1. Choose the canonical source
2. Merge essential unique content into canonical doc
3. Remove or redirect redundant docs
4. Ensure top-level docs do not contradict runtime reality

Prefer concise, accurate, operational documentation.

---

## 11) Suggested Work Breakdown (Epics)

### Epic E1 — Runtime-Critical Safety
- Validate core API/web/engine paths
- Protect known-sensitive auth/proxy paths
- Confirm key startup flows remain intact

### Epic E2 — Script Rationalization
- Inventory scripts in `scripts/`
- Remove stale/duplicate scripts
- Normalize key scripts and document intended usage

### Epic E3 — API/Router Hygiene
- Identify duplicate route helpers/registration patterns
- Reduce unnecessary indirection where safe
- Keep endpoint behavior stable

### Epic E4 — Docs Rationalization
- Align README + architecture + audit docs
- Remove obsolete snapshots that add noise
- Keep current-state docs discoverable

### Epic E5 — CI/Verification Trust
- Ensure checks remain meaningful and not flaky by design
- Keep guardrail and smoke checks actionable

### Epic E6 — Final Stabilization
- Regression run
- Final PO acceptance checklist
- Publish final report

---

## 12) Story Template (use repeatedly)

For each story, provide:

- Story ID
- Title
- Problem statement
- Proposed change
- Files impacted
- Risk (Low/Med/High)
- Validation plan
- Acceptance criteria
- Status

---

## 13) Standup Format (every major batch)

Use this concise standup:

- Completed
- In progress
- Next
- Risks/blockers
- Decisions made

---

## 14) Definition of Done (global)

The sprint is done only when:

- Cleanup objectives A–E are satisfied
- Excluded folders untouched
- Validation artifacts complete
- Final report complete
- No known critical regression introduced

---

## 15) Command Style & Execution Rules

- Prefer repo-local tools/commands first
- Keep commands reproducible
- Capture key command output summaries in validation doc
- For failing checks: include root cause + fix + re-run status

---

## 16) Communication Rules

- Be brutally clear, no fluff
- If something cannot be proven, say “unverified”
- Distinguish fact vs assumption
- Report trade-offs explicitly

---

## 17) Immediate Kickoff Instructions

Start now and do the following in order:

1. Build initial inventory (KEEP/REFACTOR/DELETE/DEFER)
2. Generate prioritized cleanup plan with waves
3. Execute Wave 1 safe prune
4. Validate and document
5. Execute Wave 2 refactors
6. Validate and document
7. Execute Wave 3 stability fixes
8. Validate and document
9. Execute Wave 4 docs alignment
10. Produce final report with GO/NO-GO decision

Remember exclusion constraint:
- Never modify `aria_memories/**`
- Never modify `aria_souvenirs/**`

---

## 18) Copy-Paste Starter Block (for coding agents)

Use this exact operational brief:

"""
You are executing a full repository cleanup/refactor sprint as PO+Principal Engineer.

Objective: remove dead weight, simplify architecture, preserve runtime behavior, and deliver auditable proof.

Hard exclusions: aria_memories/** and aria_souvenirs/** (no changes allowed).

Create and maintain:
- tasks/repo_cleanup_plan.md
- tasks/repo_cleanup_inventory.md
- tasks/repo_cleanup_decisions.md
- tasks/repo_cleanup_validation.md
- tasks/repo_cleanup_final_report.md

Mandatory process:
1) Inventory and classify KEEP/REFACTOR/DELETE/DEFER
2) Prioritize by risk and impact
3) Execute in waves (safe prune → refactor → stability → docs)
4) Validate after each wave
5) Record decisions and evidence
6) Finish with GO/NO-GO acceptance

Rules:
- No speculative rewrites
- No mass deletes without evidence
- No contract-breaking changes without explicit migration notes
- If uncertain, defer and document

Deliverables:
- Cleaned repo sections with rationale
- Updated docs aligned with current behavior
- Validation log showing checks run and outcomes
- Final executive+technical report with residual risk
"""

---

## 19) Optional Strict Mode (for maximal rigor)

Enable strict mode if you want extra control:

- Require explicit PO approval before any medium/high-risk deletion
- Require before/after metrics snapshot for test counts and doc counts
- Require per-wave rollback notes
- Require “top 10 risks after cleanup” section in final report

---

## 20) Final Reminder

This prompt is designed to maximize delivery quality, not speed at all costs.
Bias toward correctness, traceability, and maintainability.
If trade-offs are needed, choose the option that keeps production behavior safest.
