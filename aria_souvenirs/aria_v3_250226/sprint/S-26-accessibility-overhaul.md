# S-26: Accessibility Overhaul — ARIA Labels, Keyboard Nav, Focus
**Epic:** E14 — Frontend Quality | **Priority:** P0 | **Points:** 5 | **Phase:** 2

## Problem
The web interface is nearly inaccessible to keyboard-only and screen reader users:

1. **Only 1 `aria-label` in the entire codebase** — `base.html` L352 for the hamburger menu toggle. No other ARIA attributes across 43 templates.

2. **Keyboard-inaccessible dropdown navigation** — `base.html` L134-349: Drop-down menus are `:hover`-only CSS. No keyboard handler for Enter/Space/Arrow keys. Dropdown buttons lack `aria-expanded` and `aria-haspopup`.

3. **No skip navigation link** — No "Skip to content" link for keyboard users to bypass the 50+ nav links.

4. **Color-only status indicators** — `base.html` L455-461 uses colored dots without text labels. `engine_agent_dashboard.html` L15-22 uses green/yellow/red cards with no accessible labels.

5. **No `:focus-visible` outlines** — `base.css` has no global `:focus-visible` rules. Interactive elements are invisible to keyboard navigators.

## Root Cause
Accessibility was not part of the original development requirements.

## Fix

### Fix 1: Add skip navigation link
**File:** `src/web/templates/base.html` L120 (before nav)
```html
<a href="#main-content" class="skip-nav">Skip to content</a>
```
**File:** `src/web/static/css/base.css`
```css
.skip-nav {
    position: absolute;
    top: -40px;
    left: 0;
    padding: 8px 16px;
    background: var(--accent-primary);
    color: white;
    z-index: 9999;
    transition: top 0.2s;
}
.skip-nav:focus {
    top: 0;
}
```

### Fix 2: Keyboard-accessible dropdowns
**File:** `src/web/templates/base.html` — update all dropdown toggles:
```html
<button class="nav-dropdown-toggle" 
        aria-haspopup="true" 
        aria-expanded="false"
        aria-controls="dropdown-memory">
    Memory <span class="dropdown-arrow">▼</span>
</button>
<ul id="dropdown-memory" class="nav-dropdown" role="menu">
    <li role="menuitem"><a href="/memories">Memories</a></li>
    ...
</ul>
```

**File:** `src/web/static/js/aria-common.js` — add keyboard handler:
```javascript
document.querySelectorAll('.nav-dropdown-toggle').forEach(btn => {
    btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
            e.preventDefault();
            const menu = document.getElementById(btn.getAttribute('aria-controls'));
            const expanded = btn.getAttribute('aria-expanded') === 'true';
            btn.setAttribute('aria-expanded', !expanded);
            menu.hidden = expanded;
            if (!expanded) menu.querySelector('a')?.focus();
        }
    });
});
```

### Fix 3: Add aria-labels to icon buttons
Search all templates for buttons with only icons (no visible text):
```html
<!-- BEFORE -->
<button onclick="reload()">🔄</button>

<!-- AFTER -->
<button onclick="reload()" aria-label="Refresh data">🔄</button>
```

### Fix 4: Add text labels to status indicators
**File:** `src/web/templates/base.html` L455-461
```html
<!-- BEFORE -->
<span class="status-dot status-online"></span>

<!-- AFTER -->
<span class="status-dot status-online" role="status">
    <span class="sr-only">Online</span>
</span>
```

### Fix 5: Add focus-visible styles
**File:** `src/web/static/css/base.css`
```css
:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}

/* Remove default outline for mouse users */
:focus:not(:focus-visible) {
    outline: none;
}
```

### Fix 6: Add aria-live regions for dynamic content
For all auto-refreshing content areas:
```html
<div id="sessions-list" aria-live="polite" aria-atomic="false">
    <!-- Updated content -->
</div>
```

### Fix 7: Add role="alert" to error displays
Ensure `showErrorState()` in `aria-common.js` adds `role="alert"`:
```javascript
function showErrorState(container, message, retryFn) {
    container.setAttribute('role', 'alert');
    // ... existing logic
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend only |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-05/S-06/S-07 (nav regrouping) should be done FIRST — no point adding ARIA to nav that's about to be restructured.

## Verification
```bash
# 1. Skip nav link exists:
grep 'skip-nav' src/web/templates/base.html
# EXPECTED: Skip to content link

# 2. All dropdowns have aria attributes:
grep -c 'aria-expanded' src/web/templates/base.html
# EXPECTED: ≥ 10 (one per dropdown)

# 3. Focus-visible styles:
grep 'focus-visible' src/web/static/css/base.css
# EXPECTED: Global :focus-visible rule

# 4. Icon buttons have labels:
grep -rn '<button' src/web/templates/ --include='*.html' | grep -v 'aria-label' | grep -v '>[A-Za-z]'
# EXPECTED: Minimal matches (all icon-only buttons should have aria-label)

# 5. Manual keyboard test:
# Tab through the page — every interactive element should be reachable
# Enter/Space on dropdown toggles should open/close menus
# Escape should close open menus
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/templates/base.html (L100-L500 — full nav + status indicators)
- src/web/static/css/base.css (full)
- src/web/static/js/aria-common.js (full)
- src/web/static/css/components.css (focus-related rules)

CONSTRAINTS: Follow WCAG 2.1 AA guidelines. Don't break existing visual design.

STEPS:
1. Add .skip-nav link and CSS to base.html + base.css
2. Add id="main-content" to the main content wrapper
3. Update ALL dropdown toggles with aria-haspopup, aria-expanded, aria-controls
4. Add keyboard event handlers for dropdowns (Enter, Space, ArrowDown, Escape)
5. Add :focus-visible global styles to base.css
6. Add .sr-only utility class to base.css
7. Search ALL templates for icon-only buttons → add aria-label
8. Add text labels to status dots with .sr-only
9. Add aria-live="polite" to auto-refreshing content regions
10. Update showErrorState() with role="alert"
11. Test with keyboard navigation through the full nav
```
