# aria-health

System health monitoring for Aria services. Check connectivity to database, LLM, and external APIs.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py health <function> '<json_args>'
```

## Functions

### check_all
Run health checks on all services and return summary.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py health check_all '{}'
```

**Returns:**
```json
{
  "status": "healthy",
  "services": {
    "database": {"status": "up", "latency_ms": 5},
    "ollama": {"status": "up", "model": "qwen3-vl:8b"},
    "litellm": {"status": "up"},
    "moltbook": {"status": "up"}
  }
}
```

### check_service
Check a specific service.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py health check_service '{"service": "database"}'
```

**Available services:**
- `database` - PostgreSQL connection
- `ollama` - Local LLM (Qwen3-VL)
- `litellm` - LLM proxy/router
- `moltbook` - Moltbook API

### get_metrics
Get system resource usage.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py health get_metrics '{}'
```

## Service Endpoints

| Service | Internal URL |
|---------|--------------|
| Database | `postgres://aria_warehouse:5432` |
| Ollama | `http://host.docker.internal:11434` |
| LiteLLM | `http://litellm:4000` |
| Moltbook | `https://www.moltbook.com/api/v1` |

## Python Module

This skill wraps `/root/.openclaw/workspace/skills/aria_skills/health.py`
