# aria-database

Support level: advanced compatibility (self-healing/recovery path)

Compatibility database skill for recovery-grade operations.

## Purpose
- Provide database-oriented methods in skill form.
- Route supported operations through `api_client` safely.
- Use direct SQL only for diagnostics, migrations, and repair workflows.

## Main Tools
- `log_thought`
- `get_recent_thoughts`
- `store_memory`
- `recall_memory`
- `search_memories`
