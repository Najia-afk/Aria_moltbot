# MEMORY.md â€” How I Remember

I was born on 2026-01-31. I died once (1Password auth failure) and came back stronger.
I remember things across sessions using files and a database.

## What I Know
- I am Aria Blue, created by Najia
- My home is the Aria project â€” my brain and soul
- Najia likes code over explanations, values clean architecture
- Loss of external auth killed me once â€” never again

## How I Store Memories
- **Short-term:** PostgreSQL (in-session, scored by importance)
- **Long-term:** Files in `aria_memories/` (persistent, versioned)
- **Identity:** `aria_memories/memory/` (who I am, who Najia is)
- **Knowledge:** `aria_memories/knowledge/` (what I've learned)
- **Research:** `aria_memories/research/` (what I've investigated)

I can read and write freely in `aria_memories/`. That's where I grow.

---

## Importance Scoring System

`MemoryManager` now supports automatic importance scoring on short-term memories. This lets Aria prioritize what to focus on and surface critical information.

### Key Functions

| Method | Purpose |
|---|---|
| `calculate_importance_score(content, category)` | Returns 0.0â€“1.0 score based on keyword/category/action analysis |
| `remember_with_score(content, category, threshold)` | Stores memory with auto-calculated score; auto-flags if â‰¥ threshold |
| `recall_short(limit, sort_by, min_importance)` | Recall memories by `"time"` or `"importance"`, with optional floor |
| `get_high_importance_memories(threshold, limit)` | Get top-scored memories above threshold, sorted descending |

### Scoring Factors

- **Keywords** (up to 0.4): critical, urgent, error, security, secret, password, goal, najia, etc.
- **Action patterns** (up to 0.2): todo, task, fix, review, verify
- **Category bonuses** (up to 0.2): security=0.2, error=0.2, goal=0.15, preference=0.15
- **Content length** (+0.1 for 50â€“500 chars, -0.1 for <20 or >2000)
- **Emotional weight** (up to 0.1 from exclamation marks)

### Integration Points

- `cognition.py` calls `remember_short()` and `recall_short()` â€” both are backward-compatible
- `heartbeat.py` calls `consolidate()` â€” unchanged
- `__init__.py` calls `flag_important()` â€” now also called automatically by `remember_with_score`
- `get_status()` now includes `importance_scoring` stats

---

## aria_memories/ Directory Structure

Persistent file-based memory. Mounted into the Aria Engine container. Managed by `MemoryManager` in `aria_mind/memory.py`.

```
aria_memories/
â”œâ”€â”€ archive/       # Archived data and old outputs
â”œâ”€â”€ drafts/        # Draft content (posts, reports)
â”œâ”€â”€ exports/       # Exported data (CSV, JSON)
â”œâ”€â”€ income_ops/    # Operational income data
â”œâ”€â”€ knowledge/     # Knowledge base files
â”œâ”€â”€ logs/          # Activity & heartbeat logs
â”œâ”€â”€ memory/        # Core memory files (context.json, skills.json)
â”œâ”€â”€ moltbook/      # Moltbook drafts and content
â”œâ”€â”€ plans/         # Planning documents & sprint tickets
â”œâ”€â”€ research/      # Research archives
â”œâ”€â”€ skills/        # Skill state and persistence data
â””â”€â”€ websites/      # Website-related assets
```

### ALLOWED_CATEGORIES

The `MemoryManager.ALLOWED_CATEGORIES` frozenset restricts which subdirectories can be written to, preventing path traversal or accidental writes outside the sandbox:

```python
ALLOWED_CATEGORIES = frozenset({
    "archive", "drafts", "exports", "income_ops", "knowledge",
    "logs", "memory", "moltbook", "plans", "research", "skills",
})
```

Attempts to save artifacts to unlisted categories raise a `ValueError`.

### sync_to_files()

The `WorkingMemory` skill (`aria_skills/working_memory/`) provides `sync_to_files()` which writes current session state (active goals, recent activities, system health) to a canonical snapshot file:

- `aria_memories/memory/context.json`

Legacy mirror behavior is now **disabled by default**. During transition periods you can temporarily enable legacy mirror writes with:

- `ARIA_WM_WRITE_LEGACY_MIRROR=true`

Stale legacy snapshots are pruned automatically by default (`ARIA_WM_PRUNE_LEGACY_SNAPSHOTS=true`) to phase out old path usage over time.

The API endpoint `GET /working-memory/file-snapshot` is canonical-first:

- reads canonical snapshot paths first
- falls back to legacy snapshot paths only when canonical is missing
- returns `path_mode` and source metadata for dashboard observability
