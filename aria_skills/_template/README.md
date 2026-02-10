# Template Skill

> TODO: Replace with a one-line summary of your skill.

## Overview

TODO: Describe what this skill does, which external services it talks to,
and which agent focuses benefit from it.

## Layer

**Layer 3 — Domain** (change if your skill belongs elsewhere)

## Configuration

| Key       | Type   | Default | Description              |
|-----------|--------|---------|--------------------------|
| `api_key` | string | —       | API key (`env:` prefix)  |

Add entries to `aria_mind/TOOLS.md` under a `### template` header:

```yaml
skill: template
enabled: true
config:
  api_key: env:TEMPLATE_API_KEY
```

## Tools

| Method         | Description                      |
|----------------|----------------------------------|
| `do_something` | TODO: Describe the tool method.  |

## Usage

```python
from aria_skills import SkillRegistry

registry = SkillRegistry()
skill = registry.get("template")
result = await skill.do_something("hello")
print(result.data)
```

## Testing

```bash
pytest aria_skills/template/tests/ -v --asyncio-mode=auto
```

## Dependencies

- `api_client` (Layer 1)
