# S1-05: Verify DOMContentLoaded Arrow Function Wrappers
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P1 | **Points:** 2 | **Phase:** 1

## Problem
Sprint 7 ticket S7-01 fixed a bug where `DOMContentLoaded` event listeners passed the `Event` object as a function parameter (e.g., `loadThoughts` received the Event as `page` param → 422 errors). The fix was to wrap in arrow functions: `() => loadThoughts()`.

We need to verify all 13 templates with `DOMContentLoaded` use the correct pattern. Some templates may have been missed or may have regressed.

## Root Cause
The `DOMContentLoaded` event listener passes the `Event` object as the first argument to the callback. Functions like `loadThoughts(page=1)` would receive the Event as `page`, causing API calls with `?page=[object Event]` → 422 validation errors.

## Fix
Audit all 13 `DOMContentLoaded` patterns and fix any that don't use arrow function wrappers.

**Correct patterns:**
```javascript
// ✅ Arrow function wrapper (safe):
document.addEventListener('DOMContentLoaded', () => loadThoughts());
document.addEventListener('DOMContentLoaded', () => { loadGoals(); initBoard(); });
document.addEventListener('DOMContentLoaded', async () => { await init(); });

// ❌ Direct reference (DANGEROUS — receives Event as first arg):
document.addEventListener('DOMContentLoaded', loadThoughts);
document.addEventListener('DOMContentLoaded', boardInit);
```

**Templates to check (13 total):**
1. goals.html — `() => {` ✅
2. heartbeat.html — `loadHeartbeatData` ⚠️ needs check
3. knowledge.html — `loadKnowledgeGraph` ⚠️ needs check
4. memories.html — `() => loadMemories()` ✅
5. models.html — `async () => {` ✅
6. records.html — `loadRecords` ⚠️ needs check
7. services.html — `refreshAllStatus` + `() => {` ⚠️ mixed
8. skill_graph.html — `loadGraph` ⚠️ needs check
9. social.html — `() => loadPosts()` ✅
10. sprint_board.html — `boardInit` ⚠️ needs check
11. thoughts.html — `() => loadThoughts()` ✅
12. wallets.html — `async () => {` ✅

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Verify pages load after fix |
| 5 | aria_memories writable | ❌ | Code only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — independent fix. Partially overlaps with S1-04 verification.

## Verification
```bash
# 1. Check all DOMContentLoaded patterns:
grep -n "DOMContentLoaded" src/web/templates/*.html
# EXPECTED: All lines use `() =>` or `async () =>` wrapper

# 2. Find any bare function references:
grep -n "DOMContentLoaded.*,[[:space:]]*[a-zA-Z]*)" src/web/templates/*.html | grep -v "() =>"
# EXPECTED: no output (all wrapped)

# 3. Quick function check — do any load functions accept Event?
# Functions should have default params or no params:
grep -n "function loadHeartbeatData\|function loadKnowledgeGraph\|function loadRecords\|function loadGraph\|function boardInit\|function refreshAllStatus" src/web/templates/*.html
# EXPECTED: Functions listed — check if first param could be mistaken for Event

# 4. All pages return 200:
for page in heartbeat knowledge records services skill_graph sprint-board; do
  curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000/$(echo $page | tr _ -)"
done
# EXPECTED: all 200
```

## Prompt for Agent
```
Verify and fix DOMContentLoaded event listener patterns in all templates.

**Files to read:**
- src/web/templates/heartbeat.html (search for DOMContentLoaded)
- src/web/templates/knowledge.html (search for DOMContentLoaded)
- src/web/templates/records.html (search for DOMContentLoaded)
- src/web/templates/services.html (search for DOMContentLoaded)
- src/web/templates/skill_graph.html (search for DOMContentLoaded)
- src/web/templates/sprint_board.html (search for DOMContentLoaded)

**Constraints:** Docker-first testing.

**Steps:**
1. For each template, check if the DOMContentLoaded listener uses a bare function reference
2. If the function accepts parameters (page, limit, etc.), wrap in `() => fnName()`
3. If the function takes no parameters AND doesn't use `this`, a bare reference is acceptable
4. But for safety, always use arrow function wrapper
5. Verify all pages load after changes
```
