# S1-06: Fix Dashboard Chart Filter Dropdown

**Sprint:** 1 — UI/UX  
**Priority:** 🟡 MEDIUM  
**Estimate:** 3 points  
**Status:** TODO  

---

## Problem

The Activity Timeline chart filter dropdown on the dashboard is **cosmetic only** — it has no effect.

### `src/web/templates/dashboard.html:201-206`

```html
<!-- src/web/templates/dashboard.html:201-206 -->
<select class="chart-filter">
    <option>Last 24h</option>
    <option>Last 7d</option>
    <option>Last 30d</option>
</select>
```

Issues:
1. **No `id` attribute** — JavaScript cannot target this element
2. **No `onchange` handler** — selecting a different option does nothing
3. **No `value` attributes** on the `<option>` elements

### The chart always shows 7 days

The activity chart is built at **lines 369-407** with a hardcoded 7-day window:

```javascript
// src/web/templates/dashboard.html:369-372
const dayBuckets = {};
for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
```

The loop always creates 7 buckets regardless of the dropdown selection. The fetch at **line 353** pulls `limit=100` activities:

```javascript
// src/web/templates/dashboard.html:353
fetch(`${API_BASE}/activities?limit=100`)
```

This is sufficient for 7d but may not be enough for 30d.

---

## Root Cause

The dropdown was added during the dashboard UI redesign for visual completeness but was never wired to the chart rendering logic. The chart rendering is inside a `.then()` callback of the activities fetch and doesn't reference the dropdown at all.

---

## Fix

### 1. Add id, values, and onchange to the select — `dashboard.html:201-206`

**Before:**
```html
<select class="chart-filter">
    <option>Last 24h</option>
    <option>Last 7d</option>
    <option>Last 30d</option>
</select>
```

**After:**
```html
<select class="chart-filter" id="activity-period-filter" onchange="loadActivityChart()">
    <option value="1">Last 24h</option>
    <option value="7" selected>Last 7d</option>
    <option value="30">Last 30d</option>
</select>
```

### 2. Extract chart rendering into a named function — `dashboard.html` script block

**Before (lines 353-407)** — chart rendering is inline inside a `.then()`:

```javascript
fetch(`${API_BASE}/activities?limit=100`)
    .then(r => r.json())
    .then(data => {
        // ── Recent Activity List (top 10) ──
        ...
        // ── Activity Timeline Chart (7-day buckets) ──
        const now = new Date();
        const dayBuckets = {};
        for (let i = 6; i >= 0; i--) { ... }
        ...
    });
```

**After** — extract chart into a reusable function:

```javascript
// Cache activities data for reuse
let _activitiesCache = [];

function loadActivityChart() {
    const periodDays = parseInt(document.getElementById('activity-period-filter').value || '7', 10);
    const now = new Date();
    const dayBuckets = {};

    // Create buckets for selected period
    const bucketCount = periodDays === 1 ? 24 : periodDays;
    if (periodDays === 1) {
        // Hourly buckets for 24h
        for (let i = 23; i >= 0; i--) {
            const d = new Date(now);
            d.setHours(d.getHours() - i, 0, 0, 0);
            const key = d.toISOString().slice(0, 13); // YYYY-MM-DDTHH
            dayBuckets[key] = 0;
        }
        _activitiesCache.forEach(a => {
            if (!a.created_at) return;
            const key = new Date(a.created_at).toISOString().slice(0, 13);
            if (dayBuckets[key] !== undefined) dayBuckets[key] += 1;
        });
    } else {
        // Daily buckets for 7d / 30d
        for (let i = periodDays - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            const key = d.toISOString().split('T')[0];
            dayBuckets[key] = 0;
        }
        _activitiesCache.forEach(a => {
            if (!a.created_at) return;
            const key = new Date(a.created_at).toISOString().split('T')[0];
            if (dayBuckets[key] !== undefined) dayBuckets[key] += 1;
        });
    }

    const labels = Object.keys(dayBuckets).map(d => {
        if (periodDays === 1) return new Date(d).toLocaleTimeString('en-US', { hour: 'numeric' });
        return new Date(d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    });
    const values = Object.values(dayBuckets);

    const ctx = document.getElementById('activity-timeline-canvas').getContext('2d');
    if (activityChart) activityChart.destroy();
    activityChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets: [{ label: 'Activities', data: values, borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.1)', fill: true, tension: 0.4 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }, y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } } } }
    });
}
```

Update the fetch to increase the limit for 30d and call the new function:

```javascript
fetch(`${API_BASE}/activities?limit=500`)
    .then(r => r.json())
    .then(data => {
        _activitiesCache = Array.isArray(data) ? data : [];

        // ── Recent Activity List (top 10) ──
        // ... (existing list rendering code stays here) ...

        // ── Activity Timeline Chart ──
        loadActivityChart();
    });
```

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 1 — `src/web/templates/dashboard.html` |
| **Lines changed** | ~50 (refactor inline chart to named function, update HTML) |
| **Breaking changes** | None |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Revert `dashboard.html` |

---

## Dependencies

- None. Self-contained in the dashboard template.

---

## Verification

```bash
# 1. Verify select has id and onchange
grep -n 'id="activity-period-filter"' src/web/templates/dashboard.html
# Expected: 1 match with onchange="loadActivityChart()"

# 2. Verify option elements have values
grep -n 'value="1"\|value="7"\|value="30"' src/web/templates/dashboard.html
# Expected: 3 matches

# 3. Verify loadActivityChart function exists
grep -n "function loadActivityChart" src/web/templates/dashboard.html
# Expected: 1 match

# 4. Verify hardcoded "6" loop is removed from inline .then()
grep -n "i = 6; i >= 0" src/web/templates/dashboard.html
# Expected: 0 matches (moved into the function with dynamic period)
```

### Manual Verification
1. Open Dashboard → Activity Timeline chart loads with 7d (default)
2. Select "Last 24h" → chart redraws with hourly buckets for past 24 hours
3. Select "Last 30d" → chart redraws with 30 daily buckets
4. Select "Last 7d" → chart returns to 7-day view
5. Recent Activity list (below chart) is unaffected by filter changes

---

## Prompt for Agent

```
Wire the dashboard Activity Timeline chart filter dropdown to actually filter the chart.

1. In src/web/templates/dashboard.html, update the <select> at line 201:
   - Add id="activity-period-filter"
   - Add onchange="loadActivityChart()"
   - Add value="1", value="7" (selected), value="30" to the three options

2. Extract the Activity Timeline Chart rendering (lines ~369-407) into a standalone function `loadActivityChart()`:
   - Read the selected period from the dropdown
   - For 24h: create 24 hourly buckets
   - For 7d: create 7 daily buckets
   - For 30d: create 30 daily buckets
   - Use cached activities data (_activitiesCache) instead of re-fetching

3. Update the activities fetch (line 353):
   - Increase limit from 100 to 500 (to support 30d)
   - Store result in _activitiesCache
   - Call loadActivityChart() instead of inline chart code

Keep the Recent Activity list rendering (top 10) inside the original .then() — only the chart moves out.
```
