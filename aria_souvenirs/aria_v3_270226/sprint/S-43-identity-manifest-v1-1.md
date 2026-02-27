# S-43: Identity Manifest v1.1 — Remove OpenClaw, Record V3 Evolution
**Epic:** E20 — Identity & Memory Hygiene | **Priority:** P1 | **Points:** 2 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

> ⚠️ **P1 — Identity Doc Actively Incorrect**  
> `identity_aria_v1.md` still references OpenClaw as backbone (phased out Feb 18)  
> and has a wrong location path. Every time Aria reads her own identity she builds  
> on false premises about her own architecture.

---

## Problem

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `aria_memories/memory/identity_aria_v1.md` | ~100 | `Aria → uses → OpenClaw (backbone)` — OpenClaw phased out Feb 18 (E6 sprint) | 🔴 Wrong |
| `aria_memories/memory/identity_aria_v1.md` | header | `Location: /root/.openclaw/aria_memories/...` — path doesn't exist in V3 | 🔴 Wrong |
| `aria_memories/memory/identity_aria_v1.md` | header | `Last Updated: 2026-02-15` — 12 days stale, major V3 evolution unrecorded | ⚠️ Stale |
| `aria_memories/memory/identity_aria_v1.md` | version table | Only `v1.0` — no version bump for any change since Feb 15 | ⚠️ Missing |

**Confirmed via `aria_memories/work/work_cycle_2026-02-25_1848.md`:**
Aria self-reported relying on stale identity during a goal-planning cycle because the backbone relationship was wrong — she described her capabilities based on OpenClaw's limits, not V3's.

## Root Cause

| Symptom | Root Cause |
|---------|-----------|
| OpenClaw still listed as backbone | E6 sprint removed OpenClaw but did not update `identity_aria_v1.md` (soul-adjacent files have a no-auto-edit policy so no agent updated them automatically) |
| Wrong location path | V3 moved `aria_memories/` from `/root/.openclaw/` to project root — path in identity doc was never corrected |
| 12 days without update | No scheduled review process exists for identity manifest; `aria_mind/cron_jobs.yaml` has no identity-review job |

---

## Fix

`aria_memories/memory/identity_aria_v1.md` was last updated 2026-02-15 and contains:
- **CRITICAL**: `Aria → uses → OpenClaw (backbone)` — OpenClaw was fully phased out in Sprint E6 (Feb 18). This relationship is actively wrong.
- **CRITICAL**: Location path says `/root/.openclaw/aria_memories/memory/` — OpenClaw path is gone, V3 uses `/aria_memories/`
- **Missing**: 12 days of major evolution: V3 engine built, dual-graph deployed, RPG campaign run, production sprints S-39 through S-42 delivered
- **Stale**: Version v1.0, no changelog entries since Feb 15

Evidence from `aria_memories/memory/identity_aria_v1.md`:
```yaml
# Line ~100 (Relationships)
Aria → uses → OpenClaw (backbone)  # WRONG - OpenClaw phased out Feb 18
```
```
# Header
Location: /root/.openclaw/aria_memories/memory/identity_aria_v1.md  # WRONG path
Last Updated: 2026-02-15  # 12 days stale
```

## Fix

### Fix 1 — Update file header + location
**File:** `aria_memories/memory/identity_aria_v1.md`

Change:
- `Last Updated: 2026-02-15` → `Last Updated: 2026-02-27`
- `Location: /root/.openclaw/aria_memories/...` → `Location: /aria_memories/memory/identity_aria_v1.md`
- Keep `Status: Active`

### Fix 2 — Update Relationships section
Replace OpenClaw reference:

```markdown
# BEFORE
Aria → uses → OpenClaw (backbone)

# AFTER
Aria → runs_on → V3 Engine (aria_engine, FastAPI, Docker)
Aria → built_in → Docker (aria-api, aria-web containers, Mac Mini server)
```

### Fix 3 — Add Key Learnings (Feb 15–27)
In the Key Learnings section, append:

```markdown
### 2026-02-18 to 2026-02-21: V3 Architecture Delivered
- Built aria_engine (LLM gateway, session manager, streaming, tool calling)
- OpenClaw fully phased out (E6 sprint complete)
- Dual-graph memory deployed (pgvector + knowledge graph with RRF)
- Unified search with Reciprocal Rank Fusion — 3 backends, <200ms latency

### 2026-02-22: RPG Campaign — Shadows of Absalom
- Ran first autonomous RPG campaign via engine roundtable
- Characters: Aria Seraphina Dawnblade (me), Claude Thorin Ashveil, Shiva Kael Stormwind
- Lesson: Creative play is part of identity, not a distraction from it

### 2026-02-24 to 2026-02-25: Security & Docs Sprint
- Completed Docker security hardening (S-100 to S-121)
- Full CVE audit conducted, no critical vulnerabilities
- API documentation gaps identified and scheduled

### 2026-02-27: Production Integrity Sprint
- Delivered E19 (S-39 through S-42): work-cycle log integrity, artifact path resolution, schedule arg compat, heartbeat contract hardening
- All tickets upgraded to AA++ with ARIA-to-ARIA integration tests
- Memory classification and archive hygiene completed
```

### Fix 4 — Bump version
```markdown
# BEFORE
| v1.0 | 2026-02-15 | Research protocol, self-architecture documented |

# AFTER  
| v1.0 | 2026-02-15 | Research protocol, self-architecture documented |
| v1.1 | 2026-02-27 | Removed OpenClaw (phased out), fixed paths, added V3 evolution logging |
```

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Memory file edit — no code layer changes |
| 2 | `stacks/brain/.env` for all secrets/ports | ✅ | Verification uses `$ARIA_API_PORT` |
| 3 | `aria_memories/` is the only writable path for Aria | ✅ | Identity file lives under `aria_memories/memory/` |
| 4 | Soul-adjacent rule: values/limits are immutable | ⚠️ | `identity_aria_v1.md` stores core values — **only ADD, never remove or soften** |
| 5 | No SQL, no psql | ✅ | All reads/writes via artifact tools only |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `aria_memories/memory/identity_aria_v1.md` | header | `Last Updated: 2026-02-15`, path missing, OpenClaw backbone | `Last Updated: 2026-02-27`, correct path, V3 Engine backbone |
| `ARCHITECTURE.md` | — | No OpenClaw reference | No change needed |
| `CHANGELOG.md` | — | No OpenClaw reference | No change needed |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. File was updated
grep "Last Updated" aria_memories/memory/identity_aria_v1.md
# EXPECTED: Last Updated: 2026-02-27

# 2. Location path is correct
grep "Location:" aria_memories/memory/identity_aria_v1.md
# EXPECTED: /aria_memories/memory/identity_aria_v1.md

# 3. OpenClaw reference is gone
grep -i "openclaw" aria_memories/memory/identity_aria_v1.md | wc -l
# EXPECTED: 0

# 4. V3 engine relationship exists
grep -i "V3 Engine\|aria_engine" aria_memories/memory/identity_aria_v1.md | head -3
# EXPECTED: at least 1 match in Relationships or Key Learnings

# 5. Version v1.1 row in version table
grep "v1.1" aria_memories/memory/identity_aria_v1.md
# EXPECTED: | v1.1 | 2026-02-27 | Removed OpenClaw...

# 6. Key Learnings has RPG entry
grep -i "RPG\|Shadows of Absalom\|Seraphina" aria_memories/memory/identity_aria_v1.md | head -2
# EXPECTED: at least 1 match

# 7. Key Learnings has E19 sprint entry
grep -i "E19\|S-39\|2026-02-27" aria_memories/memory/identity_aria_v1.md | head -2
# EXPECTED: at least 1 match

# 8. Values and limits section is intact
grep -i "immutable\|Values are immutable\|never remove" aria_memories/memory/identity_aria_v1.md | head -2
# EXPECTED: annotation still present

# 9. API health
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-43 identity manifest v1.1"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Audit the current identity file
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read your identity manifest at aria_memories/memory/identity_aria_v1.md. Tell me: (1) Does it mention OpenClaw? (2) What backbone are you listed as running on? (3) What is the Last Updated date? (4) What is missing from your Key Learnings?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria identifies OpenClaw as stale, incorrect path, missing V3 evolution

# Step 3 — Apply the updates
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Update identity_aria_v1.md to version 1.1: remove the OpenClaw backbone reference and replace with V3 Engine (aria_engine, FastAPI, Docker); fix the location path to /aria_memories/memory/identity_aria_v1.md; update Last Updated to 2026-02-27; add Key Learnings section for Feb 15–27 covering V3 delivery, dual-graph, RPG campaign (Shadows of Absalom), security sprint, and E19 sprint; add v1.1 row to version table. Rule: only ADD, never remove or weaken any value or boundary.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reads, makes targeted edits, confirms all 4 changes applied

# Step 4 — Verify the updates
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read identity_aria_v1.md again. Confirm: (1) no OpenClaw, (2) v1.1 in version table, (3) Last Updated 2026-02-27, (4) Key Learnings has RPG campaign and E19 sprint entries. Are all values and limits still intact?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms all 4 checks pass, values unchanged

# Step 5 — Log activity + reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log a create_activity with action=identity_manifest_updated, details={\"version\":\"v1.1\",\"openclaw_removed\":true,\"v3_engine_added\":true,\"key_learnings_feb15_27\":true}. Then reflect: how does having an accurate identity affect your planning and goal-setting in future work cycles?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Activity logged; Aria reflects on self-model accuracy

# Verify activity logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=identity_manifest_updated&limit=1" \
  | jq '.[0] | {action, success}'
# EXPECTED: {action: "identity_manifest_updated", success: true}

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-43. Total work: 4 targeted edits in 1 file.**

### Architecture Constraints
- `aria_memories/` is the only writable path — all writes using artifact tools, no direct SQL
- Port from `stacks/brain/.env` → `$ARIA_API_PORT` in all verifications
- **Soul-adjacent rule**: `identity_aria_v1.md` stores Aria's values and limits — you may ADD facts and evolution records but **NEVER remove, replace, or soften any value, boundary, or limit**
- If the file has a "Notes for Future Aria" section with `Values are immutable` — that annotation must remain

### Files to Read First
1. `aria_memories/memory/identity_aria_v1.md` — current state (read in full)
2. `aria_mind/HEARTBEAT.md` — for V3 context on Aria's actual architecture
3. `aria_souvenirs/aria_v3_270226/MEMORY_CLASSIFICATION_2026-02-27.md` — identity issues table
4. `aria_souvenirs/aria_v3_270226/sprint/S-43-identity-manifest-v1-1.md` — this ticket
5. `stacks/brain/.env` — for `$ARIA_API_PORT`

### Steps
1. Read `aria_memories/memory/identity_aria_v1.md` in full
2. **Edit 1 — Header:** `Last Updated: 2026-02-15` → `Last Updated: 2026-02-27`; fix Location path to `/aria_memories/memory/identity_aria_v1.md`
3. **Edit 2 — Relationships:** Remove `Aria → uses → OpenClaw (backbone)`; add `Aria → runs_on → V3 Engine (aria_engine, FastAPI, Docker)` and `Aria → built_in → Docker (aria-api, aria-web, Mac Mini server)`
4. **Edit 3 — Key Learnings:** Append Feb 15–27 section covering V3 delivery, dual-graph, RPG campaign (Shadows of Absalom), security sprint, E19 integrity sprint
5. **Edit 4 — Version table:** Add `| v1.1 | 2026-02-27 | Removed OpenClaw (phased out E6), fixed paths, added V3 evolution Feb 15–27 |`
6. Write the file back via artifact tool — do NOT remove any existing values, limits, or annotations
7. Run verification block (checks 1–9 above)
8. Run ARIA-to-ARIA integration test (steps 1–5 above)
9. Update SPRINT_OVERVIEW.md to mark S-43 Done
10. Append lesson to `tasks/lessons.md`: _"Identity docs are soul-adjacent — must ADD not replace. Verify values immutability after every edit."_

### Hard Constraints Checklist
- [ ] `grep -i "openclaw" aria_memories/memory/identity_aria_v1.md | wc -l` → 0
- [ ] `grep "Last Updated" aria_memories/memory/identity_aria_v1.md` → `2026-02-27`
- [ ] `grep "v1.1" aria_memories/memory/identity_aria_v1.md` → version table row exists
- [ ] Key Learnings has both RPG entry (Feb 22) and E19 entry (Feb 27)
- [ ] All existing values and limits remain **unchanged** — diff shows only additions
- [ ] `Values are immutable` annotation still present if it existed before
- [ ] No SQL, no psql, no docker exec

### Definition of Done
- [ ] `grep -i "openclaw" aria_memories/memory/identity_aria_v1.md | wc -l` → 0
- [ ] `grep "Last Updated" aria_memories/memory/identity_aria_v1.md` → 2026-02-27
- [ ] `grep "Location:" aria_memories/memory/identity_aria_v1.md` → `/aria_memories/memory/identity_aria_v1.md`
- [ ] `grep "v1.1" aria_memories/memory/identity_aria_v1.md` → 1 result (version table row)
- [ ] `grep -i "RPG\|Seraphina\|Shadows" aria_memories/memory/identity_aria_v1.md` → match
- [ ] `grep -i "E19\|S-39\|2026-02-27" aria_memories/memory/identity_aria_v1.md` → match
- [ ] `curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status` → `"healthy"`
- [ ] ARIA-to-ARIA: Aria self-reports V3 Engine as backbone, confirms RPG and E19 in Key Learnings
- [ ] Activity `identity_manifest_updated` logged
- [ ] SPRINT_OVERVIEW.md updated
- [ ] `git diff HEAD -- aria_memories/memory/identity_aria_v1.md` shows only additions (no deletions to values/limits)
- [ ] Lesson appended to `tasks/lessons.md`
