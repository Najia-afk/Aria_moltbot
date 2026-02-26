# S-13: Remove Dead Templates & Routes
**Epic:** E8 — Dead Code | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
Several routes and templates are orphaned or duplicated:

1. **`/wallets`** (`src/web/app.py` L159) — 301 redirect to `/models`. Wallet concept was removed. The redirect and possibly a `wallets.html` template remain.

2. **`/activity-visualization`** (`src/web/app.py` L106) — orphan alias. Either redirects to another page or renders a dead template. Not in navigation.

3. **`/cron`** vs **`/operations/cron/`** — two different routes. If they render the same content, one should redirect. If different, clarify naming.

4. **`/agents`** vs **`/operations/agents/`** — potentially different templates (`agents.html` vs `engine_agents.html`). One should be canonical.

5. **Operations hub sub-routes** (`/operations/scheduler/`, `/operations/hub/`) — at L228-L238 — exist but aren't linked in nav.

6. **Dead templates** — templates in `src/web/templates/` that are not referenced by any route.

## Root Cause
Routes were added and renamed without cleaning up old paths. No route hygiene process.

## Fix

### Fix 1: Remove /wallets redirect
**File:** `src/web/app.py` L159
Delete the route entirely. If `wallets.html` template exists, delete it too.

### Fix 2: Remove or redirect /activity-visualization
**File:** `src/web/app.py` L106
- If it renders a template: check if the template is used elsewhere. If not, delete both.
- If it redirects: check if the target is valid. If so, keep 301 for backward compat — but remove in 1 sprint.

### Fix 3: Resolve /cron vs /operations/cron/
**File:** `src/web/app.py`
- Make `/operations/cron/` canonical
- Add 301: `/cron` → `/operations/cron/`
- Eventually remove `/cron` route

### Fix 4: Resolve /agents vs /operations/agents/
**File:** `src/web/app.py`
- After S-06 (nav regrouping), `/agents` is canonical (in Agents nav)
- 301: `/operations/agents/` → `/agents`
- Delete `engine_agents.html` if it's the duplicate template

### Fix 5: Evaluate orphan operations sub-routes
- `/operations/scheduler/` — if functional, add to Operations nav (S-07)
- `/operations/hub/` — if empty/broken, delete

### Fix 6: Scan for dead templates
Run a script to find templates not referenced by any route:
```python
import os, re
templates = set(os.listdir('src/web/templates/'))
with open('src/web/app.py') as f:
    code = f.read()
referenced = set(re.findall(r"render_template\('([^']+)'", code))
dead = templates - referenced - {'base.html', 'components'}
print("Dead templates:", dead)
```

### Fix 7: Delete dead templates
For each dead template found, verify it's not `{% include %}`d by another template, then delete.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend cleanup only |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test all routes after cleanup |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- Should follow S-05, S-06, S-07 (nav regrouping) to know which routes are canonical

## Verification
```bash
# 1. Verify /wallets returns 404:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/wallets
# EXPECTED: 404

# 2. Verify canonical redirects work:
curl -s -o /dev/null -w "%{http_code}" -L http://localhost:5050/cron
# EXPECTED: 200 (after redirect to /operations/cron/)

curl -s -o /dev/null -w "%{http_code}" -L http://localhost:5050/operations/agents/
# EXPECTED: 200 (after redirect to /agents)

# 3. Count routes in app.py:
grep -c "@app.route" src/web/app.py
# EXPECTED: Reduced by 3-5 from current count

# 4. Count templates:
ls src/web/templates/*.html | wc -l
# EXPECTED: Reduced by 2-4 from current count

# 5. Dead template scan:
python -c "
import os, re
templates = {f for f in os.listdir('src/web/templates/') if f.endswith('.html')}
with open('src/web/app.py') as f:
    code = f.read()
referenced = set(re.findall(r\"render_template\('([^']+)'\", code))
# Also check includes
for t in templates:
    with open(f'src/web/templates/{t}') as f:
        tc = f.read()
    referenced.update(re.findall(r\"{%.*include.*'([^']+)'.*%}\", tc))
dead = templates - referenced - {'base.html'}
print('Dead templates:', dead if dead else 'None')
"
# EXPECTED: None
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/app.py (full — all routes, identify dead/duplicate ones)
- src/web/templates/ — list all .html files
- src/web/templates/base.html (nav — which routes are linked)

CONSTRAINTS: Add 301 redirects for backward compatibility before removing routes.

STEPS:
1. Map every route in app.py to its template
2. Map every template to which routes reference it
3. Map every nav link in base.html to which route it points to
4. Identify: (a) routes with no nav link, (b) templates with no route, (c) duplicate routes
5. Delete /wallets route and wallets.html if exists
6. Decide on /activity-visualization — delete or redirect
7. Add 301: /cron → /operations/cron/
8. Add 301: /operations/agents/ → /agents
9. Delete unreferenced templates (after checking includes)
10. Run dead template scan
11. Run verification commands
```
