# Aria's File Memories

This folder contains **file-based artifacts** created by Aria during operation.
These are NOT database records - they are files: research papers, action plans, drafts, exports, etc.

## What goes here vs. Database

| aria_memories/ (Files) | Database (Tables) |
|------------------------|-------------------|
| Research papers (md)   | Key-value memories |
| Action plans           | Thoughts log |
| Draft content          | Goals & tasks |
| Exported data (json)   | Activity log |
| Session logs           | Rate limits |
| Income operations      | Social posts |

## Folder Structure

```
aria_memories/
├── README.md           # This file
├── logs/               # Session logs, heartbeat logs, activity reviews
│   ├── heartbeat_*.md
│   ├── hourly_goal_*.md
│   └── activity_*_review_*.md
├── research/           # Research papers and findings
├── plans/              # Action plans and strategies
├── drafts/             # Draft content before publishing
├── exports/            # JSON exports, backups, snapshots
├── income_ops/         # Income operations tracking
└── knowledge/          # Knowledge base articles
```

## Access from OpenClaw/Aria

Inside the clawdbot container, aria_memories is mounted at:
- **Primary**: `/root/.openclaw/aria_memories`  
- **Via repo**: `/root/repo/aria_memories`

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
