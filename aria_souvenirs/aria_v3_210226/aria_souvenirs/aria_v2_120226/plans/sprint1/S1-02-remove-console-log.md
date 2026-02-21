# S1-02: Remove Bare console.log from Production Templates
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P1 | **Points:** 1 | **Phase:** 1

## Problem
Two production HTML templates contain bare `console.log()` calls that are not gated behind `window.ARIA_DEBUG`:
- `src/web/templates/knowledge.html` line 596: `console.log('Selected entity:', entity);`
- `src/web/templates/sprint_board.html` line 482: `console.log('boardInit running, readyState:', document.readyState);`

Sprint 1 from yesterday (S1-09) was supposed to gate all console.log behind `window.ARIA_DEBUG`. These two were missed.

## Root Cause
The S1-09 ticket from the 2026-02-11 session did not catch these two templates. `wallets.html` was correctly gated (`if (window.ARIA_DEBUG) console.log(...)` at line 898), but knowledge.html and sprint_board.html were not updated.

## Fix

**File 1:** `src/web/templates/knowledge.html` line 596

**BEFORE:**
```javascript
console.log('Selected entity:', entity);
```

**AFTER:**
```javascript
if (window.ARIA_DEBUG) console.log('Selected entity:', entity);
```

**File 2:** `src/web/templates/sprint_board.html` line 482

**BEFORE:**
```javascript
console.log('boardInit running, readyState:', document.readyState);
```

**AFTER:**
```javascript
if (window.ARIA_DEBUG) console.log('boardInit running, readyState:', document.readyState);
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Frontend only |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Verify templates load after change |
| 5 | aria_memories only writable path | ❌ | Code change only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — independent fix.

## Verification
```bash
# 1. No bare console.log remaining:
grep -rn "console.log" src/web/templates/*.html | grep -v "ARIA_DEBUG" | grep -v "console.log.*=.*false"
# EXPECTED: no output

# 2. Gated console.log present:
grep -rn "ARIA_DEBUG.*console.log" src/web/templates/*.html
# EXPECTED: 3 lines (wallets.html, knowledge.html, sprint_board.html)

# 3. Pages still load:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/knowledge && echo " /knowledge"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/sprint-board && echo " /sprint-board"
# EXPECTED: 200 200
```

## Prompt for Agent
```
Fix bare console.log statements in two production HTML templates.

**Files to read:**
- src/web/templates/knowledge.html (line ~596)
- src/web/templates/sprint_board.html (line ~482)

**Constraints:** Docker-first testing — verify pages load after change.

**Steps:**
1. In knowledge.html, find `console.log('Selected entity:', entity);` and prefix with `if (window.ARIA_DEBUG) `
2. In sprint_board.html, find `console.log('boardInit running, readyState:', document.readyState);` and prefix with `if (window.ARIA_DEBUG) `
3. Verify no bare console.log remains: `grep -rn "console.log" src/web/templates/*.html | grep -v "ARIA_DEBUG"`
4. Verify pages load: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/knowledge`
```
