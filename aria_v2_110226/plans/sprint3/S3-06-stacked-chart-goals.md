# S3-06: Create Stacked Bar Chart for Goal Status by Day
**Epic:** E5 — Sprint Board | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
The sprint board needs a visual chart showing goal status distribution over time. No historical visualization exists.

## Root Cause
Sprint board is a new feature — chart is needed for trend analysis.

## Fix

### File: `src/web/templates/sprint_board.html`
Add Chart.js stacked bar chart using data from `/goals/history?days=14` endpoint (S3-02).

```javascript
async function loadGoalChart() {
    const resp = await fetch(`${API_BASE}/goals/history?days=14`);
    const data = await resp.json();
    const labels = data.labels;
    const statuses = ['pending', 'active', 'completed', 'paused', 'cancelled'];
    const colors = { pending:'#ffa726', active:'#42a5f5', completed:'#66bb6a', paused:'#ef5350', cancelled:'#78909c' };
    const datasets = statuses.map(s => ({
        label: s.charAt(0).toUpperCase() + s.slice(1),
        data: labels.map(day => (data.data[day] || {})[s] || 0),
        backgroundColor: colors[s], borderWidth: 0, borderRadius: 2,
    }));
    new Chart(document.getElementById('goalStatusChart').getContext('2d'), {
        type: 'bar', data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position:'bottom', labels:{ color:'#e0e0e0' } }, title: { display:true, text:'Goal Status by Day', color:'#e0e0e0' } },
            scales: { x:{ stacked:true, ticks:{color:'#9e9e9e'}, grid:{color:'rgba(255,255,255,0.05)'} }, y:{ stacked:true, ticks:{color:'#9e9e9e',stepSize:1}, grid:{color:'rgba(255,255,255,0.05)'} } },
        },
    });
}
```

Add canvas: `<div class="chart-container" style="height:300px"><canvas id="goalStatusChart"></canvas></div>`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend fetches from API |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in browser |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S3-02** (history endpoint) and **S3-03** (template) must complete first.

## Verification
```bash
grep 'goalStatusChart' src/web/templates/sprint_board.html
# EXPECTED: canvas element
grep -c 'stacked.*true' src/web/templates/sprint_board.html
# EXPECTED: 2
```

## Prompt for Agent
```
Add stacked bar chart to sprint board template.
FILES: src/web/templates/sprint_board.html, goals.html (Chart.js reference)
STEPS: 1. Add canvas element 2. Write loadGoalChart() 3. Use Chart.js stacked bar 4. Call on DOMContentLoaded
```
