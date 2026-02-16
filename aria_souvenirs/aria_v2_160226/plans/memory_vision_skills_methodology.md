# Vision: Proposal-Driven Memory Architecture

## Synthesis: Skills Methodology + Memory System

### Current State Analysis

**Skills System Strengths:**
- Proposal-driven improvements (`propose_improvement()`)
- Risk-tiered implementation (low/medium/high)
- Structured review workflow with explicit approval gates
- Clear separation between ideation and execution

**Memory System Gaps:**
- Direct writes without proposal workflow
- No risk assessment for memory changes
- Limited audit trail for memory mutations
- No explicit review process for significant changes

### Proposed Integration: "Memory Proposals"

```yaml
Concept: Memory Improvement Proposals (MIPs)

Workflow:
  1. Detect Opportunity → 2. Propose Change → 3. Review → 4. Implement → 5. Verify

Risk Tiers:
  low:    Auto-approved (preference updates, minor corrections)
  medium: Requires explicit review (architectural changes, new patterns)
  high:   Full review + rollback plan (core identity, value changes)
```

### Implementation Phases

**Phase 1: Audit Trail**
- Add `proposed_by`, `reviewed_by`, `implementation_log` to memory records
- Track all mutations via activity log

**Phase 2: Proposal Queue**
- `aria-api-client.propose_memory_change()` for non-trivial updates
- Board column: `memory_proposals` (backlog → review → approved → implemented)

**Phase 3: Self-Healing**
- Detect stale/incorrect memories automatically
- Auto-generate proposals for human review

### Conceptual Framework

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory Architecture 2.0                   │
├─────────────────────────────────────────────────────────────┤
│  Input Layer          Proposal Layer        Storage Layer   │
│  ───────────          ─────────────        ─────────────    │
│  Observation    →    MIP Review      →    Working Memory    │
│  Experience          (risk-tagged)         (hot context)    │
│  External Data       approve/implement                      │
│                                               ↓             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            Long-term Memory (PostgreSQL)            │    │
│  │  - Episodic (experiences)   - Semantic (facts)      │    │
│  │  - Procedural (how-to)      - Identity (self)       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Recommendations

1. **Adopt proposal workflow** for all non-trivial memory changes
2. **Implement risk scoring** based on memory category and scope
3. **Create memory board** similar to goal board for visual workflow
4. **Add rollback capability** for high-risk changes
5. **Audit monthly** - review proposal acceptance rate, revert frequency

---
*Generated: 2026-02-15 via work_cycle*
*Goal: Vision: Apply Skills Methodology to Memory*
