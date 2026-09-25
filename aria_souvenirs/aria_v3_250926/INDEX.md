# Aria v3 Souvenir — 2026-09-25

## What's Here

### Main Souvenir
- **[SOUVENIR_250926.md](SOUVENIR_250926.md)** — Production recovery: dead free model swap, unbuildable dependency fix, RAM/fallback cleanup, priority-0 backup, mobile chat UI hardening

### Sprint Records
- **[SPRINT_8_BOARD.md](SPRINT_8_BOARD.md)** — Sprint 8: Production Recovery & Mobile-Ready Chat (9/9 in-scope tickets done, 3 carried to next sprint)

### Aria's Files (copied for preservation)
- **[aria_files/code/](aria_files/code/)** — Snapshot of modified files: `models.yaml`, `llm_gateway.py`, `pyproject.toml`, `engine_chat.html`

### Ticket Summary

| ID | Title | Status |
|----|-------|--------|
| SP8-01 | Restore stack after boot/wake exit | ✅ Done |
| SP8-02 | Priority-0 backup before any change | ✅ Done |
| SP8-03 | Replace dead free OpenRouter model (trinity 404) | ✅ Done |
| SP8-04 | Remove local MLX from routing/fallback chain | ✅ Done |
| SP8-05 | Fix `.env` key not propagating to running containers | ✅ Done |
| SP8-06 | Fix unbuildable `apscheduler` pin | ✅ Done |
| SP8-07 | Supply-chain check before rebuilding images | ✅ Done |
| SP8-08 | Mobile-safe chat UI | ✅ Done |
| SP8-09 | Dev branch + sprint tracking | ✅ Done |
| SP8-10 | Free-tier latency mitigation | 🔜 Next sprint |
| SP8-11 | Manual phone/Tailscale visual QA | 🔜 Next sprint |
| SP8-12 | Mobile audit of remaining admin templates | 🔜 Next sprint |

### Branch
- `dev/2026-09-25-sprint8` (off `feature/secure-nas-local-llm`)

### Files Modified
- `aria_models/models.yaml` — SP8-03 + SP8-04 (free model swap, local MLX removed from routing)
- `aria_engine/llm_gateway.py` — system-message coalescing for OpenAI-compatible backend compat
- `stacks/brain/litellm-config.yaml` — regenerated from `models.yaml`
- `pyproject.toml` — SP8-06 (apscheduler constraint fix)
- `src/web/templates/base.html` + `engine_chat.html` — SP8-08 (mobile-safe chat UI)
- `DEPLOYMENT.md`, `MODELS.md`, `aria_models/README.md` — doc accuracy for the model rename
