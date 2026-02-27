# S-48: Browser Uses Hardcoded LiteLLM Port `:18793` Instead of `$LITELLM_PORT`
**Epic:** E20 — Architecture Compliance | **Priority:** P0 | **Points:** 2 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

> ⚠️ **P0 — Architecture Violation**  
> `index.html` hardcodes `:18793` for the LiteLLM link. If `LITELLM_PORT` is changed in `.env`
> the browser link silently breaks — same class of issue as every other hardcoded port already
> fixed in this sprint.

---

## Problem

**Bug 1 — `index.html:354` hardcodes LiteLLM port**

```html
<!-- index.html line 354 -->
<a href="http://{{ request.host.split(':')[0] }}:18793" target="_blank" class="service-card">
```

`18793` is hard-coded. It should come from `LITELLM_PORT` via the Flask context processor —
exactly the same pattern used for `ARIA_API_PORT` → `api_port`.

**Bug 2 — `LITELLM_PORT` not passed to `aria-web` container**

`stacks/brain/docker-compose.yml` injects `ARIA_API_PORT` into the `aria-web` env (line 422)
but **never injects `LITELLM_PORT`**:

```yaml
# aria-web env (lines 410-428) — LITELLM_PORT is absent
environment:
  SECRET_KEY: ${WEB_SECRET_KEY:-aria-dev-secret-key}
  ...
  ARIA_API_PORT: ${ARIA_API_PORT:-8000}   ← present
  # LITELLM_PORT: ???                     ← MISSING
```

**Bug 3 — `app.py` context_processor doesn't inject `litellm_port`**

```python
# app.py lines 48-56 — litellm_port absent
@app.context_processor
def inject_config():
    return {
        'service_host': service_host,
        'api_base_url': api_base_url,
        'ws_base_url': _ws_base_url,
        'ws_api_key': _api_key,
        'api_port': _api_port,      ← present
        # litellm_port              ← MISSING
        'build_ts': _build_ts,
    }
```

**Bonus cosmetic — `services.html:321` also hardcodes `:18793` in the display label**

```html
<!-- services.html line 321 — just a display label, non-functional but inconsistent -->
<div class="arch-service-port">:18793</div>
```

This doesn't control any navigation but shows a stale value if the port changes.

### Problem Table

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `src/web/templates/index.html` | 354 | `:18793` hardcoded — breaks when `LITELLM_PORT` changes in `.env` | 🔴 P0 Architecture violation |
| `stacks/brain/docker-compose.yml` | ~422 | `LITELLM_PORT` absent from aria-web environment block | 🔴 P0 Architecture violation |
| `src/web/app.py` | ~52 | `litellm_port` not injected in context_processor return dict | 🔴 P0 Architecture violation |
| `src/web/templates/services.html` | 321 | `:18793` hardcoded in display label — cosmetically stale | ⚠️ Low |

### Root Cause Table

| Symptom | Root Cause |
|---------|------------|
| LiteLLM link breaks when port is different from 18793 | `index.html` uses `:18793` literal instead of `{{ litellm_port }}` Jinja2 variable |
| `LITELLM_PORT` env var not visible in Flask container | `docker-compose.yml` passes `ARIA_API_PORT` to aria-web but omits `LITELLM_PORT` |
| `{{ litellm_port }}` would resolve empty even if added to template | `app.py` context_processor dict doesn't include `litellm_port` key |

---

## Fix

### Fix 1 — Add `LITELLM_PORT` to `aria-web` environment in docker-compose

**File:** `stacks/brain/docker-compose.yml`

```yaml
# BEFORE (aria-web env, after ARIA_API_PORT line)
      ARIA_API_PORT: ${ARIA_API_PORT:-8000}
      # Internal API URL for server-to-server calls (Docker network)

# AFTER
      ARIA_API_PORT: ${ARIA_API_PORT:-8000}
      LITELLM_PORT: ${LITELLM_PORT:-18793}
      # Internal API URL for server-to-server calls (Docker network)
```

### Fix 2 — Read `LITELLM_PORT` in `app.py` and inject into context_processor

**File:** `src/web/app.py`

```python
# BEFORE (line ~44)
    # Host-exposed API port (for browser-side WS fallback)
    _api_port = os.environ.get('ARIA_API_PORT', '8000')

# AFTER
    # Host-exposed API port (for browser-side WS fallback)
    _api_port = os.environ.get('ARIA_API_PORT', '8000')
    # LiteLLM external port (for browser-side model router link)
    _litellm_port = os.environ.get('LITELLM_PORT', '18793')
```

```python
# BEFORE context_processor return dict
        return {
            'service_host': service_host,
            'api_base_url': api_base_url,
            'ws_base_url': _ws_base_url,
            'ws_api_key': _api_key,
            'api_port': _api_port,
            'build_ts': _build_ts,
        }

# AFTER
        return {
            'service_host': service_host,
            'api_base_url': api_base_url,
            'ws_base_url': _ws_base_url,
            'ws_api_key': _api_key,
            'api_port': _api_port,
            'litellm_port': _litellm_port,
            'build_ts': _build_ts,
        }
```

### Fix 3 — Use `{{ litellm_port }}` in `index.html`

**File:** `src/web/templates/index.html`

```html
<!-- BEFORE (line 354) -->
<a href="http://{{ request.host.split(':')[0] }}:18793" target="_blank" class="service-card">

<!-- AFTER -->
<a href="http://{{ request.host.split(':')[0] }}:{{ litellm_port }}" target="_blank" class="service-card">
```

### Fix 4 (cosmetic) — Use `{{ litellm_port }}` in `services.html` display label

**File:** `src/web/templates/services.html`

```html
<!-- BEFORE (line 321) -->
<div class="arch-service-port">:18793</div>

<!-- AFTER -->
<div class="arch-service-port">:{{ litellm_port }}</div>
```

---

## Fresh Clone Dependency

> **Prerequisite: S-49** — the dynamic port fix in this ticket reads `LITELLM_PORT` from
> `stacks/brain/.env`. On a fresh clone with no `.env`, `LITELLM_PORT` is absent and the
> docker-compose default `:18793` is used — the template variable `{{ litellm_port }}` falls
> back to `'18793'` in `app.py`, which happens to still work. But in a randomised port setup
> (S-49 interactive mode), the `.env` must exist before `aria-web` starts or the port will
> be stale. S-49 guarantees `.env` exists before `make up` starts the stack.

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Change in Config/Web layer |
| 2 | All ports/secrets from `stacks/brain/.env` → env vars | ✅ | This is EXACTLY the constraint being fixed |
| 3 | No direct SQL | ✅ | Not applicable |
| 4 | No hardcoded ports in any layer | ✅ | Root constraint this ticket enforces |
| 5 | `aria_memories/` only writable path for Aria | ✅ | Not applicable |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `DEPLOYMENT.md` | aria-web env section | `LITELLM_PORT` not listed as a configurable env var for aria-web | Add `LITELLM_PORT: ${LITELLM_PORT:-18793}` to the aria-web environment variable documentation |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. LITELLM_PORT is passed to aria-web in docker-compose
grep -n "LITELLM_PORT" stacks/brain/docker-compose.yml | grep -v "^.*litellm:"
# EXPECTED: at least one match in the aria-web environment block (not just the litellm service)

# 2. app.py reads LITELLM_PORT
grep -n "LITELLM_PORT\|litellm_port" src/web/app.py
# EXPECTED: _litellm_port = os.environ.get('LITELLM_PORT', ...) AND 'litellm_port' in context_processor

# 3. index.html no longer hardcodes 18793
grep -n "18793" src/web/templates/index.html
# EXPECTED: 0 lines

# 4. index.html uses litellm_port template var
grep -n "litellm_port" src/web/templates/index.html
# EXPECTED: 1 match in the LiteLLM service card href

# 5. services.html display label updated
grep -n "litellm_port" src/web/templates/services.html
# EXPECTED: 1 match (arch-service-port div)

# 6. API healthy
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"

# 7. Web dashboard responding
curl -sS "http://localhost:${ARIA_WEB_PORT:-5050}/" -o /dev/null -w "%{http_code}"
# EXPECTED: 200

# 8. Rendered port in live HTML matches env var
curl -sS "http://localhost:${ARIA_WEB_PORT:-5050}/" \
  | grep -o ":[0-9]*.*LiteLLM\|LiteLLM.*:[0-9]*" | head -3
# EXPECTED: shows ${LITELLM_PORT} value, not hardcoded 18793 (unless LITELLM_PORT=18793 in .env)
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-48 dynamic port audit"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Ask Aria to audit the fix
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read src/web/app.py. Does the context_processor now inject litellm_port? What value does it fall back to if LITELLM_PORT env var is not set?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms litellm_port in context_processor, fallback is '18793'

# Step 3 — Ask Aria to check index.html
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read src/web/templates/index.html around the LiteLLM service card. Is port 18793 still hardcoded, or does it now use {{ litellm_port }}?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms {{ litellm_port }} is used, no hardcoded 18793

# Step 4 — Ask Aria to check docker-compose
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read stacks/brain/docker-compose.yml aria-web environment section. Is LITELLM_PORT listed alongside ARIA_API_PORT?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms LITELLM_PORT in aria-web env block

# Step 5 — Ask about architecture compliance
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Scan src/web/templates/ for any remaining hardcoded port numbers (like 8000, 5000, 5432, 3000, 9090, 3001) that appear in href or src attributes (functional uses, not display labels). Are there any left?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reports findings — any remaining functional hardcoded ports are new P0 candidates

# Step 6 — Log result
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log create_activity with action=port_hardcode_s48_fixed, details={\"file\":\"index.html\",\"port_var\":\"LITELLM_PORT\",\"was_hardcoded\":18793}.","enable_tools":true}' \
  | jq -r '.content // .message // .'

# Step 7 — Reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: What is the pattern for adding a new external port to the browser dashboard? What are the 3 places that must always be changed together?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria articulates the 3-place pattern: docker-compose aria-web env + app.py + template

# Verify activity
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=port_hardcode_s48_fixed&limit=1" \
  | jq '.[0] | {action, success}'

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-48. Total changes: 4 files, 5 line edits.**

### Architecture Constraints
- Port from `stacks/brain/.env` → env var → docker-compose env → Flask `os.environ.get` → Jinja2 `{{ var }}` — **this is the ONLY allowed chain**
- Never hardcode any port number in a template or app.py
- `aria_memories/` only writable path for Aria's files — not applicable here (server code only)

### Files to Read First
1. `stacks/brain/docker-compose.yml` — lines 404-445 (aria-web environment section)
2. `src/web/app.py` — lines 30-60 (env reads + context_processor)
3. `src/web/templates/index.html` — line 354 (LiteLLM service card)
4. `src/web/templates/services.html` — line 321 (LiteLLM display port)
5. `stacks/brain/.env` — confirm `LITELLM_PORT` exists

### Steps
1. Read all 5 files
2. `stacks/brain/docker-compose.yml`: add `LITELLM_PORT: ${LITELLM_PORT:-18793}` to aria-web env, immediately after the `ARIA_API_PORT` line
3. `src/web/app.py`: add `_litellm_port = os.environ.get('LITELLM_PORT', '18793')` after the `_api_port` line; add `'litellm_port': _litellm_port,` to context_processor return dict
4. `src/web/templates/index.html` line 354: replace `:18793` with `:{{ litellm_port }}`
5. `src/web/templates/services.html` line 321: replace `:18793` with `:{{ litellm_port }}`
6. Restart `aria-web` container (or it will pick up template changes via volume mount)
7. Run verification block
8. Run ARIA-to-ARIA integration test (Step 5 specifically — Aria scans for other hardcoded ports)
9. **Update `DEPLOYMENT.md`** aria-web service env section: document `LITELLM_PORT: ${LITELLM_PORT:-18793}` as a new configurable env var
10. Update SPRINT_OVERVIEW.md S-48 to Done
11. Append lesson to `tasks/lessons.md`: "3-place pattern for adding external port to browser dashboard: docker-compose aria-web env → app.py os.environ.get → Jinja2 {{ var }}"

### Hard Constraints Checklist
- [ ] `grep "18793" src/web/templates/index.html | wc -l` → 0
- [ ] `grep "18793" src/web/templates/services.html | wc -l` → 0 (display label updated)
- [ ] `LITELLM_PORT` present in aria-web environment in docker-compose
- [ ] `litellm_port` in app.py context_processor return dict
- [ ] No other functional hardcoded ports found by Aria in Step 5 scan (or new ticket filed if found)

### Definition of Done
- [ ] `grep "18793" src/web/templates/index.html` → 0 results
- [ ] `grep "LITELLM_PORT" stacks/brain/docker-compose.yml | grep -v "^.*litellm:"` → match in aria-web block
- [ ] `grep "litellm_port" src/web/app.py` → 2 matches (read + inject)
- [ ] `grep "litellm_port" src/web/templates/index.html` → 1 match
- [ ] `grep "LITELLM_PORT" DEPLOYMENT.md` → match in aria-web env documentation
- [ ] `git diff HEAD -- DEPLOYMENT.md` shows LITELLM_PORT added to aria-web section
- [ ] `curl http://localhost:${ARIA_WEB_PORT:-5050}/` returns HTTP 200
- [ ] ARIA-to-ARIA confirms dynamic port, logs activity, scans for remaining hardcoded ports
- [ ] SPRINT_OVERVIEW.md updated
