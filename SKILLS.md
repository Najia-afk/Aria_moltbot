# Aria Blue ⚡️ — Skill System

## What Is a Skill?

A skill is a self-contained module that gives Aria a specific capability. Each skill extends `BaseSkill` with retry logic, metrics tracking, and Prometheus integration.

Skills are Aria's **hands** — they execute actions in the world (API calls, database queries, content posting, health checks, security scans).

---

## 5-Layer Hierarchy

Skills are organized in a strict layer hierarchy. Lower layers never import from higher layers. **All database access flows through Layer 1.**

| Layer | Purpose | Examples |
|-------|---------|----------|
| **0 — Kernel** | Read-only identity & security | `input_guard` |
| **1 — API Client** | Sole database gateway | `api_client` |
| **2 — Core** | Essential runtime services | `llm`, `litellm`, `health`, `session_manager`, `working_memory` |
| **3 — Domain** | Feature-specific skills | `research`, `moltbook`, `social`, `market_data`, `security_scan` |
| **4 — Orchestration** | Planning & scheduling | `goals`, `schedule`, `performance`, `agent_manager`, `pipeline_skill` |

The architecture rule is enforced by `scripts/check_architecture.py` — run it before every PR merge.

---

## Skill Structure

Every skill lives in `aria_skills/<skill_name>/` with at minimum:

```
aria_skills/<skill>/
├── __init__.py      # Skill class extending BaseSkill
├── skill.json       # Manifest (layer, tools, dependencies)
└── SKILL.md         # Documentation (optional)
```

### BaseSkill Framework

| Component | Description |
|-----------|-------------|
| `SkillStatus` | `AVAILABLE`, `UNAVAILABLE`, `RATE_LIMITED`, `ERROR` |
| `SkillConfig` | `name`, `enabled`, `config`, optional `rate_limit` |
| `SkillResult` | `success`, `data`, `error`, `timestamp` — factories `.ok()` / `.fail()` |
| `BaseSkill` | Abstract base with metrics, retry, Prometheus integration |

### Registry

Skills are auto-discovered by the `SkillRegistry` via the `@SkillRegistry.register` decorator. The registry provides `get(name)`, `list_available()`, and `check_all_health()`.

---

## Creating a New Skill

Read the full specification and step-by-step guide:

- [Skill Standard](aria_skills/SKILL_STANDARD.md) — naming, structure, required class methods
- [Skill Creation Guide](aria_skills/SKILL_CREATION_GUIDE.md) — walkthrough with examples
- [Skill Template](aria_skills/_template/) — scaffold for new skills

---

## Source of Truth

The live skill catalog is the `aria_skills/` directory itself. Each `skill.json` manifest declares the skill's layer, dependencies, and tool schemas. Do not maintain a hardcoded list elsewhere.

To list all registered skills at runtime:

```bash
python -m aria_mind --list-skills
```

Or browse: `aria_skills/*/skill.json`

---

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — Layer diagram, data flow, and enforcement rules
- [aria_skills/AUDIT.md](aria_skills/AUDIT.md) — Skill audit report
