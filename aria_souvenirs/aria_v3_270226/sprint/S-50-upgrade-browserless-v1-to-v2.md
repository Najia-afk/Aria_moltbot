# S-50: Upgrade browserless/chrome v1 → ghcr.io/browserless/chromium v2
**Epic:** E20 — Infrastructure Hardening | **Priority:** P1 | **Points:** 1 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

> ⚠️ **P1 — Stale/Unpatched Browser**  
> The `aria-browser` service runs `browserless/chrome:latest` (v1), last pushed **~2 years ago**  
> on Docker Hub. No Chrome updates, no CVE patches, no bug fixes — bot-detection evasion  
> degrades silently and any Chromium CVE from the last 2 years is unaddressed in production.

---

## Problem

The `aria-browser` service is pinned to a dead Docker image:

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `stacks/brain/docker-compose.yml` | 30 | `browserless/chrome:latest@sha256:57d19e...` — v1, frozen ~2 years on Docker Hub | 🔴 Security / stale |

Browserless fully abandoned the `browserless/chrome` Docker Hub repository and migrated all active development to `ghcr.io/browserless/chromium` (v2, GitHub Container Registry). The v1 image will never receive another update.

**Confirmed state of the two repositories:**

| Repository | Last push | Latest tag | Status |
|------------|-----------|------------|--------|
| `browserless/chrome` (Docker Hub) | ~2 years ago | `latest` (=v1.61.1) | 🔴 Frozen — no future updates |
| `ghcr.io/browserless/chromium` (GHCR) | 2 days ago | `v2.42.0` | 🟢 Active — weekly releases |

**Why this is not a breaking change:**  
The v1 `browserless/chrome` self-hosted REST API (`POST /content`, `POST /scrape`, `POST /screenshot`, `?token=` auth) is **fully preserved** in v2's self-hosted docker image. The `/chromium/` URL prefix seen in some v2 docs only applies to the Browserless **cloud/multi-browser** hosted service where they need to distinguish Chrome from Firefox/WebKit. The single-browser self-hosted docker container keeps the flat paths unchanged.

`aria_skills/browser/__init__.py` requires **zero changes**.

---

## Root Cause

| Symptom | Root Cause |
|---------|-----------|
| `browserless/chrome:latest` frozen ~2 years | Browserless team migrated to GHCR for v2; Docker Hub v1 permanently abandoned |
| SHA pinned to old digest | SHA was added for stability but now locks to an unmaintained image |
| Chrome is ~2 years outdated | No image pushes = no Chromium security releases = unpatched CVEs in production |
| Bot-detection evasion degrades over time | Outdated user-agent fingerprint + absent Chromium anti-detection patches |

---

## Fix

### Fix 1 — Replace image in `stacks/brain/docker-compose.yml`

**File:** `stacks/brain/docker-compose.yml`

```yaml
# BEFORE (line 30)
    image: browserless/chrome:latest@sha256:57d19e414d9fe4ae9d2ab12ba768c97f38d51246c5b31af55a009205c136012f

# AFTER
    image: ghcr.io/browserless/chromium:v2.42.0
```

The full `aria-browser` service block after the change (everything else unchanged):
```yaml
  aria-browser:
    image: ghcr.io/browserless/chromium:v2.42.0
    container_name: aria-browser
    restart: unless-stopped
    environment:
      TOKEN: ${BROWSERLESS_TOKEN:-}
      BROWSERLESS_INTERNAL_PORT: ${BROWSERLESS_INTERNAL_PORT:-3000}
    ports:
      - "${BROWSERLESS_PORT:-3000}:${BROWSERLESS_INTERNAL_PORT:-3000}"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:$${BROWSERLESS_INTERNAL_PORT}/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
```

No other files change.

---

## Why Not Other Alternatives?

| Option | Image | Verdict |
|--------|-------|---------|
| Stay on v1 | `browserless/chrome:latest` | ❌ Frozen 2 years — no CVE patches, no Chrome updates |
| Browserless v2 ✅ | `ghcr.io/browserless/chromium:v2.42.0` | ✅ Same API, same vendor, zero skill changes, weekly releases, 11.4M pulls |
| `browserless/chrome:2` (Docker Hub) | Does not exist | ❌ v2 was never published on Docker Hub |
| Playwright Docker | `mcr.microsoft.com/playwright` | ❌ Library only (no REST server), requires full skill rewrite |
| Steel | `ghcr.io/steel-dev/steel` | ❌ Completely different API, requires full skill rewrite |

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Only docker-compose changes — no code layers touched |
| 2 | `stacks/brain/.env` for all secrets/ports | ✅ | Verification uses `$BROWSERLESS_PORT`, `$ARIA_API_PORT` |
| 3 | No hardcoded ports | ✅ | Port mapping stays as `${BROWSERLESS_PORT:-3000}:${BROWSERLESS_INTERNAL_PORT:-3000}` |
| 4 | No `:latest` tags | ✅ | Pin to `v2.42.0` — no SHA, no `:latest` |
| 5 | `aria_skills/browser/__init__.py` must remain untouched | ✅ | REST API is identical between v1 and v2 self-hosted |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `DEPLOYMENT.md` | ~258 | `browserless/chrome:2.18.0` | `ghcr.io/browserless/chromium:v2.42.0` |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. No old v1 image reference remains
grep -n "browserless/chrome" stacks/brain/docker-compose.yml
# EXPECTED: 0 results

# 2. New v2 image is present
grep -n "ghcr.io/browserless/chromium" stacks/brain/docker-compose.yml
# EXPECTED: one line — "    image: ghcr.io/browserless/chromium:v2.42.0"

# 3. No SHA digest in the image line
grep -n "browserless" stacks/brain/docker-compose.yml | grep "@sha256"
# EXPECTED: 0 results

# 4. Environment vars unchanged
grep -A10 "aria-browser:" stacks/brain/docker-compose.yml | grep -E "TOKEN|BROWSERLESS_INTERNAL_PORT|BROWSERLESS_PORT"
# EXPECTED: TOKEN, BROWSERLESS_INTERNAL_PORT, BROWSERLESS_PORT all still present

# 5. Container is up and healthy
docker compose -f stacks/brain/docker-compose.yml ps aria-browser
# EXPECTED: aria-browser is "Up" with health "healthy" (not "starting" or "unhealthy")

# 6. POST /content returns HTTP 200
curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:${BROWSERLESS_PORT:-3000}/content?token=${BROWSERLESS_TOKEN:-}" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
# EXPECTED: 200

# 7. Content body starts with HTML
curl -s -X POST \
  "http://localhost:${BROWSERLESS_PORT:-3000}/content?token=${BROWSERLESS_TOKEN:-}" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' | head -3
# EXPECTED: <!DOCTYPE html> or <html

# 8. POST /screenshot returns valid response (non-empty body)
curl -s -X POST \
  "http://localhost:${BROWSERLESS_PORT:-3000}/screenshot?token=${BROWSERLESS_TOKEN:-}" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' | wc -c
# EXPECTED: > 1000 (PNG bytes)

# 9. aria_skills/browser/__init__.py is unchanged
git diff HEAD -- aria_skills/browser/__init__.py
# EXPECTED: no output (zero diff)

# 10. API still healthy
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-50 browser v2 smoke test"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Navigate to example.com with browser tool
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Use your browser tool to navigate to https://example.com and tell me the page title and the first H1 heading you find.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria returns "Example Domain" as title and H1

# Step 3 — Take a screenshot with browser tool
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Now take a screenshot of https://example.com using your browser tool and confirm whether the screenshot was captured successfully.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms screenshot captured (base64 PNG received, no error)

# Step 4 — Log confirmation
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log a create_activity with action=browser_v2_upgrade_verified, details={\"image\":\"ghcr.io/browserless/chromium:v2.42.0\",\"content_ok\":true,\"screenshot_ok\":true}.","enable_tools":true}' \
  | jq -r '.content // .message // .'

# Step 5 — Reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: what was the risk of running an unpatched 2-year-old Chrome in production? What does upgrading to browserless v2 protect?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on CVE exposure, outdated fingerprint, maintenance risk

# Verify activity logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=browser_v2_upgrade_verified&limit=1" \
  | jq '.[0] | {action, success}'

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-50. Total changes: 1 line in 1 file.**

### Architecture Constraints
- Only `stacks/brain/docker-compose.yml` changes — no Python files, no skills, no API code
- Port from `stacks/brain/.env` → `$BROWSERLESS_PORT`, `$ARIA_API_PORT` in all verifications
- **Do NOT use `:latest`** — pin to the explicit version tag `v2.42.0`
- **Do NOT add a SHA digest** — the version tag is sufficient and allows future tag-based bumps

### Files to Read First
1. `stacks/brain/docker-compose.yml` lines 25-50 — aria-browser service block (confirm current image line + env vars)

### Steps
1. Read `stacks/brain/docker-compose.yml` lines 25-50 to confirm current state
2. Replace image line 30: `browserless/chrome:latest@sha256:57d19e414d9fe4ae9d2ab12ba768c97f38d51246c5b31af55a009205c136012f` → `ghcr.io/browserless/chromium:v2.42.0`
3. Read the same lines again to confirm — verify `TOKEN`, `BROWSERLESS_INTERNAL_PORT`, `BROWSERLESS_PORT` env vars untouched
4. Pull the new image: `set -a && source stacks/brain/.env && set +a && docker compose -f stacks/brain/docker-compose.yml pull aria-browser`
5. Restart the service: `docker compose -f stacks/brain/docker-compose.yml up -d aria-browser`
6. Wait 15 seconds, then check health: `docker compose -f stacks/brain/docker-compose.yml ps aria-browser`
7. Run the verification block (checks 1–10 above)
8. Run the ARIA-to-ARIA integration test (steps 1–5 above)
9. **Update `DEPLOYMENT.md` ~line 258:** replace `browserless/chrome:2.18.0` → `ghcr.io/browserless/chromium:v2.42.0`
10. Update SPRINT_OVERVIEW.md to mark S-50 Done
11. Append lesson to `tasks/lessons.md`

### Hard Constraints Checklist
- [ ] `stacks/brain/docker-compose.yml` is the **only** file changed
- [ ] `aria_skills/browser/__init__.py` — **zero diff** (`git diff HEAD -- aria_skills/browser/__init__.py` → empty)
- [ ] Image tag is `ghcr.io/browserless/chromium:v2.42.0` — no `:latest`, no SHA
- [ ] `TOKEN`, `BROWSERLESS_INTERNAL_PORT`, `BROWSERLESS_PORT` env vars in docker-compose remain unchanged
- [ ] Container healthcheck passes (green) after `up -d`
- [ ] `POST /content` returns HTTP 200 + HTML body
- [ ] `POST /screenshot` returns non-empty response body

### Definition of Done
- [ ] `grep "browserless/chrome" stacks/brain/docker-compose.yml` → 0 results
- [ ] `grep "ghcr.io/browserless/chromium:v2.42.0" stacks/brain/docker-compose.yml` → 1 result
- [ ] `grep "@sha256" stacks/brain/docker-compose.yml | grep browserless` → 0 results
- [ ] `docker compose ps aria-browser` shows `healthy`
- [ ] `curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:${BROWSERLESS_PORT:-3000}/content?token=${BROWSERLESS_TOKEN:-}" -H "Content-Type: application/json" -d '{"url":"https://example.com"}'` → `200`
- [ ] `git diff HEAD -- aria_skills/browser/__init__.py` → empty
- [ ] `curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status` → `"healthy"`
- [ ] `grep "ghcr.io/browserless/chromium:v2.42.0" DEPLOYMENT.md` → 1 result
- [ ] `grep "browserless/chrome:2.18.0" DEPLOYMENT.md` → 0 results
- [ ] `git diff HEAD -- DEPLOYMENT.md` shows browserless image updated
- [ ] ARIA-to-ARIA confirms `/content` and `/screenshot` functional through skill layer
- [ ] SPRINT_OVERVIEW.md updated
- [ ] Lesson appended to `tasks/lessons.md`
