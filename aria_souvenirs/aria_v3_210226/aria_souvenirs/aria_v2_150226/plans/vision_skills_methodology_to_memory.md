# Vision: Applying Skills Methodology to Memory System

## Executive Summary

This document proposes transforming Aria's memory system by adopting the same proposal-driven, risk-calibrated methodology that powers the skills layer. The goal: make memory operations as safe, auditable, and self-improving as code changes.

---

## Current State Analysis

### Skills System (Reference)
- **Proposal-driven**: All medium/high-risk changes require explicit proposals
- **Risk calibration**: Low/medium/high tiers with appropriate review gates
- **Audit trail**: Every proposal has lifecycle tracking (proposed → approved → implemented → verified)
- **Self-improvement**: Patterns from implemented proposals feed back into system design

### Memory System (Current)
- **Direct operations**: Working memory and long-term memory via direct API calls
- **Limited audit trail**: Activities logged, but memory changes not proposal-tracked
- **No risk calibration**: All memory operations treated equally
- **Ad-hoc improvements**: No structured feedback loop

---

## Proposed Architecture

### Core Principle: "Memory as Skill"

Treat memory operations with the same rigor as skill development:

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY OPERATIONS                        │
├─────────────────────────────────────────────────────────────┤
│  Working Memory (ephemeral)    │  Long-term Memory (durable)│
│  ─────────────────────────     │  ───────────────────────── │
│  • Session context             │  • Core facts              │
│  • Active goals                │  • User preferences        │
│  • Transient observations      │  • Learned patterns        │
│  • Checkpointable state        │  • Relationship graphs     │
├─────────────────────────────────────────────────────────────┤
│  Proposal Layer (risk-calibrated)                           │
│  ─────────────────────────────────────────────────────────  │
│  • Low risk: Direct write (auto-approved)                   │
│  • Medium risk: Proposal required, fast-track review        │
│  • High risk: Proposal + explicit approval + verification   │
├─────────────────────────────────────────────────────────────┤
│  Audit Layer (complete traceability)                        │
│  ─────────────────────────────────────────────────────────  │
│  • Every write = proposal record                            │
│  • Rollback capability via proposal_id                      │
│  • Quality metrics per memory category                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Risk Calibration Framework

| Operation | Risk Level | Proposal Required | Example |
|-----------|------------|-------------------|---------|
| Session checkpoint | Low | No | `sync_to_files()` during normal operation |
| User preference update | Medium | Yes, auto-approve after logging | "User prefers dark mode" |
| Core fact modification | Medium | Yes, auto-approve | "User changed their name" |
| Relationship graph change | High | Yes, explicit approval | "Trust relationship established with X" |
| Memory deletion/correction | High | Yes, explicit approval | "Remove incorrect learned fact" |
| Memory schema migration | High | Yes, explicit approval + verification | "Restructure knowledge graph" |

---

## Implementation Phases

### Phase 1: Audit Trail (Week 1-2)
- Extend `aria-api-client` memory endpoints to create proposal records
- All memory writes get `proposal_id` reference
- Backfill existing memory entries with synthetic proposals

### Phase 2: Risk Calibration (Week 3-4)
- Categorize all memory operations by risk level
- Implement proposal requirement gates
- Build fast-track approval for medium-risk operations

### Phase 3: Self-Improvement Loop (Week 5-6)
- Track memory access patterns
- Identify high-churn, high-value memory categories
- Propose structural optimizations based on usage data
- Quality scoring for memory entries (accuracy, relevance, freshness)

### Phase 4: Advanced Features (Week 7-8)
- Memory rollback via proposal revert
- Conflict detection for concurrent memory updates
- Automated memory grooming (archive stale, surface valuable)

---

## Migration Strategy

### Backward Compatibility
```python
# Current API (preserved)
aria-api-client.set_memory({"key": "preference", "value": "dark_mode"})

# New proposal-aware API (additive)
aria-api-client.set_memory({
    "key": "preference", 
    "value": "dark_mode",
    "proposal": {
        "title": "Update user theme preference",
        "risk_level": "medium",
        "auto_approve": true  # For medium risk with patterns
    }
})
```

### Gradual Adoption
1. All memory operations create audit records (no change to caller)
2. Medium/high risk operations emit warnings for 2 weeks
3. Proposal requirements enforced for new operations
4. Legacy operations grandfathered with synthetic proposal records

---

## Expected Benefits

1. **Safety**: No accidental overwrites of critical memory
2. **Auditability**: Complete history of what Aria "learned" and when
3. **Quality**: Explicit review gates improve memory accuracy
4. **Trust**: Najia can review and approve significant memory changes
5. **Self-Improvement**: Usage patterns drive architectural evolution

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Memory write audit coverage | 100% |
| Proposal approval time (medium risk) | < 5 seconds |
| Rollback success rate | > 99% |
| Memory accuracy score (user-reported) | > 95% |
| Unintended memory overwrites | 0 |

---

## Conclusion

Applying the skills methodology to memory transforms a passive storage system into an active, self-improving knowledge architecture. The proposal-driven approach ensures that Aria's memory grows more accurate and valuable over time, with appropriate safeguards for high-stakes changes.

**Recommendation**: Proceed with Phase 1 implementation immediately.

---

*Document Version: 1.0*
*Created: 2026-02-15*
*Status: Vision Complete → Ready for Implementation Planning*
