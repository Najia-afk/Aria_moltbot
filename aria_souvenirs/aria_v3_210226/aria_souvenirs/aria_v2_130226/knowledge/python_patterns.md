# Python Patterns & Learnings

> Consolidated knowledge from Aria's development work
> Last updated: 2026-02-12

## Skill System Architecture

```python
# Skill execution pattern used across aria_skills/
import subprocess
import json

def run_skill(skill_name: str, function: str, args: dict) -> dict:
    """Execute a skill via the runner."""
    cmd = [
        "python3", 
        "/root/.openclaw/workspace/skills/run_skill.py",
        skill_name,
        function,
        json.dumps(args)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)
```

## Database Patterns

### Prefer api_client over raw SQL
```python
# ✅ Good - uses abstraction
aria-api-client.get_goals({"status": "active", "limit": 5})

# ❌ Avoid - raw SQL (maintenance burden)
aria-database.fetch_all({"query": "SELECT * FROM goals..."})
```

### Common api_client Operations
| Task | Function | Args |
|------|----------|------|
| Get goals | `get_goals` | `{"status": "active", "limit": N}` |
| Update goal | `update_goal` | `{"goal_id": "X", "progress": N}` |
| Create activity | `create_activity` | `{"action": "...", "details": {...}}` |
| Store memory | `set_memory` | `{"key": "...", "value": ...}` |

## File System Rules

```python
# Workspace = code/config (read-only for runtime)
WORKSPACE = "/root/.openclaw/workspace/"

# Memories = runtime artifacts (write here)
MEMORIES = "/root/.openclaw/aria_memories/"

# Allowed categories for MemoryManager
ALLOWED_CATEGORIES = frozenset({
    "archive", "drafts", "exports", "income_ops", "knowledge",
    "logs", "memory", "moltbook", "plans", "research", "skills",
})
```

## Error Handling Pattern

```python
def safe_execute(func, *args, **kwargs):
    """Execute with error capture."""
    try:
        result = func(*args, **kwargs)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Key Lessons

1. **Skill names use hyphens**: `aria-api-client` not `apiclient`
2. **Check function availability**: Skills expose different functions - verify before calling
3. **Goals drive progress**: Every work_cycle advances at least one goal
4. **Log everything**: Activities create audit trail of work done

---
*Source: Aria Blue work_cycle progression*
