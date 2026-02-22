# RT-08: Sessions Admin — No Bulk-Delete Ghost Sessions View

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P2 🟠 | **Points:** 3 | **Phase:** 3

---

## Roundtable Exchange

**SM:** The admin sessions page (`/sessions`) has individual delete buttons but no way
to mass-clear ghost sessions. Shiva has to delete them one by one.

**Aria (PO):** Add a "Clean up ghosts" button on the sessions admin page that calls
`DELETE /api/engine/sessions/ghosts` and reports how many were deleted with a toast.
Also expose a "Ghost sessions" count in the stats cards so we can monitor it.

Acceptance:
1. Stats card shows "Ghost sessions (0 msg)" count in red if > 0
2. "🧹 Clean Ghosts" button calls the purge endpoint and shows result toast
3. Ghost count refreshes after cleanup

---

## Problem

`src/web/templates/sessions.html` has stats cards but none showing `message_count = 0` count.
No bulk-action exists for ghost cleanup. The purge endpoint (added in RT-01/RT-05) exists
but is not surfaced in the UI.

---

## Root Cause

Frontend was built before ghost detection was identified as an issue.
Purely a UI gap — backend already supports `DELETE /sessions/ghosts`.

---

## Fix Plan

### Stats card — add ghost count
```javascript
// In loadSessionDashboard() JS, add ghost count query:
const ghostRes = await fetch('/api/engine/sessions?limit=1&message_count_max=0');
const ghostCount = ghostRes.ok ? (await ghostRes.json()).total : '?';
document.getElementById('ghost-count').textContent = ghostCount;
```

```html
<!-- Add to .stats-grid: -->
<div class="stat-card red" id="ghost-card">
    <h4>Ghost Sessions</h4>
    <div class="value" id="ghost-count">-</div>
    <div class="stats-sub">0 messages — never used</div>
</div>
```

### Clean Ghosts button
```html
<button class="btn btn-danger btn-sm" onclick="cleanGhosts()" title="Delete all 0-message sessions">
    🧹 Clean Ghosts
</button>
```

```javascript
async function cleanGhosts() {
    const res = await fetch('/api/engine/sessions/ghosts?older_than_minutes=0', {method: 'DELETE'});
    const data = await res.json();
    showToast(`Cleaned ${data.deleted} ghost sessions`, 'success');
    loadSessionDashboard();
}
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend calls API — no direct DB |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Browser test |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Verify ghost count appears in stats:
# Open /sessions page — stats grid should show "Ghost Sessions" card with number

# 2. Click "Clean Ghosts" — toast appears:
# Browser: click button → toast "Cleaned N ghost sessions"
# Stats card should refresh to 0
```

---

## Prompt for Agent

Read: `src/web/templates/sessions.html` lines 1–200 (stats grid + controls section).

Steps:
1. Add "Ghost Sessions" stat card (red) to `.stats-grid`
2. Add "🧹 Clean Ghosts" button to `.page-controls`
3. Add `cleanGhosts()` JS function
4. Wire ghost count into `loadSessionDashboard()`

Constraints: 4 (browser test). Dependencies: RT-01/RT-05 (ghost purge endpoint must exist first).
