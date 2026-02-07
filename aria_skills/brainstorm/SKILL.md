---
name: aria-brainstorm
description: "🎨 Creative brainstorming and ideation for Creative Adventurer"
metadata: {"openclaw": {"emoji": "🎨"}}
---

# aria-brainstorm

Creative brainstorming and ideation skill. Start sessions, add ideas, apply techniques (SCAMPER, Six Hats, etc.), and evaluate results.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm <function> '<json_args>'
```

## Functions

### start_session
Start a new brainstorming session.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm start_session '{"topic": "new feature ideas"}'
```

### add_idea
Add an idea to a session.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm add_idea '{"session_id": "abc", "idea": "use AI for search", "category": "tech"}'
```

### apply_technique
Apply a brainstorming technique (scamper, six_hats, random_word, worst_idea).

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm apply_technique '{"session_id": "abc", "technique": "scamper"}'
```

### get_random_prompt
Get a random creative prompt.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm get_random_prompt '{}'
```

### connect_ideas
Find connections between ideas.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm connect_ideas '{"session_id": "abc"}'
```

### evaluate_ideas
Evaluate and rank ideas.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm evaluate_ideas '{"session_id": "abc"}'
```

### summarize_session
Get a summary of a brainstorming session.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm summarize_session '{"session_id": "abc"}'
```
