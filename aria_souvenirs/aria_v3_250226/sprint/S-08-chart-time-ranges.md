# S-08: Chart Time Range Selectors
**Epic:** E4 — Chart Time Ranges | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
Multiple dashboard pages have hardcoded 24-hour time ranges with no way for users to view historical data:

1. **sessions.html** L334: `loadHourlySeries(hours = 24)` — hardcoded, no selector UI
2. **sessions.html** L615: Second chart also uses `hours=24`
3. **sentiment.html** L222: `hours=24` hardcoded in API call
4. **creative_pulse.html** L64-L69: Has a selector but only offers 6h/12h/24h/72h — missing 7d/30d

Aria has weeks of historical data. Users can only see the last 24 hours.

## Root Cause
Time range selectors were not built consistently. `creative_pulse.html` has a partial implementation that can be used as a pattern for the others.

## Fix

### Fix 1: Create a reusable time range selector component
**File:** `src/web/templates/components/time_range_selector.html` (NEW — Jinja2 include)
```html
<!-- Reusable time range selector -->
<div class="btn-group time-range-selector mb-3" role="group" data-target="{{ target_id }}">
  <button type="button" class="btn btn-outline-secondary btn-sm" data-hours="6">6h</button>
  <button type="button" class="btn btn-outline-secondary btn-sm" data-hours="12">12h</button>
  <button type="button" class="btn btn-outline-secondary btn-sm active" data-hours="24">24h</button>
  <button type="button" class="btn btn-outline-secondary btn-sm" data-hours="72">3d</button>
  <button type="button" class="btn btn-outline-secondary btn-sm" data-hours="168">7d</button>
  <button type="button" class="btn btn-outline-secondary btn-sm" data-hours="720">30d</button>
</div>
```

### Fix 2: Add selector to sessions.html
**File:** `src/web/templates/sessions.html`
- Add `{% include 'components/time_range_selector.html' %}` above the chart
- At L334: Change `loadHourlySeries(hours = 24)` to `loadHourlySeries(hours = selectedHours)`
- At L615: Same treatment for second chart
- Add JS click handler:
```javascript
document.querySelectorAll('.time-range-selector button').forEach(btn => {
  btn.addEventListener('click', function() {
    this.parentNode.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    this.classList.add('active');
    const hours = parseInt(this.dataset.hours);
    loadHourlySeries(hours);
  });
});
```

### Fix 3: Add selector to sentiment.html
**File:** `src/web/templates/sentiment.html`
- Add selector include above sentiment chart
- At L222: Replace `hours=24` with dynamic value from selector
- Same JS click handler pattern

### Fix 4: Extend creative_pulse.html range options
**File:** `src/web/templates/creative_pulse.html` L64-L69
- Add `7d` (168h) and `30d` (720h) buttons to existing selector
- Default stays at 24h

### Fix 5: Verify API endpoints support larger ranges
Check that the API endpoints called by these pages accept `hours` > 24. If they have a max limit, increase it or add pagination.

**APIs to verify:**
- `/api/proxy/engine/sessions/hourly?hours=720`
- `/api/proxy/analytics/sentiment?hours=720`
- `/api/proxy/analytics/creative-pulse?hours=720`

If any API caps at 24h, fix the API handler.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | If API changes needed, go DB↔ORM↔API↔client↔skill |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

**Pagination:** Always think about pagination. If the API returns 720 hours of hourly data (720 rows), ensure the query is indexed and the response is paged or aggregated.

## Dependencies
- None — standalone

## Verification
```bash
# 1. Verify component file exists:
test -f src/web/templates/components/time_range_selector.html && echo "OK"

# 2. Verify sessions.html includes component:
grep 'time_range_selector' src/web/templates/sessions.html
# EXPECTED: include statement

# 3. Verify sentiment.html includes component:
grep 'time_range_selector' src/web/templates/sentiment.html
# EXPECTED: include statement

# 4. Verify creative_pulse.html has 7d/30d:
grep '168\|720' src/web/templates/creative_pulse.html
# EXPECTED: data-hours="168" and data-hours="720"

# 5. Verify no hardcoded hours=24 remains:
grep -rn 'hours.*=.*24' src/web/templates/sessions.html src/web/templates/sentiment.html
# EXPECTED: No matches (all dynamic now)

# 6. Manual: Open sessions page, click 7d, verify chart loads
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/templates/sessions.html (L300-L650 — chart JS section)
- src/web/templates/sentiment.html (L200-L250 — chart section)
- src/web/templates/creative_pulse.html (L50-L100 — time selector)
- src/web/app.py (find routes for sessions, sentiment, creative-pulse)
- Find the API proxy routes to check max hours support

CONSTRAINTS: #1 (if API changes needed), pagination/indexing on queries.

STEPS:
1. Create src/web/templates/components/ directory if missing
2. Create time_range_selector.html reusable component with 6h/12h/24h/3d/7d/30d buttons
3. Include component in sessions.html, wire to loadHourlySeries()
4. Include component in sentiment.html, wire to sentiment API call
5. Add 7d/30d to creative_pulse.html existing selector
6. Check each API endpoint for max hours support — fix if capped
7. Add DB index on timestamp columns used in hourly aggregation if missing (via migration)
8. Remove ALL hardcoded hours=24 from JS
9. Run verification commands
```
