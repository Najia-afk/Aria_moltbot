# S-59: Archive Prototypes Folder
**Epic:** E10 — Prototypes Integration | **Priority:** P2 | **Points:** 1 | **Phase:** 3

## Problem

`aria_mind/prototypes/` contains 6 Python prototype files and 7 markdown docs that were
written on 2026-02-16 as research/proof-of-concept work. All implementations have since
been productionised into `aria_skills/`:

| Prototype | Target Skill | Status |
|-----------|-------------|--------|
| `session_protection_fix.py` | `aria_skills/session_manager/` | ✅ Implemented (lines 243-256) |
| `memory_compression.py` | `aria_skills/memory_compression/` | ✅ Implemented (516 lines) |
| `sentiment_analysis.py` | `aria_skills/sentiment_analysis/` | ✅ Implemented (962 lines) |
| `pattern_recognition.py` | `aria_skills/pattern_recognition/` | ✅ Implemented |
| `embedding_memory.py` | pgvector via api_client | ✅ STOPPED (reinvents existing pgvector) |
| `advanced_memory_skill.py` | N/A | ✅ STOPPED (broken imports, superseded) |

The prototypes folder creates cognitive load — agents reading `aria_mind/` see both the
prototype and the production skill, causing confusion about the canonical implementation.

## Root Cause

No archival step was planned in the original 2026-02-16 sprint to move prototypes once
implemented. They remain in the active workspace.

## Fix

Move `aria_mind/prototypes/` to `aria_souvenirs/prototypes_160226/` (the established
pattern for archiving Aria evolution artifacts, matching `aria_souvenirs/aria_v2_180226/`
and `aria_souvenirs/aria_v2_160226/`).

```bash
# In repository root
mv aria_mind/prototypes aria_souvenirs/prototypes_160226
```

Update `aria_mind/README.md` (or `ARCHITECTURE.md`) to note the prototypes were archived.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Not a code change |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | N/A |
| 4 | Docker-first testing | ✅ | Docker uses `aria_mind/` — no reference to prototypes/ in any Dockerfile |
| 5 | aria_memories only writable path | ❌ | Moving within workspace, not Aria writing |
| 6 | No soul modification | ✅ | prototypes/ is not soul/ — safe to move |

## Dependencies

None. Independent of all other tickets.

## Verification

```bash
# 1. Prototypes no longer in aria_mind/
ls aria_mind/prototypes 2>&1
# EXPECTED: ls: cannot access 'aria_mind/prototypes': No such file or directory

# 2. Prototypes exist in aria_souvenirs/
ls aria_souvenirs/prototypes_160226/
# EXPECTED: listing of all 6 .py files and 7 .md files

# 3. No Docker or production code references prototypes/ directly
grep -r "prototypes" Dockerfile docker-compose.yaml aria_engine/ src/ aria_skills/ 2>/dev/null
# EXPECTED: no matches (or only comments/docs)

# 4. Git status clean after move
git status
# EXPECTED: renamed: aria_mind/prototypes/* -> aria_souvenirs/prototypes_160226/*
```

## Prompt for Agent

**Context:** The `aria_mind/prototypes/` folder contains historical prototype code from
2026-02-16. All implementations are now in `aria_skills/`. Archive to `aria_souvenirs/`.

**Steps:**
1. Run: `mv aria_mind/prototypes aria_souvenirs/prototypes_160226`
2. Verify: `ls aria_souvenirs/prototypes_160226/` shows all files
3. Verify: `ls aria_mind/prototypes` returns "No such file or directory"
4. Run: `grep -r "aria_mind/prototypes" --include="*.py" --include="*.yaml" --include="*.md" . | head -20`
   — If any references found (other than docs), update them to point to `aria_souvenirs/prototypes_160226/`
5. `git add -A && git commit -m "archive: move prototypes/ to aria_souvenirs/prototypes_160226"`

**Constraints:** This is a pure file move. No code changes required unless references are found.
