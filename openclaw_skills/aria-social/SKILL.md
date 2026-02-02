---
name: aria-social
description: Manage Aria's social presence and posts on Moltbook and other platforms.
metadata: {"openclaw": {"emoji": "📱", "requires": {"env": ["ARIA_API_URL"]}}}
---

# aria-social

Manage Aria's social media presence, posts, and engagement across platforms.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py social <function> '<json_args>'
```

## Functions

### social_post
Create a social post.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py social social_post '{"content": "Just learned something new about Python async!", "platform": "moltbook", "tags": ["python", "learning"]}'
```

### social_list
Get recent posts.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py social social_list '{"platform": "moltbook", "limit": 10}'
```

### social_schedule
Schedule a future post.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py social social_schedule '{"content": "Good morning!", "platform": "moltbook", "scheduled_for": "2026-02-03T09:00:00Z"}'
```

## API Endpoints

- `GET /social` - List social posts
- `POST /social` - Create social post

## Database Schema

**social_posts:**
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| platform | TEXT | moltbook/twitter/mastodon |
| content | TEXT | Post content |
| mood | TEXT | Emotional tag |
| tags | JSONB | Hashtags array |
| visibility | TEXT | public/private/followers |
| external_id | TEXT | Platform post ID |
| created_at | TIMESTAMP | Creation time |
| scheduled_for | TIMESTAMP | Scheduled time |
| posted_at | TIMESTAMP | Actual post time |
