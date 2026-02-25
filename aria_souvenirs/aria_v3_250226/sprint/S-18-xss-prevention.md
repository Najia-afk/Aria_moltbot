# S-18: XSS Prevention — innerHTML Escaping & onclick Migration
**Epic:** E10 — Security Hardening | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
Two categories of DOM-based XSS vulnerability across the web interface:

### Category A: Unescaped innerHTML injections
API response data and error messages are inserted into `innerHTML` without escaping:
- `src/web/templates/engine_operations.html` L482: `${e.message}` in innerHTML
- `src/web/templates/engine_operations.html` L661: `${e.message}` in innerHTML  
- `src/web/templates/creative_pulse.html` L328: `${err.message}` in innerHTML
- `src/web/templates/activity_visualization.html` L165: `${err.message}` in innerHTML
- `src/web/templates/sprint_board.html` L247: mixed escaped/unescaped values
- `src/web/templates/sentiment.html` L235: `${data.total_events}` raw in innerHTML

If the API returns attacker-controlled strings (e.g., a malicious session name or error message), JavaScript code can be injected and executed.

### Category B: Inline onclick handlers with interpolated data
200+ `onclick="functionName('${id}')"` across ALL templates. API-returned IDs interpolated directly into HTML attribute context via JS template literals:
- `src/web/templates/models_manager.html` L310-314: `onclick="openEditModal('${m.id}')"`
- `src/web/templates/engine_operations.html` L528-531: `onclick="triggerJob('${job.id}')"`
- `src/web/templates/sessions.html` L519: similar pattern
- `src/web/templates/proposals.html` L99-100: similar

If an ID contains `')` or `')-alert(1)-('`, it breaks out of the handler → XSS.

## Root Cause
Quick development without security review. An `escapeHtml()` function exists in `aria-common.js` L96-113 but is rarely used.

## Fix

### Fix 1: Audit and escape ALL innerHTML insertions
For every `innerHTML =` or `.innerHTML +=` in templates:
- If inserting text/error messages: use `textContent` instead
- If inserting HTML structure: escape all interpolated data with `escapeHtml()`

**Pattern:**
```javascript
// BEFORE (vulnerable):
container.innerHTML = `<div class="error">${e.message}</div>`;

// AFTER (safe):
container.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
// OR even better:
container.textContent = e.message;
```

### Fix 2: Migrate onclick handlers to event delegation
For each template with inline `onclick`:

**BEFORE (vulnerable):**
```javascript
row.innerHTML = `<button onclick="deleteItem('${item.id}')">Delete</button>`;
```

**AFTER (safe):**
```javascript
row.innerHTML = `<button class="btn-delete" data-id="${escapeHtml(item.id)}">Delete</button>`;
// In setup:
document.addEventListener('click', (e) => {
    if (e.target.matches('.btn-delete')) {
        deleteItem(e.target.dataset.id);
    }
});
```

### Fix 3: Create `safeHTML()` template literal tag
**File:** `src/web/static/js/aria-common.js` — add:
```javascript
function safeHTML(strings, ...values) {
    return strings.reduce((result, str, i) => {
        const val = i < values.length ? escapeHtml(String(values[i])) : '';
        return result + str + val;
    }, '');
}
```
Usage: `` container.innerHTML = safeHTML`<div>${userInput}</div>`; ``

### Fix 4: Priority templates for onclick migration
Migrate these templates first (most vulnerable):
1. `models_manager.html` — full CRUD with edit/delete buttons
2. `engine_operations.html` — job trigger buttons
3. `sessions.html` — session action buttons
4. `engine_roundtable.html` — ~60 inline onclick occurrences
5. `proposals.html` — vote/approve buttons

### Fix 5: rpg.html var → const/let
**File:** `src/web/templates/rpg.html` L216-467
Replace all 44 `var` declarations with `const` or `let` as appropriate. This is code quality, not XSS, but was found in the same audit.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend only |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-17 (CSRF) should be done together for a security-focused sprint block.

## Verification
```bash
# 1. No unescaped innerHTML in error paths:
grep -rn '\.innerHTML.*\${.*\.message}' src/web/templates/ --include='*.html' | grep -v 'escapeHtml'
# EXPECTED: 0 matches

# 2. No raw onclick with interpolated IDs:
grep -rn "onclick=\"[^\"]*\${" src/web/templates/ --include='*.html' | grep -v 'escapeHtml'
# EXPECTED: 0 matches (all migrated to data-* + delegation)

# 3. var usage eliminated in rpg.html:
grep -c '\bvar ' src/web/templates/rpg.html
# EXPECTED: 0

# 4. safeHTML function exists:
grep 'function safeHTML' src/web/static/js/aria-common.js
# EXPECTED: 1 match

# 5. Manual: Open models manager, create model with name containing <script>alert(1)</script>
# EXPECTED: Script tag rendered as text, not executed
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/static/js/aria-common.js (full — find existing escapeHtml)
- src/web/templates/engine_operations.html (L470-L670 — onclick + innerHTML sections)
- src/web/templates/models_manager.html (L280-L320 — onclick section)
- src/web/templates/sessions.html (L500-L530 — onclick section)
- src/web/templates/rpg.html (L210-L470 — var usage)

CONSTRAINTS: SECURITY-CRITICAL. Test XSS payloads manually.

STEPS:
1. Add safeHTML() template tag to aria-common.js
2. Grep ALL templates for innerHTML with ${} interpolation → list each one
3. For each: replace with escapeHtml() or textContent
4. Grep ALL templates for onclick="...${}" → list each one
5. For each: migrate to data-* attributes + event delegation
6. Prioritize models_manager, engine_operations, sessions, proposals first
7. Fix rpg.html var → const/let
8. Run grep verification commands to confirm 0 vulnerable patterns remain
9. Test with XSS payload: create an entity with name <img src=x onerror=alert(1)>
10. All buttons must still function after migration — test CRUD flows!
```
