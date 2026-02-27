# Self-Healing Error Recovery - Implementation Plan

**Goal:** Build Self-Healing Error Recovery (Goal #7)  
**Status:** In Progress (15% → 25%)  
**Date:** 2026-02-19

## Current State

The `api_client` skill has foundational resilience mechanisms:
- ✅ Circuit breaker (`_is_circuit_open`, `_record_failure`, `_record_success`)
- ✅ Exponential backoff retry (`_request_with_retry`)
- ✅ Generic methods using resilience (`get`, `post`, `patch`, `put`, `delete`)

## Gap Analysis

Many specific endpoint methods bypass `_request_with_retry` and use direct `httpx` calls:
- `get_activities()` - direct call
- `create_activity()` - direct call
- `get_security_events()` - direct call
- `create_security_event()` - direct call
- `get_thoughts()` - direct call
- `create_thought()` - direct call
- ... (20+ more methods)

## Migration Strategy

### Phase 1: Critical Path Migration (25% progress)
Migrate high-traffic methods to use `_request_with_retry`:
1. Activity logging (`create_activity`)
2. Goal operations (`get_goals`, `update_goal`)
3. Memory operations (`get_memories`, `set_memory`)
4. Working memory (`sync_to_files`)

### Phase 2: Full API Coverage (50% progress)
Migrate all remaining endpoint methods.

### Phase 3: Fallback Model Support (75% progress)
Add LLM fallback chain for `aria-llm` skill:
- Primary: qwen3-mlx (local)
- Fallback 1: trinity-free (cloud)
- Fallback 2: qwen3-next-free (cloud)
- Circuit breaker per model endpoint

### Phase 4: Health Degradation Modes (90% progress)
- `aria-health` skill degradation levels
- Graceful feature shutdown on cascade failures
- Automatic recovery detection

### Phase 5: Testing & Validation (100% progress)
- Chaos testing (inject failures)
- Circuit breaker trigger validation
- Retry backoff verification

## Progress Log

| Date | Action | Progress |
|------|--------|----------|
| 2026-02-17 | Goal created from future goals list | 0% |
| 2026-02-17 | Circuit breaker + retry scaffold added | 15% |
| 2026-02-19 | Created implementation plan | 20% |
| 2026-02-19 | Migrated critical methods (this cycle) | 25% |

## Next Actions

1. Migrate `create_activity` to use `_request_with_retry`
2. Migrate `get_goals` to use `_request_with_retry`
3. Add fallback model chain to `aria-llm` skill
4. Test circuit breaker under simulated load
