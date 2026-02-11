# S1-12: Fix Stale /litellm Link in services.html

**Priority:** Low | **Estimate:** 1 pt | **Status:** TODO

---

## Problem

In `src/web/templates/services.html:317`, the LiteLLM service link in the architecture diagram points to `/litellm`:

```html
<a href="/litellm" class="arch-service checking" data-service="litellm">
    <span class="arch-service-status"></span>
    <div class="arch-service-icon">⚡</div>
    <div class="arch-service-name">LiteLLM</div>
    <div class="arch-service-port">:18793</div>
</a>
```

The `/litellm` route now issues a **301 redirect to `/models`**. Users clicking this link see a visible redirect flash before landing on the Models page, which is a poor UX.

---

## Root Cause

The route was changed from `/litellm` → `/models` (likely in a previous sprint), but the link in the services architecture diagram was not updated to match.

---

## Fix

### Before (`src/web/templates/services.html:317`)

```html
                <a href="/litellm" class="arch-service checking" data-service="litellm">
```

### After

```html
                <a href="/models" class="arch-service checking" data-service="litellm">
```

Only the `href` changes. The `data-service="litellm"` attribute stays as-is — it's used for health-check status polling, not navigation.

---

## Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | Only change the href, not data-service | ✅ data-service used for status checks |
| 2 | No changes to health check logic | ✅ Status polling unaffected |
| 3 | No changes to other LiteLLM references | ✅ Lines 418-419 and 499 are display labels, not links |
| 4 | Jinja2 template compatibility | ✅ Plain HTML attribute change |
| 5 | Works with Traefik routing | ✅ /models is a valid route |
| 6 | No Python backend changes | ✅ Template-only fix |

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| None | — | Standalone fix, no ordering constraints |

---

## Verification

```bash
# 1. Verify the href is updated
grep 'href="/litellm"' src/web/templates/services.html
# Expected: (no output — old link gone)

# 2. Verify new href exists
grep 'href="/models"' src/web/templates/services.html
# Expected: 1 match at the architecture diagram link

# 3. Verify data-service still says litellm (for health checks)
grep 'data-service="litellm"' src/web/templates/services.html
# Expected: 2 matches (architecture diagram + control card)

# 4. Browser test: click LiteLLM in services page
# Expected: Navigates directly to /models (no redirect flash)

# 5. Verify other LiteLLM references unchanged
grep -n "litellm" src/web/templates/services.html | wc -l
# Expected: 7 (same count as before — only href value changed, not removed)
```

---

## Prompt for Agent

```
Read src/web/templates/services.html.

At line 317, there is a link:
  <a href="/litellm" class="arch-service checking" data-service="litellm">

The /litellm route now redirects 301 to /models. Fix the link to point directly to /models:
  <a href="/models" class="arch-service checking" data-service="litellm">

Do NOT change the data-service="litellm" attribute — it's used for health check status polling.
Do NOT change any other LiteLLM references in the file (lines 418-419, 499, 509 are display labels and status check identifiers).

Verify: grep 'href="/litellm"' src/web/templates/services.html should return nothing.
Verify: grep 'href="/models"' src/web/templates/services.html should return 1 match.
```
