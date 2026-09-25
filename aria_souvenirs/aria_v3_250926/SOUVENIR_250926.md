# Aria v3 Souvenir — 2026-09-25

## Context

Production had gone dark: the whole Docker stack (`aria-engine`, `aria-web`, `aria-brain`, `litellm`, `aria-sandbox`, etc.) had exited (mostly `137`/SIGKILL, consistent with the known boot/wake race already noted in `service-reload` history). Najia asked for a full recovery pass — bring Aria back up, find a working free OpenRouter model, harden the config, back everything up first, and refresh the chat UI for phone + PC — using subagent-style focused investigation, a scrum sprint doc, and a dedicated dev branch.

## What was actually wrong (root causes)

1. **Dead free model.** `arcee-ai/trinity-large-preview:free` — the model wired as Aria's primary/fallback free chat model — no longer exists on OpenRouter (`404 No endpoints found`). Confirmed live against OpenRouter's `/api/v1/models` catalog.
2. **Empty key.** `OPEN_ROUTER_KEY` / `OPEN_ROUTER_KEY_DEEP` / `MOONSHOT_KIMI_KEY` were all empty in `stacks/brain/.env`. Najia added a real `OPEN_ROUTER_KEY`, but the running `litellm`/`aria-api` containers didn't pick it up — `docker compose restart` does **not** reload `.env`-sourced variables; it took a `--force-recreate` to actually inject the new key into the container environment.
3. **Local MLX was never a safe fallback.** The host is a small 16GB Mac Mini; running the 4B MLX model as a live "standby" fallback held ~3GB RSS the machine can't spare. Removed entirely from routing.
4. **A silent, unbuildable dependency pin.** `pyproject.toml` required `apscheduler>=4.0.0,<5.0.0` — APScheduler 4.x has never had a stable PyPI release (alphas only). Every fresh `docker compose build --no-cache` failed at `pip install .`. The *running* container only worked because it was built before/without this constraint; a real redeploy from a clean clone would have failed outright. `aria_engine/scheduler.py` already has a working 3.x compatibility shim, so the fix was pinning to the installable `apscheduler>=3.10.0,<4.0.0` line instead.
5. **Chat UI mobile gaps.** `100vh` layout height (doesn't account for mobile browser chrome), no iOS safe-area padding on the composer/sidebar, and a 14.4px input font that triggers iOS Safari's auto-zoom on focus.

## What changed

| Area | Change |
|---|---|
| `aria_models/models.yaml` | `trinity` repointed to `nvidia/nemotron-3.5-lightning:free` (1M ctx, tool-calling, verified live) with reasoning disabled by default for fast task profiles. `qwen3.5_mlx` fully removed from routing/fallback (no `priority`/`fallback_order`/`tasks`) — still registered in LiteLLM for manual use only. `sentiment_tiny` (Ollama `qwen2.5:0.5b`, ~0.5GB) is now the only resident local model. Comments trimmed to one factual line each. |
| `aria_engine/llm_gateway.py` | Coalesce multiple `system`-role messages into one leading system message (some OpenAI-compatible backends reject >1 system message / non-leading system messages). |
| `pyproject.toml` | `apscheduler` constraint fixed from an unbuildable `>=4.0.0,<5.0.0` to `>=3.10.0,<4.0.0`, matching the existing 3.x shim in `scheduler.py`. |
| `stacks/brain/litellm-config.yaml` | Regenerated from `models.yaml` via `scripts/generate_litellm_config.py` (never hand-edited). |
| `DEPLOYMENT.md`, `MODELS.md`, `aria_models/README.md` | Stale "Trinity 400B MoE" description corrected to reflect the actual live free model. |
| `src/web/templates/base.html` | `viewport-fit=cover`, `theme-color`, and mobile-web-app meta tags added. |
| `src/web/templates/engine_chat.html` | `100dvh` layout height (with `100vh` fallback), `env(safe-area-inset-bottom)` padding on the composer and sidebar for notched phones, and `font-size: 16px` on mobile inputs (chat box + session search) to stop iOS Safari's auto-zoom-on-focus. |

## Verification

- **Backup first, always.** Ran `scripts/aria_backup.sh` before touching anything: full Postgres dump (`aria_warehouse`, `aria_data`, `aria_engine`, `litellm`, globals, JSON export — 529M total) to `~/aria_vault/backups/postgres_daily/20260925_114720/`, plus a copy of `.env` and the uncommitted diff at that point in time.
- **Chat verified end-to-end**: `POST /api/engine/chat/sessions/{id}/messages` → real completion via the new free model (`{"content":"Hello! How can I assist you today?", ...}`, `cost_usd: 0.0`). Latency ~123s on this request — free-tier OpenRouter congestion, not a defect.
- **Fresh build proven**: `docker compose build --no-cache` for `aria-api`, `aria-engine`, `aria-brain`, `aria-web` now succeeds from a clean Docker cache (previously impossible — see root cause #4). All four containers redeployed and passed health checks.
- **Supply-chain check**: every pulled image in `docker-compose.yml` is pinned to a specific version (several by digest); all 4 custom-built images derive from official `python:3.13-slim`/`alpine`. `litellm` stays hard-pinned to `1.82.0` per the existing in-repo note that `1.82.7`/`1.82.8` contain supply-chain malware.
- **DB integrity check**: row counts across `aria_data`/`aria_engine` schemas sane post-recovery (`agent_state=11`, `chat_sessions=4`, `skill_graph_entities=354`, etc.) — nothing corrupted.
- **RAM reclaimed**: local MLX server (`com.aria.mlx-server`) unloaded via `launchctl` — ~3GB RSS freed since it's no longer in the fallback chain.
- Mobile CSS changes confirmed present in the live served HTML (`curl http://localhost:5050/chat/` shows `dvh`, `safe-area-inset`, `viewport-fit=cover`).

## What's still open (carried to next sprint)

- Free-tier OpenRouter latency (~2 min on a cold request) may need a provider-routing hint or a second free-model fallback for snappier replies.
- No visual/browser QA was possible in this session (the sandboxed browser tool can't reach the host's Docker network) — a manual phone check over Tailscale is recommended before calling the UI refresh fully done.
- Full site-wide mobile audit only covered the chat page (`engine_chat.html`) and the shared `base.html` shell; the other ~50 admin templates weren't individually reviewed.

## Branches

- `dev/2026-09-25-sprint8` — all of today's work, branched from `feature/secure-nas-local-llm` (which stayed untouched as the last-known-good deployed branch).
