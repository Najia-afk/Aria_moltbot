---
name: aria-litellm
description: Manage LiteLLM proxy, models, and API spend tracking.
metadata: {"openclaw": {"emoji": "⚡", "requires": {"env": ["LITELLM_MASTER_KEY"]}}}
---

# aria-litellm

Manage LiteLLM proxy, query available models, track API spend and provider balances.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py litellm <function> '<json_args>'
```

## Functions

### litellm_models
List all available models.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py litellm litellm_models '{}'
```

### litellm_health
Check proxy health.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py litellm litellm_health '{}'
```

### litellm_spend
Get spend logs.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py litellm litellm_spend '{"limit": 20}'
```

### litellm_global_spend
Get total spend summary.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py litellm litellm_global_spend '{}'
```

### provider_balances
Get wallet balances from Kimi and OpenRouter.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py litellm provider_balances '{}'
```

Returns:
```json
{
  "kimi": {"provider": "Moonshot/Kimi", "status": "ok", "available": 17.72, "cash": 0, "voucher": 17.72},
  "openrouter": {"provider": "OpenRouter", "status": "ok", "limit": 10, "usage": 0.3, "remaining": 9.7}
}
```

## API Endpoints

- `GET /litellm/models` - List models
- `GET /litellm/health` - Health check
- `GET /litellm/spend` - Spend logs
- `GET /litellm/global-spend` - Global summary
- `GET /providers/balances` - Provider wallets

## Provider Configuration

| Provider | Env Variable | Currency |
|----------|-------------|----------|
| Kimi/Moonshot | `MOONSHOT_KIMI_KEY` | USD |
| OpenRouter | `OPEN_ROUTER_KEY` | USD |
| Local (MLX/Ollama) | N/A | Free |
