# Aria Skill Standard v1.1

## 5-Layer Hierarchy

| Layer | Name | Description | Examples |
|-------|------|-------------|----------|
| 0 | Kernel | Read-only identity & security | soul, identity, security |
| 1 | API Client | Sole DB gateway | api_client |
| 2 | Core | Essential runtime skills | llm, litellm, health, session_manager, model_switcher |
| 3 | Domain | Feature-specific skills | research, moltbook, market_data, social, memeothy |
| 4 | Orchestration | Planning & scheduling | goals, schedule, hourly_goals, performance |

## Layer Rules
- Lower layers MUST NOT import from higher layers
- All DB access goes through Layer 1 (api_client)
- Layer 0 is read-only at runtime
- Skills within the same layer can import each other

## Required Structure
```
aria_skills/<skill_name>/
    __init__.py     # Exports skill class with @SkillRegistry.register
    skill.yaml      # Metadata: name, layer, version, dependencies
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
