# S2-02: Fix XSS Vulnerability in Security Template
**Epic:** E1 — Bug Fixes | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
`src/web/templates/security.html` line ~217 uses `input_preview` in a `title` attribute without proper escaping: `title="${preview}"`. The cell content uses `escapeHtml()` but the title attribute is vulnerable — a crafted preview containing `"` can break out of the attribute and inject HTML/JS.

## Root Cause
The `renderSecurityTable()` function in `security.html` escapes `input_preview` for cell content display via `escapeHtml()`, but passes the raw (or partially escaped) value into the `title` attribute of the table cell. HTML attribute context requires different escaping (must escape `"`, `'`, `&`, `<`, `>`). A security event with `input_preview` containing `" onmouseover="alert(1)` would execute JavaScript.

## Fix

### File: `src/web/templates/security.html`
Find the line where `title="${preview}"` is used in the security events table rendering.

BEFORE:
```javascript
title="${preview}"
```
AFTER:
```javascript
title="${escapeHtml(preview)}"
```

Additionally, ensure the `escapeHtml` function also escapes single quotes:
Find the `escapeHtml` function definition. If it doesn't escape `'`, add:
```javascript
.replace(/'/g, '&#039;')
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Frontend-only change |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test via browser after `docker compose up` |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
None — standalone security fix.

## Verification
```bash
# 1. Verify escapeHtml is used in title attribute:
grep -n 'title=' src/web/templates/security.html | grep -i 'escape\|preview'
# EXPECTED: title="${escapeHtml(preview)}" (escaped)

# 2. Verify escapeHtml handles single quotes:
grep -A5 'function escapeHtml' src/web/templates/security.html
# EXPECTED: includes .replace(/'/g, '&#039;')

# 3. Manual test: Create a security event with XSS payload:
curl -X POST http://localhost:8000/api/security-events -H 'Content-Type: application/json' \
  -d '{"threat_level":"LOW","threat_type":"xss_test","input_preview":"test\" onmouseover=\"alert(1)","source":"test"}'
# Then visit security page and verify no JS executes on hover
```

## Prompt for Agent
```
You are fixing an XSS vulnerability in the Aria security dashboard.

FILES TO READ FIRST:
- src/web/templates/security.html (find renderSecurityTable, look for title="${preview}")

STEPS:
1. Read security.html and find where input_preview/preview is used in title attributes
2. Wrap all title attribute values with escapeHtml()
3. Ensure escapeHtml() also escapes single quotes (&#039;)
4. Run verification commands

CONSTRAINTS: Frontend-only. No secrets. No API changes.
```
