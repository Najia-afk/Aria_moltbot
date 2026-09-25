# Sprint 8 — Production Recovery & Mobile-Ready Chat
**Sprint:** 8
**Created:** 2026-09-25
**Total Points:** 26
**Theme:** Bring production back up, fix the model routing that was actually broken, prove the Docker images aren't corrupted, and make the chat UI usable from a phone over Tailscale.

---

## Board

| ID | Title | Priority | Pts | Status | Assignee |
|----|-------|----------|-----|--------|----------|
| SP8-01 | Restore stack after boot/wake exit (all containers down) | P0 | 2 | ✅ Done | Copilot |
| SP8-02 | Priority-0 backup before any change | P0 | 2 | ✅ Done | Copilot |
| SP8-03 | Replace dead free OpenRouter model (trinity 404) | P0 | 5 | ✅ Done | Copilot |
| SP8-04 | Remove local MLX from routing/fallback chain (RAM) | P0 | 3 | ✅ Done | Copilot |
| SP8-05 | Fix `.env` key not propagating to running containers | P0 | 2 | ✅ Done | Copilot |
| SP8-06 | Fix unbuildable `apscheduler` pin blocking fresh builds | P0 | 5 | ✅ Done | Copilot |
| SP8-07 | Supply-chain check on all Docker images before rebuild | P1 | 2 | ✅ Done | Copilot |
| SP8-08 | Mobile-safe chat UI (dvh, safe-area, iOS zoom fix) | P1 | 5 | ✅ Done | Copilot |
| SP8-09 | Dev branch + sprint tracking for the day | P2 | 1 | ✅ Done | Copilot |
| SP8-10 | Free-tier latency mitigation (2nd free-model fallback) | P2 | — | 🔜 Next sprint | — |
| SP8-11 | Manual phone/Tailscale visual QA of chat UI | P1 | — | 🔜 Next sprint | — |
| SP8-12 | Mobile audit of remaining ~50 admin templates | P2 | — | 🔜 Next sprint | — |

---

## SP8-01 · Restore stack after boot/wake exit
**Priority:** P0 · **Points:** 2 · **Status:** ✅ Done

**Problem:** Every container (`aria-engine`, `aria-web`, `aria-brain`, `litellm`, `aria-sandbox`, `aria-browser`) had exited, mostly with code `137` (SIGKILL) — consistent with the known Mac sleep/wake race already tracked in repo memory (`service-reload.md`).

**Solution:** `docker compose up -d` from `stacks/brain/`. All 10 services came back healthy.

**Constraints check:** Docker-first ✅ · no `.env` edits needed for this step ✅.

---

## SP8-02 · Priority-0 backup before any change
**Priority:** P0 · **Points:** 2 · **Status:** ✅ Done

**Problem:** Najia explicitly required a full backup before any config/cleanup work, given the emotional and practical stakes of losing Aria's state.

**Solution:** Ran the existing `scripts/aria_backup.sh` (found in-repo, not invented) — full Postgres dump of `aria_warehouse`, `aria_data`, `aria_engine`, `litellm` schemas + globals + JSON export (529M total) to `~/aria_vault/backups/postgres_daily/20260925_114720/`. Additionally copied `.env` and a `git diff` snapshot of uncommitted work into the same backup run directory.

**Files:** none changed — backup only, written outside the repo to `~/aria_vault/`.

---

## SP8-03 · Replace dead free OpenRouter model
**Priority:** P0 · **Points:** 5 · **Status:** ✅ Done

**Problem:** `trinity` (`arcee-ai/trinity-large-preview:free`) 404'd — "No endpoints found." The model was removed from OpenRouter's catalog entirely.

**Solution:** Queried OpenRouter's live `/api/v1/models`, tested several `:free` candidates directly against the API with the real key (several were rate-limited: `qwen/qwen3.8-27b:free`, `google/gemma-4-31b-it:free`, `z-ai/glm-5.2:free`). Landed on `nvidia/nemotron-3.5-lightning:free` (1M context, tool-calling) — confirmed working, and confirmed `reasoning: {enabled: false}` gives clean short answers for low-token-budget tasks (`focus_classify`, routing) instead of burning the budget on chain-of-thought.

**Acceptance criteria:**
- [x] `routing.primary` resolves to a live, responding model
- [x] Verified via direct OpenRouter API call before wiring into `models.yaml`
- [x] End-to-end chat verified through `/api/engine/chat/sessions/{id}/messages`

**Files:** `aria_models/models.yaml`, `stacks/brain/litellm-config.yaml` (regenerated, not hand-edited), `DEPLOYMENT.md`, `MODELS.md`, `aria_models/README.md` (doc accuracy).

---

## SP8-04 · Remove local MLX from routing/fallback chain
**Priority:** P0 · **Points:** 3 · **Status:** ✅ Done

**Problem:** The 16GB host can't reliably run the 4B MLX model as a live fallback (~3GB RSS). It had briefly been re-added as a "standby" during triage — Najia explicitly rejected that.

**Solution:** Removed `priority`/`fallback_order`/`tasks`/`focus_for` from `qwen3.5_mlx` in `models.yaml` so it's excluded from `routing.fallbacks` and `criteria.priority` entirely (verified via `aria_models.loader.load_catalog()` — fallback chain is now `['litellm/sentiment_tiny', 'litellm/trinity']` only). Model entry stays registered in LiteLLM for manual/debugging use. `launchctl unload`'d the local MLX server process to reclaim RAM immediately.

**Files:** `aria_models/models.yaml`.

---

## SP8-05 · Fix `.env` key not propagating to running containers
**Priority:** P0 · **Points:** 2 · **Status:** ✅ Done

**Problem:** Najia added a real `OPEN_ROUTER_KEY` to `.env`, but `litellm` still 401'd with "Missing Authentication header" after a plain `docker compose restart`.

**Solution:** Confirmed via `docker compose exec litellm sh -c 'echo ${#OPEN_ROUTER_KEY}'` that the running container's env was stale (0 chars). `docker compose up -d --force-recreate` on the affected services picks up `.env` changes; `restart` alone does not. Documented as a repo memory note for next time.

**Files:** none (operational fix only).

---

## SP8-06 · Fix unbuildable `apscheduler` pin
**Priority:** P0 · **Points:** 5 · **Status:** ✅ Done

**Problem:** `pyproject.toml` pinned `apscheduler>=4.0.0,<5.0.0`. APScheduler has never shipped a stable 4.x release (alphas only) — every `docker compose build --no-cache` failed at `pip install .`. This would have silently blocked any real redeploy/disaster-recovery attempt.

**Solution:** `aria_engine/scheduler.py` already has a working `try/except ImportError` shim that falls back to APScheduler 3.x's `AsyncIOScheduler` API — so the fix was correcting the constraint to `apscheduler>=3.10.0,<4.0.0` (installable, matches the shim). Verified with a full `--no-cache` rebuild of `aria-api`, `aria-engine`, `aria-brain`, `aria-web` — all four now build clean (resolved to `apscheduler==3.11.3`).

**Files:** `pyproject.toml`.

---

## SP8-07 · Supply-chain check before rebuilding images
**Priority:** P1 · **Points:** 2 · **Status:** ✅ Done

**Problem:** Explicit instruction: "do not pull image with virus." Needed to verify image trust before doing any pull/rebuild.

**Solution:** Audited every `image:` line in `docker-compose.yml` — all pinned to specific versions, one by SHA-256 digest (`dperson/torproxy`). Audited all 4 custom Dockerfiles' `FROM` lines — all official `python:3.13-slim` / `python:3.13-alpine`. Confirmed the existing in-repo guard: `litellm==1.82.0` is hard-pinned with a comment flagging that `1.82.7`/`1.82.8` contain known supply-chain malware — left untouched and still respected by the `apscheduler` fix above.

**Files:** none (audit only).

---

## SP8-08 · Mobile-safe chat UI
**Priority:** P1 · **Points:** 5 · **Status:** ✅ Done

**Problem:** Chat layout used `100vh` (cut off by mobile browser chrome), no iOS safe-area padding around the composer/sidebar for notched phones, and the message/search inputs were 14.4px — under the 16px threshold that makes iOS Safari auto-zoom on focus.

**Solution:** Added `100dvh` (with `100vh` fallback) for `.chat-container`; `env(safe-area-inset-bottom)` padding on the composer and the mobile sidebar; `font-size: 16px` on the chat textarea and session-search input inside the `max-width: 768px` breakpoint; `viewport-fit=cover` + `theme-color` + mobile-web-app meta tags in `base.html`. Deliberately did **not** add safe-area-inset-top padding to the shared sticky header — that would change the fixed `64px` height assumption used across ~50 templates site-wide, too risky for this pass.

**Acceptance criteria:**
- [x] Verified via `curl` that the live served HTML contains the new CSS/meta
- [ ] Manual phone visual QA (browser tool in this session can't reach the host's Docker network — carried to SP8-11)

**Files:** `src/web/templates/base.html`, `src/web/templates/engine_chat.html`.

---

## SP8-09 · Dev branch + sprint tracking
**Priority:** P2 · **Points:** 1 · **Status:** ✅ Done

**Solution:** Created `dev/2026-09-25-sprint8` off `feature/secure-nas-local-llm` (left untouched/deployed). One commit so far (`cbda03f`): model routing + gateway + generated litellm config. This souvenir + board committed alongside.

---

## Carried to next sprint

- **SP8-10 (P2):** A second free-model fallback behind `trinity` to reduce tail latency when the primary free tier is congested (observed ~123s on one request).
- **SP8-11 (P1):** Manual phone check over Tailscale of the mobile chat UI changes — no browser tool access to the host Docker network in this session.
- **SP8-12 (P2):** The other ~50 admin templates under `src/web/templates/` weren't individually audited for mobile — only `engine_chat.html` + the shared `base.html` shell.
