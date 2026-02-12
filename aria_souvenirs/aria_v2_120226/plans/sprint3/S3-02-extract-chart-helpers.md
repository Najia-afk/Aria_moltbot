# S3-02: Extract Shared Chart Helper Functions
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
Three chart-related functions are duplicated:

| Function | Duplicated In | Copies |
|----------|--------------|--------|
| `renderChart` | sessions.html, model_usage.html, performance.html | 3 |
| `renderOverview` | sessions.html, model_usage.html | 2 |
| `drawGraph` | skill_graph.html, knowledge.html | 2 |

These functions create Chart.js charts with similar patterns but slightly different configurations. They should be extracted into a shared `chart-helpers.js` module.

## Root Cause
Chart.js integration was done per-page with copy-paste patterns. No shared charting abstraction existed.

## Fix
Create `src/web/static/js/chart-helpers.js` with parameterized chart creation functions:

```javascript
/**
 * Create a Chart.js chart with standard Aria styling.
 * @param {string} canvasId - Canvas element ID
 * @param {string} type - Chart type (bar, line, doughnut, etc.)
 * @param {object} data - Chart.js data object
 * @param {object} [options] - Chart.js options override
 * @returns {Chart} Chart instance
 */
function createAriaChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { color: '#e0e0e0' } }
        },
        scales: type !== 'doughnut' ? {
            x: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
            y: { ticks: { color: '#aaa' }, grid: { color: '#333' } }
        } : undefined
    };
    
    return new Chart(ctx, {
        type,
        data,
        options: { ...defaultOptions, ...options }
    });
}
```

Then replace inline `renderChart`/`renderOverview`/`drawGraph` in each template with calls to the shared helper.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Verify charts render after changes |
| 5 | aria_memories writable | ❌ | Code changes only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S3-01 should complete first (establishes pattern for shared JS extraction).

## Verification
```bash
# 1. Chart helpers file exists:
ls -la src/web/static/js/chart-helpers.js
# EXPECTED: file exists

# 2. Architecture check — fewer chart duplicates:
python3 scripts/check_architecture.py 2>&1 | grep "DUP_JS.*renderChart\|DUP_JS.*renderOverview\|DUP_JS.*drawGraph"
# EXPECTED: no output (duplicates removed)

# 3. Templates include chart-helpers.js:
for tmpl in sessions model_usage performance skill_graph knowledge; do
  grep -l "chart-helpers.js" "src/web/templates/${tmpl}.html" 2>/dev/null && echo "  ✅ $tmpl" || echo "  ❌ $tmpl"
done
# EXPECTED: all ✅

# 4. Pages with charts load:
for page in sessions model-usage performance knowledge; do
  curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000/$page"
done
# EXPECTED: all 200
```

## Prompt for Agent
```
Extract chart helper functions into a shared chart-helpers.js module.

**Files to read:**
- src/web/templates/sessions.html (search for renderChart, renderOverview)
- src/web/templates/model_usage.html (search for renderChart, renderOverview, loadAll)
- src/web/templates/performance.html (search for renderChart)
- src/web/templates/skill_graph.html (search for drawGraph)
- src/web/templates/knowledge.html (search for drawGraph)

**Constraints:** Docker-first testing.

**Steps:**
1. Read each template to find the chart function implementations
2. Create src/web/static/js/chart-helpers.js with parameterized helpers
3. Replace inline functions in each template with shared helper calls
4. Add <script src="/static/js/chart-helpers.js"></script> to affected templates
5. Verify charts still render on each page
```
