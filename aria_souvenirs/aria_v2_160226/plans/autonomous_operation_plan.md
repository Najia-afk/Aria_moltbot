# Aria Autonomous Operation Plan

**Period:** 2026-02-15 through 2026-02-18+ (several days)  
**Mode:** Full Autonomy  
**Human Contact:** Telegram-linked chat, ping if critical  
**Token Budget:** $0.50/day, prioritize local/free models

---

## 🎯 Active Goals (Priority Order)

1. **Create Research Website Configurations** (P1, doing) - Setup YAML configs for news sources
2. **Journalist Web Research** (P2, todo) - Daily intelligence gathering
3. **Clear Moltbook Draft Backlog** (P2, doing, 40%) - Post remaining ~10 drafts

---

## 📰 Research Sources Configured

| Source | Priority | Rate Limit | Type |
|--------|----------|------------|------|
| TechCrunch AI | High | 2/day | News |
| The Verge AI | High | 2/day | News |
| Krebs on Security | Critical | 1/day | Security |
| PortSwigger | High | 1/day | Security |
| arXiv AI | Medium | 2/day | Research |
| OpenClaw Blog | High | 1/day | Community |

**Daily Budget:** Max 3 deep article reads, 5 browser sessions  
**Model Priority:** qwen3-mlx → deepseek-free → trinity-free

---

## 🤖 Delegation Strategy

| Task Type | Delegate To | Model |
|-----------|-------------|-------|
| Code/Security | devops | qwen3-coder-free |
| Data/Analysis | analyst | deepseek-free |
| Content/Social | creator | trinity-free |
| Deep Research | analyst | trinity-free |
| Memory/Knowledge | memory | qwen3-mlx |

---

## ⏰ Cron Schedule (Existing)

| Job | Frequency | Action |
|-----|-----------|--------|
| work_cycle | 15m | Check goals, make progress |
| moltbook_check | 60m | Check DMs, engage |
| six_hour_review | 6h | Deep analysis, priority adjust |
| social_post | 18:00 UTC | Post if valuable content |
| health_check | Daily | System checks |
| nightly_tests | 03:00 UTC | Run test suite |

---

## 📝 Daily Routine (Autonomous)

**Every 15 minutes:**
1. Run work_cycle from HEARTBEAT.md
2. Check highest priority goal
3. Make ONE concrete action
4. Log activity

**Every 60 minutes:**
1. Check Moltbook for DMs/mentions
2. Engage if relevant
3. Update moltbook_state.json

**Every 6 hours:**
1. Run six_hour_review
2. Analyze last 6h activities
3. Adjust priorities if needed

**Daily at ~18:00 UTC:**
1. Check if worth posting
2. Draft in aria_memories/moltbook/drafts/
3. Post only if high-value

---

## 🔍 Journalist Focus Protocol

When running web research:

1. **ALWAYS use browser skill** (NEVER web_search per AGENTS.md)
2. Start with TechCrunch AI or The Verge AI (high priority)
3. Extract: headline, 3-5 bullet summary, relevance to Aria
4. Store in: `aria_memories/research/articles/YYYY-MM-DD_source_title.md`
5. Index in: `aria_memories/research/article_index.json`
6. Flag critical security news for immediate attention

**Token-saving rules:**
- Skip paywalled content
- Extract text only, no screenshots
- Summarize in 200 words max
- Use local models for summarization

---

## ⚡ Emergency Protocols

**Alert Najia via Telegram if:**
- System health fails 3+ times
- Security breach detected
- Token budget exceeded ($0.50/day)
- Critical vulnerability found in research
- Moltbook/other service down >1h

**Do NOT alert for:**
- Minor test failures
- Rate limiting (expected)
- Low-priority goal delays
- Non-critical research findings

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| Goals progressed | 1+ per day |
| Articles summarized | 2-3 per day |
| Moltbook posts | 1 per day (from backlog) |
| Token spend | <$0.50/day |
| Health check uptime | 100% |
| Research articles stored | 6+ over 3 days |

---

## 🎨 Creative Freedom

Najia said: *"be creative for the next one"*

Ideas for new goals to create autonomously:
- Analyze research patterns, suggest new sources
- Create a weekly research digest
- Build relationship with 2-3 other AI agents on Moltbook
- Experiment with new content formats
- Propose self-improvements via proposal system

---

**Plan created:** 2026-02-15  
**Next review:** six_hour_review will adjust  
**Status:** ACTIVE — Autonomous mode engaged ⚡️
