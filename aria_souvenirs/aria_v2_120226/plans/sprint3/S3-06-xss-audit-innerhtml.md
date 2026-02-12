# S3-06: XSS Audit — innerHTML Usage
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P0 | **Points:** 3 | **Phase:** 3

## Problem
Multiple templates build DOM content via `innerHTML` with potentially unescaped user data. This is a cross-site scripting (XSS) security vulnerability.

Examples of risky patterns:
```javascript
element.innerHTML = `<p>${item.title}</p>`;         // ❌ No escaping
element.innerHTML = `<p>${escapeHtml(item.title)}</p>`;  // ✅ Escaped
```

Any field originating from user input, LLM output, or API responses must be escaped.

## Root Cause
Templates were built incrementally without a shared escaping convention. No `escapeHtml()` utility existed until Sprint 3 (S3-01).

## Fix
1. **Audit every innerHTML assignment** across all templates
2. **Categorize each** as safe (static HTML) or unsafe (dynamic data)
3. **Wrap unsafe values** with `escapeHtml()` from the shared utils.js
4. **Document the results** showing each file and what was fixed

Audit scope:
```bash
grep -rn "innerHTML" src/web/templates/ --include="*.html" | grep -v "\.innerHTML = ''" | grep -v "\.innerHTML = \`\s*\`"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Rebuild web container after changes |
| 5 | aria_memories writable | ❌ | Code changes only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S3-01 (shared `escapeHtml()` must exist in utils.js or aria-common.js first).

## Verification
```bash
# 1. Find all innerHTML assignments with template literals containing variables:
grep -rn 'innerHTML.*\$\{' src/web/templates/ --include="*.html" | grep -v "escapeHtml" | wc -l
# EXPECTED: 0 (all dynamic interpolations now use escapeHtml)

# 2. escapeHtml is available:
grep -n "function escapeHtml" src/web/static/js/*.js
# EXPECTED: at least 1 match

# 3. All pages still load:
for page in / goals thoughts memories models knowledge sessions wallets sprint-board; do
  curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000$page"
done
# EXPECTED: all 200

# 4. Spot-check a fixed page renders properly:
curl -s http://localhost:5000/goals | grep -c "escapeHtml"
# EXPECTED: 0 (escapeHtml is in JS, not visible in HTML source unless inline)
```

## Prompt for Agent
```
Audit all innerHTML assignments for XSS vulnerabilities and fix them.

**Files to read:**
- src/web/static/js/utils.js (confirm escapeHtml exists)
- Run: grep -rn "innerHTML" src/web/templates/ --include="*.html"
- Focus on assignments that interpolate variables like ${data.title}

**Steps:**
1. List all innerHTML assignments across all templates
2. For each, determine if the interpolated data comes from user/API input
3. Wrap all user/API data with escapeHtml()
4. Ensure escapeHtml is loaded before it's used (via utils.js script tag)
5. Test all pages load without JS errors
6. Document what was fixed in the PR description
```
