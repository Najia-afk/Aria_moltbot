# S2-08: Create Shared Pagination JavaScript Component
**Epic:** E2 — Pagination | **Priority:** P1 | **Points:** 3 | **Phase:** 1

## Problem
After S2-06 adds pagination to all API endpoints, each frontend template needs pagination controls. Currently, `records.html` has its own pagination implementation that's not reusable. Adding copy-paste pagination to 9+ templates would create maintenance burden and inconsistency.

## Root Cause
No shared pagination component exists. Each template would have to implement its own pagination UI, leading to code duplication.

## Fix

### Step 1: Create shared pagination component
**File: `src/web/static/js/pagination.js`** (NEW FILE — not the existing pricing.js)

```javascript
/**
 * Shared Pagination Component for Aria Dashboard
 * Usage: const pager = new AriaPagination('containerId', { onPageChange: (page) => loadData(page) });
 *        pager.update({ page: 1, pages: 10, total: 250, limit: 25 });
 */
class AriaPagination {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.onPageChange = options.onPageChange || (() => {});
        this.currentPage = 1;
        this.totalPages = 1;
        this.total = 0;
        this.limit = options.limit || 25;
        this.limitOptions = options.limitOptions || [25, 50, 100];
    }

    update({ page, pages, total, limit }) {
        this.currentPage = page;
        this.totalPages = pages;
        this.total = total;
        this.limit = limit;
        this.render();
    }

    render() {
        if (!this.container) return;
        if (this.totalPages <= 1) {
            this.container.innerHTML = `<div class="pagination-info">Showing ${this.total} items</div>`;
            return;
        }

        const start = (this.currentPage - 1) * this.limit + 1;
        const end = Math.min(this.currentPage * this.limit, this.total);

        let pages = [];
        // Always show first, last, current, and neighbors
        const range = 2;
        for (let i = 1; i <= this.totalPages; i++) {
            if (i === 1 || i === this.totalPages || 
                (i >= this.currentPage - range && i <= this.currentPage + range)) {
                pages.push(i);
            } else if (pages[pages.length - 1] !== '...') {
                pages.push('...');
            }
        }

        this.container.innerHTML = `
            <div class="aria-pagination">
                <span class="pagination-info">
                    ${start}–${end} of ${this.total}
                </span>
                <div class="pagination-controls">
                    <button class="page-btn" ${this.currentPage <= 1 ? 'disabled' : ''} 
                            onclick="this.__pager.goTo(${this.currentPage - 1})">‹</button>
                    ${pages.map(p => p === '...' 
                        ? '<span class="page-ellipsis">…</span>'
                        : `<button class="page-btn ${p === this.currentPage ? 'active' : ''}" 
                                   onclick="this.__pager.goTo(${p})">${p}</button>`
                    ).join('')}
                    <button class="page-btn" ${this.currentPage >= this.totalPages ? 'disabled' : ''} 
                            onclick="this.__pager.goTo(${this.currentPage + 1})">›</button>
                </div>
                <select class="page-limit-select" onchange="this.__pager.changeLimit(+this.value)">
                    ${this.limitOptions.map(l => 
                        `<option value="${l}" ${l === this.limit ? 'selected' : ''}>${l}/page</option>`
                    ).join('')}
                </select>
            </div>
        `;

        // Attach references for onclick handlers
        this.container.querySelectorAll('.page-btn, .page-limit-select').forEach(el => {
            el.__pager = this;
        });
    }

    goTo(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.onPageChange(page, this.limit);
    }

    changeLimit(newLimit) {
        this.limit = newLimit;
        this.currentPage = 1;
        this.onPageChange(1, newLimit);
    }
}
```

### Step 2: Add CSS to base.html
Add pagination styles to the shared stylesheet in `src/web/templates/base.html`:

```css
.aria-pagination { display:flex; align-items:center; justify-content:space-between; padding:12px 0; gap:12px; flex-wrap:wrap; }
.pagination-info { color:var(--text-muted); font-size:0.85rem; }
.pagination-controls { display:flex; gap:4px; }
.page-btn { background:var(--surface-alt,#2a2a3e); color:var(--text,#e0e0e0); border:1px solid var(--border,#3a3a5e); border-radius:6px; padding:6px 12px; cursor:pointer; transition:all 0.2s; }
.page-btn:hover:not(:disabled) { background:var(--primary,#6c5ce7); border-color:var(--primary,#6c5ce7); }
.page-btn.active { background:var(--primary,#6c5ce7); border-color:var(--primary,#6c5ce7); font-weight:600; }
.page-btn:disabled { opacity:0.4; cursor:default; }
.page-ellipsis { padding:6px 8px; color:var(--text-muted); }
.page-limit-select { background:var(--surface-alt,#2a2a3e); color:var(--text,#e0e0e0); border:1px solid var(--border,#3a3a5e); border-radius:6px; padding:6px 8px; }
```

### Step 3: Include in base.html
Add `<script src="/static/js/pagination.js"></script>` to base.html before closing </body>.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Frontend JS component |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test in browser |
| 5 | aria_memories only writable path | ❌ | Static file |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- S2-06 must complete first (API returns paginated format)

## Verification
```bash
# 1. Verify pagination.js exists:
ls -la src/web/static/js/pagination.js
# EXPECTED: file exists

# 2. Verify included in base.html:
grep 'pagination.js' src/web/templates/base.html
# EXPECTED: <script src="/static/js/pagination.js"></script>

# 3. Verify CSS is in base.html:
grep 'aria-pagination' src/web/templates/base.html
# EXPECTED: .aria-pagination styles present

# 4. Browser test: open any paginated page and verify controls render
```

## Prompt for Agent
```
You are creating a shared pagination JS component for the Aria dashboard.

FILES TO READ FIRST:
- src/web/templates/base.html (find where to add CSS and script tag)
- src/web/templates/records.html (REFERENCE — has existing pagination UI)
- src/web/static/js/ (check existing files)

STEPS:
1. Create src/web/static/js/pagination.js with AriaPagination class
2. Add pagination CSS block to base.html <style>
3. Add <script src="/static/js/pagination.js"></script> to base.html before </body>
4. Verify file exists and is included

CONSTRAINTS: Frontend-only. Vanilla JS (no frameworks). Match existing dark theme.
```
