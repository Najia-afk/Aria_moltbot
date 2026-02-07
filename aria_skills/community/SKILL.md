---
name: aria-community
description: "🌐 Community management and growth for Social Architect"
metadata: {"openclaw": {"emoji": "🌐"}}
---

# aria-community

Community management and growth. Track members, record engagement, identify champions, create campaigns, and plan content.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community <function> '<json_args>'
```

## Functions

### track_member
Add or update a community member.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community track_member '{"member_id": "user123"}'
```

### record_engagement
Record member engagement activity.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community record_engagement '{"member_id": "user123", "activity": "post"}'
```

### get_community_health
Get overall community health metrics.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community get_community_health '{}'
```

### identify_champions
Identify top community champions.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community identify_champions '{}'
```

### create_campaign
Create a community campaign.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community create_campaign '{"name": "weekly challenge", "type": "engagement"}'
```

### get_growth_strategies
Get community growth strategies.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community get_growth_strategies '{}'
```

### generate_content_calendar
Generate a content calendar.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py community generate_content_calendar '{}'
```
