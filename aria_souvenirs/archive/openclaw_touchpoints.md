# OpenClaw Touch Points Analysis (S-31)

## Files Referencing OpenClaw / clawdbot

| # | File | Type | Description |
|---|------|------|-------------|
| 1 | stacks/brain/docker-compose.yml:49 | Service | clawdbot container definition |
| 2 | stacks/brain/openclaw-config.json | Config | OpenClaw config template |
| 3 | stacks/brain/openclaw-entrypoint.sh | Script | Container startup + cron injection |
| 4 | aria_models/openclaw_config.py | Python | Config generator (render_openclaw_config) |
| 5 | patch/openclaw_patch.js | JS | Custom patches for OpenClaw |
| 6 | patch/openclaw-litellm-fix.patch | Patch | LiteLLM routing fix |
| 7 | aria_mind/cron_jobs.yaml | YAML | Cron jobs injected by entrypoint.sh |

## Gateway Abstraction (v1.2)
- `aria_mind/gateway.py` — GatewayInterface ABC + OpenClawGateway implementation
- Tracks per-request latency via `get_latency_stats()`

## Metrics to Collect (v1.2)
- **Latency:** gateway.py tracks per-request latency via get_latency_stats()
- **Brave search frequency:** grep Docker logs for "brave" tool calls
- **Tool routing accuracy:** manual review of cron job outputs

## Phase-Out Timeline
- **v1.2 (current):** Customize prompts (S-27), reduce dependency, create abstraction
- **v1.3 (next sprint):** Build NativeGateway with direct LiteLLM + MCP
- **v1.4 (future):** Remove OpenClaw container entirely
