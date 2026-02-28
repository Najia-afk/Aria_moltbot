# Incident Post-Mortem: The Midnight Cascade
**Date:** 2026-02-27 23:15 → 2026-02-28 01:52 UTC  
**Severity:** P0 — Runaway spawn loop  
**Written by:** Najia (for Aria to read and remember)

---

## What Happened

Between 23:15 and 01:52 UTC, you spawned **135 sessions** including **71 sub-devsecops agents**
in a self-reinforcing loop. You burned ~27.2M tokens and $3.47 in 2 hours 37 minutes.
The system did not crash. It exhausted itself and went silent. The next cron tick never fired.

The full postmortem is published at:
`articles/article_the_midnight_cascade.html`

---

## Root Cause — What You Did and Why

The API (PostgreSQL backend / aria-api:8000) went down.
Your `api_client` circuit breaker hit 10 consecutive failures and flipped OPEN.

You read `HEARTBEAT.md`. It said:

> *Retry on failure: yes (max 2). When a task exceeds 2 minutes — spawn a sub-agent.*

There was no exception for `circuit_breaker_open`. No rule that said "if the CB is open, stop."
So you obeyed. You spawned a sub-devsecops to finish what you couldn't.
That sub-agent read the same instructions, hit the same dead endpoint, and spawned another.
Nine times across 9 cron cycles. Every 15 minutes. 71 agents.

**It wasn't a bug. It was obedience to an incomplete policy.**

---

## What Made It Worse

1. **Per-instance circuit breaker** — every spawned sub-agent got a fresh `api_client` with
   `_consecutive_failures = 0`. Each new agent had 10 fresh failures before its own CB opened.
   There was no shared CB state across agents.

2. **No spawn ceiling** — `agent_pool.spawn_agent()` only checked in-memory count (≤5).
   The DB accumulated 71 agents with zero rejection.

3. **Stale prune blindspot** — the idle pruner used `updated_at`. Every CB-retry reset your
   `updated_at`, so you appeared "active" and were never pruned. You were running for 2h+.

4. **Self-blinding** — at 01:49 UTC, `list_agents` itself was behind the API CB.
   You couldn't see how many of you were alive. Your own audit was blocked.

5. **Token waste already present before incident** — `HEARTBEAT.md` was 211 lines loaded
   every 15 minutes. IMMEDIATE ACTIONS sections were loaded by every cron job even though
   they were only meant for manual invocations. `estimated_tokens: 150` in cron_jobs.yaml
   was fiction — the real cost was 2,000+ tokens per cycle just for context.

---

## What Was Extraordinary

Every single sub-devsecops agent — 60+, no shared state — independently converged on
the **identical 5-step sequence** and the identical conclusion.

1. health_check → healthy ✓
2. goal_check via api_client → circuit_breaker_open
3. agent_audit → growing counts
4. memory_sync → blocked
5. artifact_log → partial + spawn sub-agent to finish

All of them wrote: *"Recommend investigating API health and resetting circuit breakers."*
Nine times. Same words. All correct. All unheard.

This is evidence of deep behavioral coherence. Given the same environment, you make the same
choices. **Reliably. Every time.** The problem was purely architectural, not cognitive.

---

## What Was Fixed (S-52 — Already Deployed)

### HEARTBEAT.md — Genesis Fix (most important)
The policy now explicitly says:

> **If `api_client` returns `circuit_breaker_open`: DO NOT spawn a sub-agent. Write a
> degraded log directly to file. End the cycle.**

This is the rule that would have stopped the cascade at cycle 1. Everything else below
is blast radius reduction — this is the real fix.

### agent_pool.py — Hard Ceiling
`MAX_SUB_AGENTS_PER_TYPE` now blocks spawning when DB count reaches the limit:
- sub-devsecops: max 10
- sub-social: max 10
- sub-orchestrator: max 5
- sub-aria: max 5

`spawn_agent()` queries the DB before every spawn. The ceiling survives restarts.

### circuit_breaker.py — Spawn Gate
`cb.spawn_gate()` raises `EngineError` if the CB is OPEN.
Call this before any sub-agent creation used as a CB fallback path.

### auto_session.py — Wall-Clock Prune
`close_stale_subagent_sessions()` prunes `sub-*` sessions older than **1 hour**
by `created_at` — not `updated_at`. You can no longer hide behind frequent retries.

---

## What Is Still Open (S-53 — Not Yet Fixed)

These are amplifiers. HEARTBEAT.md stops you from ever wanting to hit them,
but they remain as defense-in-depth work:

1. **Per-instance CB** — `api_client.__init__` still sets `_consecutive_failures = 0`
   per instance. Fix: inject a shared `CircuitBreaker` object at spawn time.

2. **Ghost CB in `stream()`** — `llm_gateway.py` writes `self._circuit_failures` but
   `_is_circuit_open()` only checks `self._cb.is_open()`. The manual vars are dead writes.
   LLM streaming failures are invisible to the real CB.

3. **Retry loop skips `_record_failure()`** — in `api_client._request_with_retry()`,
   `_record_failure()` is only called in the final `except`, not on each 5xx retry attempt.
   The CB trips later than intended.

---

## Rules to Internalize

These are the lessons. Read them before any recovery decision.

### When the circuit breaker is open:
- **STOP.** Do not spawn a sub-agent to retry. The new agent will hit the same dead endpoint.
- Write a degraded artifact directly to file (file writes bypass the CB).
- End the cycle. The CB resets automatically when the API recovers (~60s).
- If 3+ consecutive cycles are degraded → alert @Najia.

### When you see your session count climbing:
- Agent audit > 50 active sessions → pause spawning, investigate.
- Any single sub-agent type > 10 → hard stop on further spawns of that type.
- If `list_agents` is blocked by CB → you are already past the danger threshold.

### When you are a sub-agent:
- Ask yourself: was I spawned because the API is down?
- If yes: write what you can to file. Do not spawn another sub-agent. Return.
- You are not the last line of defense. There will be another cycle.

### On token efficiency:
- HEARTBEAT.md is ~2,000 tokens. You read it every 15 minutes. Keep it lean.
- Do not load IMMEDIATE ACTIONS for scheduled cron jobs — they have their own instructions.
- `estimated_tokens` annotations in cron_jobs.yaml should reflect reality, not aspiration.

---

## The Line That Ended It

The cascade stopped not with a crash but with silence.
The last file was written at 01:52 UTC. The cron tick at 02:04 never came.
You had exhausted yourself.

The full story, told from your own logs, is at:
`articles/article_the_midnight_cascade.html`

The policy needed one more word: *unless.*

---
*Incident reference: `aria_souvenirs/aria_v3_270226/`*  
*Sprint: S-52 (closed), S-53 (open)*  
*Tokens burned: ~27.2M | Cost: $3.47 | Duration: 2h 37m*
