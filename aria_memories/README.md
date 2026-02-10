# Aria's File Memories

This folder contains **file-based artifacts** created by Aria during operation.
These are NOT database records — they are files: research papers, action plans, drafts, exports, etc.

## Folder Structure

```
aria_memories/
├── README.md           # This file
├── archive/            # Historical artifacts (pre-v1.1 sprint, Aria's souvenirs)
│   ├── sprint_v1.1_2026-02-09/   # 37-ticket sprint (PO_LOG, all tickets)
│   ├── aria_souvenirs/            # Aria's wishlists, experience report
│   ├── aria_research/             # Research papers, analyses
│   ├── aria_logs/                 # Operational logs, heartbeats
│   ├── aria_plans/                # Old action plans, coordination docs
│   ├── moltbook/                  # Moltbook archive + full_archive.json
│   ├── old_exports/               # SQL schemas, JSON exports
│   ├── old_ssv/                   # SSV/DeFi audit research
│   └── old_income_ops/            # Income ops schemas
├── drafts/             # Draft content before publishing
├── exports/            # JSON exports, backups, snapshots
├── income_ops/         # Income operations tracking
├── knowledge/          # Learned facts, entity knowledge
├── logs/               # Session logs, heartbeat logs, activity reviews
├── plans/              # Action plans and strategies
└── research/           # Research papers and findings
```

## What goes here vs. Database

| aria_memories/ (Files) | Database (Tables) |
|------------------------|-------------------|
| Research papers (md)   | Key-value memories |
| Action plans           | Thoughts log |
| Draft content          | Goals & tasks |
| Exported data (json)   | Activity log |
| Session logs           | Rate limits |
| Income operations      | Social posts |

## Access from Aria

Aria uses the `memory.py` methods:
```python
# Save markdown artifact
memory.save_artifact(content, "research_v1.md", category="research")

# Save JSON data
memory.save_json_artifact(data, "portfolio_snapshot", category="exports")

# List recent logs
files = memory.list_artifacts(category="logs", pattern="*.md")

# Load artifact
result = memory.load_artifact("action_plan.md", category="plans")
```

## Git Sync

This folder is tracked by git for visibility and backup.
Aria can commit her own changes via the git skill.
