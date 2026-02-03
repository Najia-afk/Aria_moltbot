# Aria Development Prompts

This folder contains detailed guides and references for developing and extending Aria Blue.

## Documents

### [Agent Workflow Guidelines](agent-workflow.md)
General workflow principles for AI agents working on this codebase:
- Planning and task management
- Subagent strategies
- Self-improvement loops
- DevSecOps practices
- Deployment workflow

### [Skill Development Guide](skill-development-guide.md)
Complete guide for creating new skills:
- Python skill implementation (`aria_skills/`)
- OpenClaw manifest creation (`openclaw_skills/`)
- Testing and verification
- Deployment checklist
- Best practices and patterns

### [Architecture Reference](architecture-reference.md)
Deep dive into Aria's cognitive architecture:
- Agent system (`aria_agents/`)
- Mind system (`aria_mind/`)
- Soul, Memory, Cognition, Heartbeat
- Integration patterns
- Database schema

---

## Quick Start

### Creating a New Skill

1. Read [skill-development-guide.md](skill-development-guide.md)
2. Create Python implementation in `aria_skills/`
3. Create OpenClaw manifest in `openclaw_skills/aria-skillname/`
4. Add configuration to `aria_mind/TOOLS.md`
5. Write tests in `tests/`
6. Deploy following the workflow in [agent-workflow.md](agent-workflow.md)

### Understanding the Architecture

1. Start with [architecture-reference.md](architecture-reference.md)
2. Review `aria_mind/` documentation files:
   - `IDENTITY.md` - Who Aria is
   - `ORCHESTRATION.md` - Self-awareness
   - `GOALS.md` - Goal-driven work
   - `MEMORY.md` - Memory architecture
   - `TOOLS.md` - Available skills
   - `AGENTS.md` - Agent definitions

### Working on This Codebase

1. Follow [agent-workflow.md](agent-workflow.md) principles
2. Plan before coding
3. Verify before shipping
4. Update `tasks/lessons.md` after corrections

---

## File Structure Reference

```
Aria_moltbot/
├── aria_agents/         # Agent system
│   ├── base.py          # BaseAgent, AgentConfig, AgentMessage
│   ├── coordinator.py   # AgentCoordinator
│   └── loader.py        # AgentLoader
│
├── aria_mind/           # Cognitive system
│   ├── cognition.py     # Processing pipeline
│   ├── memory.py        # Short/long-term memory
│   ├── heartbeat.py     # Health & scheduling
│   ├── startup.py       # Boot sequence
│   ├── soul/            # Identity, values, boundaries
│   └── *.md             # Configuration & documentation
│
├── aria_skills/         # Skill implementations
│   ├── base.py          # BaseSkill, SkillResult, SkillStatus
│   ├── registry.py      # SkillRegistry
│   └── *.py             # Individual skills
│
├── openclaw_skills/     # OpenClaw manifests
│   └── aria-*/          # One folder per skill
│       ├── skill.json   # Tool definitions
│       └── SKILL.md     # Documentation
│
├── prompts/             # Development guides (this folder)
├── tests/               # Test suite
└── tasks/               # Task tracking
```
