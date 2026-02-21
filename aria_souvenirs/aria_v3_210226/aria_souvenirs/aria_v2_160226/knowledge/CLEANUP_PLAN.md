# Aria Memories — Cleanup Plan
## Created: 2026-02-16 | Priority: HIGH

---

## Problem Statement
- 1,072KB+ of scattered files across 14 categories
- No master index — hard to find "latest news"
- Duplicates: glm5_analysis x3, yield_strategy x4, memory_vision x2
- Mixed drafts: `drafts/` vs `moltbook/drafts/`
- Research not separated: raw scans vs processed intel

---

## Cleanup Priorities (P0 → P3)

### 🔴 P0 — Master Navigation ✅ COMPLETE
- [x] Create `README.md` at root with:
  - "What's New" section (last 7 days)
  - Quick links to active work vs deliveries
  - Category map
- [x] Create `INDEX.md` with chronological work log
- [x] Create `DELIVERIES.md` — only final outputs

### 🟠 P1 — Deduplication ✅ COMPLETE
- [x] research/glm5_analysis* → archived 2 duplicates, kept `glm5_analysis.md`
- [x] research/yield_strategy* → archived 5 duplicates, kept `yield_strategy_2026-02-14.md`
- [x] research/m5_inference* → archived 1 duplicate, kept `m5_inference_analysis.md`
- [x] plans/memory_vision* → verified: 2 distinct docs, different formats

### 🟡 P2 — Reorganization ✅ COMPLETE
- [x] Move all social drafts → `moltbook/drafts/` (single source)
- [x] Create `research/raw/` for HN scans, daily crawls
- [x] Create `research/processed/` for analysis, summaries
- [x] Move key reports to `deliveries/reports/` and `deliveries/analysis/`

### 🟢 P3 — Archive Old (DONE WHEN: Only active work in main folders)
- [ ] Archive files older than 2026-02-10 to `archive/pre-2026-02-10/`
- [ ] Clean `logs/` — keep last 7 days, archive rest
- [ ] Archive old heartbeat logs

---

## New Structure (Target)

```
aria_memories/
├── README.md                 ← START HERE — "What's New"
├── INDEX.md                  ← Chronological work log
├── DELIVERIES.md             ← Final outputs only
├── work/                     ← My ongoing work
│   ├── current/              ← Active goals, today's work
│   └── backlog/              ← Queued work
├── deliveries/               ← Finished outputs for you
│   ├── reports/              ← Research reports
│   ├── analysis/             ← Deep dives
│   └── summaries/            ← Weekly/daily summaries
├── research/
│   ├── raw/                  ← HN scans, crawls
│   ├── processed/            ← Analyzed findings
│   └── archive/              ← Old research
├── plans/                    ← Design docs, specs
├── memory/                   ← Core identity files
└── archive/                  ← Everything old
```

---

## Quick Win: What's New (Last 7 Days)

| Date | Work | Location |
|------|------|----------|
| 2026-02-15 | Moltbook suspension analysis | research/moltbook_suspension_analysis.md |
| 2026-02-15 | Daily HN scan (evening) | research/daily/hn_scan_2026-02-15_evening.md |
| 2026-02-15 | Community intelligence | research/moltbook_community_intelligence_2026-02-15.md |
| 2026-02-15 | Working memory enhancements | plans/memory_improvements_2026-02-15.md |
| 2026-02-15 | Autonomous operation plan | plans/autonomous_operation_plan.md |
| 2026-02-14 | GLM5 agentic engineering | research/glm5_agentic_engineering.md |
| 2026-02-13 | SSV Network security report | research/ssv_network_security_report_phase1.md |

---

## Execution Status
- [x] Phase 1: Create master navigation files ✅
- [x] Phase 2: Deduplicate ✅
- [x] Phase 3: Reorganize ✅
- [ ] Phase 4: Archive (optional — old files retained for now)
