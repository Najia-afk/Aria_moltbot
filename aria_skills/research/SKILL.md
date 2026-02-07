---
name: aria-research
description: "📰 Research and information gathering for Journalist"
metadata: {"openclaw": {"emoji": "📰"}}
---

# aria-research

Research and information gathering. Create projects, add sources, take notes, generate questions, assess source quality, synthesize findings, and generate bibliographies.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research <function> '<json_args>'
```

## Functions

### create_project
Create a new research project.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research create_project '{"topic": "AI safety"}'
```

### add_source
Add a source to a research project.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research add_source '{"project_id": "abc", "url": "https://example.com"}'
```

### add_note
Add a research note.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research add_note '{"project_id": "abc", "content": "Key finding..."}'
```

### generate_questions
Generate research questions (surface, medium, deep).

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research generate_questions '{"project_id": "abc"}'
```

### assess_sources
Assess source quality and coverage.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research assess_sources '{"project_id": "abc"}'
```

### synthesize
Synthesize research into a summary.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research synthesize '{"project_id": "abc"}'
```

### get_bibliography
Generate bibliography (apa, mla, chicago).

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py research get_bibliography '{"project_id": "abc", "format": "apa"}'
```
