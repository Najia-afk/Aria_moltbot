# Sprint aria_v3_280226 — Focus System v2

**Theme:** Turn `focus_type` from a routing tag into a first-class personality
architecture. Aria chooses her own headspace, composes her prompt accordingly,
trims tokens ruthlessly per focus, and delegates roundtable/swarm picks from
focus-match scores — not hardcoded lists.

**Sprint Owner:** Najia | **Date:** 2026-02-28 | **Version:** aria_v3_280226

---

## Epic E7 — Focus System v2 (8 tickets, ~26 points)

| Ticket | Title | Points | Phase | Depends on |
|--------|-------|--------|-------|------------|
| S-70 | FocusProfile DB model + migration | 3 | 1 | — |
| S-71 | `engine_focus.py` CRUD router + seed | 3 | 1 | S-70 |
| S-72 | routing.py — DB-driven SPECIALTY_PATTERNS | 2 | 2 | S-71 |
| S-73 | agent_pool: focus-aware prompt composition | 3 | 2 | S-71 |
| S-74 | Token budget enforcement per focus | 3 | 2 | S-73 |
| S-75 | Focus-aware delegation in roundtable + swarm | 5 | 3 | S-72, S-73 |
| S-76 | `engine_focus.html` management UI | 4 | 3 | S-71 |
| S-77 | `api_client` focus skill (Aria self-activates) | 3 | 4 | S-71 |

---

## Architecture Summary

### What is a FocusProfile?

A **FocusProfile** is Aria's headspace. It composes **on top of** the base
agent system prompt. It is never a replacement — it is additive.

```
effective_system_prompt = agent.system_prompt
                        + "\n\n---\n"
                        + focus.system_prompt_addon   ← focus injects personality
```

### Layer assignment

```
DB (aria_engine.focus_profiles)
  ↕ ORM (FocusProfileEntry in src/api/db/models.py)
  ↕ API (src/api/routers/engine_focus.py)
  ↕ api_client skill (aria_skills/focus/)
  ↕ Aria Mind
```

### Token discipline

Each focus profile carries a `token_budget_hint` integer. The agent's
`process()` method caps `max_tokens` at this value unless the caller explicitly
overrides with a higher limit. This is the drastic token discipline:

| Focus | Budget (tokens) | Rationale |
|-------|----------------|-----------|
| orchestrator | 2000 | Meta-decisions, no verbose output |
| devsecops | 1500 | Code diffs, not essays |
| data | 1500 | Metrics tables, not narratives |
| creative | 3000 | Permitted expansion for craft |
| social | 800 | Post-length outputs only |
| research | 2500 | Citations + summaries |
| journalist | 2000 | Leads + key facts only |
| rpg_master | 2000 | Scene setting, not novels |

### Delegation levels

Focus profiles carry a `delegation_level` integer (1, 2, or 3):

- **L1 (1):** Core focus — can initiate roundtable/swarm
- **L2 (2):** Specialist — invited by L1, not initiator
- **L3 (3):** Narrow/ephemeral — spawned on-demand, auto-terminates

In roundtable/swarm, `agent_ids` resolution becomes:
```
If agent_ids omitted → select all L1+L2 agents whose focus
                       specialty_keywords hit the topic.
                       Max 5 agents (token budget).
```

---

## Constraints Reference (all tickets)

| # | Constraint | Application |
|---|-----------|-------------|
| 1 | 5-layer architecture | FocusProfile: DB→ORM→API→api_client→Skills→Agents |
| 2 | No secrets in code | No keys; profiles are config, not secrets |
| 3 | models.yaml SoT | `model_override` in FocusProfile references model_id from models.yaml |
| 4 | Docker-first | Every ticket has docker-exec verification |
| 5 | aria_memories writable | Aria reads profiles via api_client (read-only OK) |
| 6 | No soul modification | Focus addons extend personality; SOUL.md values untouched |

---

## Execution Order

```
Phase 1 (foundation):  S-70 → S-71  (serial, DB must exist before API)
Phase 2 (engine):      S-72, S-73, S-74  (parallel after S-71)
Phase 3 (behaviour):   S-75, S-76  (parallel after Phase 2)
Phase 4 (skill):       S-77  (after S-76 — reads the UI endpoints)
```
