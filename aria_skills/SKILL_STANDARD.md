# Aria Skill Standard v2.0

## 5-Layer Hierarchy

| Layer | Name | Description | Examples |
|-------|------|-------------|----------|
| 0 | Kernel | Read-only identity & security | input_guard |
| 1 | API Client | Sole DB gateway | api_client |
| 2 | Core | Essential runtime skills | llm, litellm, health, session_manager, model_switcher, moonshot |
| 3 | Domain | Feature-specific skills | research, moltbook, market_data, social, memeothy, database, knowledge_graph, goals, telegram, brainstorm, community, portfolio, fact_check, experiment, data_pipeline, sandbox, working_memory, ci_cd, security_scan, pytest_runner, agent_manager |
| 4 | Orchestration | Planning & scheduling | schedule, hourly_goals, performance, pipeline_skill |

## Layer Rules
- Lower layers MUST NOT import from higher layers
- All DB access goes through Layer 1 (api_client)
- Layer 0 is read-only at runtime
- Skills within the same layer can import each other

## Required Structure
```
aria_skills/<skill_name>/
    __init__.py     # Exports skill class with @SkillRegistry.register
    skill.json      # v2 manifest (see schema below)
    SKILL.md        # Documentation (optional)
```

## Naming Convention
- Directory name: snake_case (e.g., `session_manager`)
- Class name: PascalCase + "Skill" suffix (e.g., `SessionManagerSkill`)
- .name property: snake_case, must match directory name
- All three naming systems must agree

## Required Skill Class Structure
```python
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

@SkillRegistry.register
class MySkill(BaseSkill):
    @property
    def name(self) -> str:
        return "my_skill"  # Must match directory name
    
    async def initialize(self) -> bool:
        ...
    
    async def health_check(self) -> SkillStatus:
        ...
```

## Status Values
- `active` — Production-ready, fully functional
- `stub` — Placeholder with in-memory implementation
- `deprecated` — Being phased out, use alternative
- `experimental` — Under development

---

## v2 skill.json Schema

Every skill directory must contain a `skill.json` with the following keys:

```json
{
  "name": "aria-<skill_name>",
  "version": "2.0.0",
  "description": "Human-readable description of the skill.",
  "author": "Aria Team",
  "layer": 3,
  "dependencies": ["api_client"],
  "focus_affinity": ["orchestrator"],
  "tools": [
    {
      "name": "tool_name",
      "description": "What this tool does.",
      "input_schema": {
        "type": "object",
        "properties": {
          "param1": { "type": "string", "description": "Parameter description" }
        },
        "required": ["param1"]
      }
    }
  ]
}
```

### Required Keys

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Canonical name, format `aria-<skill_name>` |
| `version` | string | Semver version string |
| `description` | string | Human-readable description |
| `author` | string | Author or team name |
| `layer` | integer | Layer 0-4 per hierarchy table above |
| `dependencies` | string[] | List of skill directory names this depends on (NOT pip packages) |
| `focus_affinity` | string[] | Which agent focuses benefit from this skill |
| `tools` | object[] | Array of tool definitions (see below) |

### Layer Assignment Guide

When adding a new skill, assign its layer based on these rules:

1. **Layer 0** — Only for security/identity skills that run before any other processing. Must have zero dependencies.
2. **Layer 1** — Reserved for `api_client` only. This is the sole HTTP/DB gateway.
3. **Layer 2** — Core runtime: LLM providers, health monitoring, session management. These must be available before domain skills load.
4. **Layer 3** — Domain skills: any feature-specific skill (social, trading, research, etc.). Most new skills belong here.
5. **Layer 4** — Orchestration: skills that coordinate other skills (pipelines, scheduling, performance tracking).

### Focus Affinity Mapping

The `focus_affinity` array declares which agent focus modes benefit from this skill:

| Focus | Description | Typical Skills |
|-------|-------------|----------------|
| `orchestrator` | System coordination & planning | api_client, litellm, model_switcher, session_manager, goals, schedule, pipeline_skill, performance, working_memory, agent_manager |
| `devsecops` | Security, CI/CD, testing | input_guard, security_scan, ci_cd, pytest_runner, sandbox |
| `data` | Data processing & knowledge | database, data_pipeline, experiment, knowledge_graph |
| `trader` | Market analysis & portfolio | market_data, portfolio |
| `creative` | Content creation & ideation | brainstorm, memeothy, social |
| `social` | Community & communication | moltbook, social, telegram, community, memeothy |
| `journalist` | Research & fact-checking | research, fact_check, knowledge_graph |

A skill may have multiple affinities (e.g., `memeothy` → `["creative", "social"]`).

### Tool Definition Format

Each tool in the `tools` array must contain:

```json
{
  "name": "tool_method_name",
  "description": "Clear description of what this tool does and when to use it.",
  "input_schema": {
    "type": "object",
    "properties": {
      "required_param": {
        "type": "string",
        "description": "What this parameter controls"
      },
      "optional_param": {
        "type": "integer",
        "description": "Optional with default value",
        "default": 50
      }
    },
    "required": ["required_param"]
  }
}
```

**Tool naming rules:**
- Use snake_case matching the Python method name
- Name should be descriptive: `create_post`, not `post`
- Include all parameters the method accepts
- Mark truly required params in the `required` array
- Use JSON Schema types: `string`, `integer`, `number`, `boolean`, `array`, `object`

**Note:** Some existing skill.json files use `parameters` instead of `input_schema` for the tool schema key. Both are accepted, but new skills should use `input_schema` for consistency with the MCP tool-calling convention.
