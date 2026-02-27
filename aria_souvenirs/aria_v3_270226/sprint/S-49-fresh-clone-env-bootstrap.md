# S-49: Fresh-Clone Bootstrap — Auto-Generate `.env` When Missing
**Epic:** E20 — Developer Experience & Architecture Compliance | **Priority:** P0 | **Points:** 2 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

> ⚠️ **P0 — Silent Failure on Fresh Clone**  
> A developer who clones the repo and runs `make up` or `docker compose up` without reading the
> README will get a broken stack: **`DB_PASSWORD` is empty, `LITELLM_MASTER_KEY` is empty,
> `WEB_SECRET_KEY` is empty** — containers start but fail auth checks silently.
> The architecture constraint "all ports/secrets from `.env`" is currently only enforced at
> runtime, not at startup.

---

## Problem

Current fresh-clone experience:

```bash
git clone ...
cd aria
make up    # silently starts with DB_PASSWORD= LITELLM_MASTER_KEY= WEB_SECRET_KEY= all empty
           # → PostgreSQL accepts empty password (if pg_hba.conf is trust)
           # → LiteLLM refuses to start (master key required)
           # → aria-web crashes (SECRET_KEY required by Flask)
```

`scripts/first-run.sh` **exists and does exactly the right thing** — copies `.env.example`,
generates `DB_PASSWORD`, `WEB_SECRET_KEY`, `LITELLM_MASTER_KEY`, etc. — but a fresh-clone user
has no reason to know to run it first. The README mentions it, but `make up` has no guard.

**Connection to S-47 and S-48:**  
- S-47 (schema isolation) depends on the `litellm` schema being created at startup — which only
  works if `DB_PASSWORD` / `DATABASE_URL` are correct, which requires a valid `.env`
- S-48 (dynamic port) depends on `LITELLM_PORT` being in `.env` — if `.env` doesn't exist,
  `LITELLM_PORT` falls back to docker-compose hardcode, which may or may not match the template

**What `.env.example` already contains (safe to auto-use):**
- All default ports (`ARIA_API_PORT=8000`, `LITELLM_PORT=18793`, etc.)
- DB username (`DB_USER=admin`)
- All service URLs (Docker network names)
- All optional keys left blank (Moonshot, OpenRouter, Telegram, Molt — Najia fills these herself)

**What needs generation (cannot be blank):**  
`DB_PASSWORD`, `WEB_SECRET_KEY`, `LITELLM_MASTER_KEY`, `GRAFANA_PASSWORD`, `PGADMIN_PASSWORD`,
`ARIA_API_KEY`, `ARIA_ADMIN_KEY`, `BROWSERLESS_TOKEN`

### Problem Table

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `Makefile` | `up` target | No `.env` guard — `make up` starts stack with all secrets empty | 🔴 P0 silent failure |
| `scripts/first-run.sh` | — | No `--auto` flag — always interactive, can't run from Makefile | 🔴 P0 blocks CI/bootstrap |
| `stacks/brain/.env` | — | Absent on fresh clone — `DB_PASSWORD`, `WEB_SECRET_KEY`, `LITELLM_MASTER_KEY` all empty | 🔴 P0 containers fail |

### Root Cause Table

| Symptom | Root Cause |
|---------|------------|
| `docker compose up` starts silently with empty secrets | `Makefile` `up` target has no prerequisite check for `.env` existence |
| Cannot call `first-run.sh` from Makefile non-interactively | `first-run.sh` prompts stdin for overwrite confirmation — no `--auto` bypass |
| LiteLLM refuses to start on fresh clone | `LITELLM_MASTER_KEY=` is blank without a generated `.env` |

---

## Fix

### Fix 1 — Add `--auto` mode to `scripts/first-run.sh`

**File:** `scripts/first-run.sh`

Add non-interactive mode that skips the overwrite prompt and silently exits if `.env` already
exists. Called by `make up` guard. No port randomization in auto mode — use `.env.example` defaults.

```bash
# Add near the top, after variable declarations
AUTO=false
if [[ "${1:-}" == "--auto" ]]; then
    AUTO=true
fi
```

```bash
# Replace the interactive overwrite block:

# BEFORE
if [ -f "$ENV_FILE" ]; then
    warn ".env already exists at $ENV_FILE"
    read -rp "Overwrite? (y/N) " choice
    if [[ ! "$choice" =~ ^[Yy]$ ]]; then
        info "Keeping existing .env. Exiting."
        exit 0
    fi
    cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d%H%M%S)"
    info "Backed up existing .env"
fi

# AFTER
if [ -f "$ENV_FILE" ]; then
    if [[ "$AUTO" == "true" ]]; then
        info ".env already exists — skipping auto-bootstrap."
        exit 0
    fi
    warn ".env already exists at $ENV_FILE"
    read -rp "Overwrite? (y/N) " choice
    if [[ ! "$choice" =~ ^[Yy]$ ]]; then
        info "Keeping existing .env. Exiting."
        exit 0
    fi
    cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d%H%M%S)"
    info "Backed up existing .env"
fi
```

```bash
# Wrap port randomization in interactive-only guard (auto mode keeps .env.example defaults):

# BEFORE
info "Randomizing host-exposed ports..."
ARIA_API_PORT=$(random_port)
...

# AFTER
if [[ "$AUTO" == "false" ]]; then
    info "Randomizing host-exposed ports..."
    ARIA_API_PORT=$(random_port)
    ...
    # (all fill_env port calls stay inside this block)
else
    info "Auto mode: using default ports from .env.example"
fi
```

### Fix 2 — Add `check-env` target to `Makefile`

**File:** `Makefile`

```makefile
# ============================================================================
# Environment Bootstrap
# ============================================================================

.PHONY: check-env

check-env: ## Auto-bootstrap stacks/brain/.env from .env.example if missing
	@if [ ! -f stacks/brain/.env ]; then \
		echo "[INFO] stacks/brain/.env not found — auto-bootstrapping from .env.example..."; \
		bash scripts/first-run.sh --auto; \
		echo "[INFO] .env created. Edit stacks/brain/.env to add private API keys."; \
	fi

up: check-env ## Start all services
	$(COMPOSE) up -d
```

### Fix 3 — Add inline guard comment to `docker-compose.yml`

**File:** `stacks/brain/docker-compose.yml`

Add a comment at the top of the file, just after the opening line:

```yaml
# ──────────────────────────────────────────────────────────────────────────────
# FRESH CLONE? Run: bash scripts/first-run.sh
# Or just:    make up   (auto-bootstraps .env from .env.example on first run)
# Private tokens (API keys) must be added manually to stacks/brain/.env
# ──────────────────────────────────────────────────────────────────────────────
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Config/bootstrap layer only |
| 2 | `stacks/brain/.env` for all secrets/ports | ✅ | **This ticket creates it when missing** |
| 3 | No hardcoded secrets in code | ✅ | `.env.example` has only empty or dev-mode values |
| 4 | Private tokens never committed | ✅ | `MOONSHOT_KIMI_KEY`, `OPEN_ROUTER_KEY`, `TELEGRAM_BOT_TOKEN` stay blank in auto mode |
| 5 | No direct SQL | ✅ | N/A |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `README.md` | `first-run.sh` section (~lines 40-45) | Only describes interactive usage — no `--auto` flag documented | Add `./scripts/first-run.sh --auto` usage for CI/fresh-clone bootstrapping |
| `DEPLOYMENT.md` | Fresh clone / quick-start section | No mention of `check-env` Makefile target or `--auto` mode | Add `make check-env` and `first-run.sh --auto` to deployment bootstrap instructions |

---

## What auto-bootstrap produces (safe, no private data)

| Variable | Source | Value in auto mode |
|----------|--------|-------------------|
| `DB_PASSWORD` | Generated | `secrets.token_urlsafe(32)` |
| `WEB_SECRET_KEY` | Generated | `secrets.token_urlsafe(32)` |
| `LITELLM_MASTER_KEY` | Generated | `sk-aria-<random>` |
| `GRAFANA_PASSWORD` | Generated | `secrets.token_urlsafe(32)` |
| `PGADMIN_PASSWORD` | Generated | `secrets.token_urlsafe(32)` |
| `ARIA_API_KEY` | Generated | `secrets.token_urlsafe(32)` |
| `ARIA_ADMIN_KEY` | Generated | `secrets.token_urlsafe(32)` |
| `ARIA_API_PORT` | .env.example | `8000` |
| `LITELLM_PORT` | .env.example | `18793` |
| `ARIA_WEB_PORT` | .env.example | `5050` |
| `MOONSHOT_KIMI_KEY` | .env.example | `` (empty — user fills) |
| `OPEN_ROUTER_KEY` | .env.example | `` (empty — user fills) |
| `TELEGRAM_BOT_TOKEN` | .env.example | `` (empty — user fills) |
| All other private tokens | .env.example | `` (empty — user fills) |

**Zero private data committed or auto-filled. ✅**

---

## Verification

```bash
# 1. Rename .env temporarily to test the guard
mv stacks/brain/.env stacks/brain/.env.real

# 2. Run make up — should auto-bootstrap
make up 2>&1 | head -20
# EXPECTED: "[INFO] stacks/brain/.env not found — auto-bootstrapping from .env.example..."
#           "[INFO] .env created. Edit stacks/brain/.env to add private API keys."

# 3. .env was created
ls -la stacks/brain/.env
# EXPECTED: file exists

# 4. REQUIRED secrets are not empty
grep -E "^DB_PASSWORD=|^WEB_SECRET_KEY=|^LITELLM_MASTER_KEY=" stacks/brain/.env
# EXPECTED: all 3 have values (not empty)

# 5. Private tokens ARE empty (safe)
grep -E "^MOONSHOT_KIMI_KEY=|^OPEN_ROUTER_KEY=|^TELEGRAM_BOT_TOKEN=" stacks/brain/.env
# EXPECTED: all 3 empty (=)

# 6. Running make up a second time does NOT re-bootstrap (idempotent)
make up 2>&1 | grep "auto-bootstrapping"
# EXPECTED: no output (already exists)

# 7. API comes up healthy after auto-bootstrapped .env
set -a && source stacks/brain/.env && set +a
sleep 10
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"

# 8. Restore real .env
mv stacks/brain/.env.real stacks/brain/.env
make up
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-49 env bootstrap review"}' \
  | jq -r '.id')

# Step 2 — Ask Aria to review the bootstrap mechanism
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read scripts/first-run.sh. Does it support --auto mode (non-interactive, skips overwrite prompt, keeps .env.example default ports)? Read Makefile — does the up target depend on check-env?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms --auto flag in first-run.sh, up depends on check-env in Makefile

# Step 3 — Ask Aria about what a fresh clone gets
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read stacks/brain/.env.example. Tell me: (1) Which fields are blank that auto-bootstrap fills in? (2) Which fields stay blank because they are private tokens that only Najia has? (3) Would a fresh clone produce a working stack with auto-bootstrap?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria identifies DB_PASSWORD/WEB_SECRET_KEY/LITELLM_MASTER_KEY as auto-filled;
#           MOONSHOT_KIMI_KEY/OPEN_ROUTER_KEY/TELEGRAM_BOT_TOKEN as intentionally empty

# Step 4 — Log completion
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log create_activity: action=env_bootstrap_s49_verified, details={\"auto_mode\":true,\"private_tokens_empty\":true,\"required_secrets_generated\":true}.","enable_tools":true}' \
  | jq -r '.content // .message // .'

# Step 5 — Reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: What does zero-friction fresh-clone mean for a project like this? How does auto-bootstrapping reduce the barrier to someone contributing to Aria?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on contributor accessibility, trust in defaults, and separation of operational secrets

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-49. Total changes: 2 files.**

### Architecture Constraints
- `stacks/brain/.env` must always contain real secrets before containers start — this ticket ensures it
- Never write private tokens to `.env.example` or generate them automatically
- `--auto` mode must be **idempotent**: if `.env` already exists, do nothing
- Port randomization only happens in interactive mode — auto mode uses `.env.example` defaults

### Files to Read First
1. `scripts/first-run.sh` — full file (239 lines) — understand current flow
2. `Makefile` — full file (92 lines) — understand current targets
3. `stacks/brain/.env.example` — lines 1-20 and the PORTS section (~line 115) — understand what auto mode should copy vs generate
4. `stacks/brain/docker-compose.yml` — first 10 lines — to add the comment

### Steps — first-run.sh
1. After the variable declarations block, add `AUTO=false` + `if [[ "${1:-}" == "--auto" ]]; then AUTO=true; fi`
2. In the "`.env` already exists" block: if `AUTO=true`, `info ".env already exists — skipping."` + `exit 0`
3. Wrap the port randomization block (`random_port` calls + `fill_env` for port vars) inside `if [[ "$AUTO" == "false" ]]; then ... fi`
4. Leave all secret generation (`fill_env "DB_PASSWORD"` etc.) **outside** the guard — always generate secrets in both modes

### Steps — Makefile
5. Add `check-env` target with the `@if [ ! -f stacks/brain/.env ]` guard above the Docker section
6. Change `up: ## Start all services` → `up: check-env ## Start all services`

### Steps — docker-compose.yml
7. Add the 4-line FRESH CLONE comment block at the very top of `stacks/brain/docker-compose.yml` (after line 1)

### Steps — Wrap Up
8. Run verification block (rename `.env`, run `make up`, check keys non-empty, check private tokens empty, restore)
9. Run ARIA-to-ARIA integration test
10. **Update `README.md`** first-run.sh section (~lines 40-45): document `./scripts/first-run.sh --auto` usage — "Use `--auto` for CI or fresh-clone bootstrap: generates secrets, skips interactive port randomization, idempotent (safe to re-run)"
11. **Update `DEPLOYMENT.md`** bootstrap/quick-start section: add `make check-env` as a step before `make up`, note `first-run.sh --auto` for non-interactive environments
12. Update SPRINT_OVERVIEW.md to mark S-49 Done
13. Append lesson to `tasks/lessons.md`

### Hard Constraints Checklist
- [ ] `--auto` mode is idempotent — never overwrites existing `.env`
- [ ] Port randomization ONLY in interactive mode (auto uses `.env.example` defaults — predictable for CI)
- [ ] All REQUIRED secrets generated in both modes
- [ ] `MOONSHOT_KIMI_KEY`, `OPEN_ROUTER_KEY`, `TELEGRAM_BOT_TOKEN` remain empty after auto-bootstrap ✓
- [ ] `Makefile` `up` depends on `check-env`
- [ ] No change to `.env.example` itself — it is the source of truth, never modified

### Definition of Done
- [ ] `first-run.sh --auto` exits 0 with no interactive prompts when no `.env` exists
- [ ] `first-run.sh --auto` exits 0 immediately if `.env` already exists (idempotent)
- [ ] `make up` (no `.env`) → auto-bootstraps, then starts stack
- [ ] `grep -E "^DB_PASSWORD=.+" stacks/brain/.env` → has value after auto-bootstrap
- [ ] `grep -E "^MOONSHOT_KIMI_KEY=$" stacks/brain/.env` → empty (private token untouched)
- [ ] `curl http://localhost:${ARIA_API_PORT}/health | jq .status` → "healthy" after fresh auto-bootstrap
- [ ] `grep "\-\-auto" README.md` → 1+ matches in first-run.sh section
- [ ] `grep "check-env\|--auto" DEPLOYMENT.md` → matches in bootstrap section
- [ ] `git diff HEAD -- README.md` shows `--auto` flag documented
- [ ] `git diff HEAD -- DEPLOYMENT.md` shows check-env/auto-bootstrap instructions added
- [ ] ARIA-to-ARIA confirms mechanism, logs `env_bootstrap_s49_verified`
- [ ] SPRINT_OVERVIEW.md updated
