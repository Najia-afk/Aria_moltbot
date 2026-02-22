# RT-10: Chat Model Picker Doesn't Show Agent Aliases From models.yaml

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P3 🟢 | **Points:** 2 | **Phase:** 3

---

## Roundtable Exchange

**SM:** The models admin page shows all models. But the chat UI's model selector (if any)
doesn't use the human-readable aliases from `models.yaml agent_aliases`.
Users see IDs like `litellm/qwen3-coder-free` instead of `Qwen3 Coder 480B (OpenRouter FREE)`.

**Aria (PO):** The `agent_aliases` map in `models.yaml` exists precisely for UI display.
The models page (`/models`) renders them correctly. The chat page should use the same data.
Acceptance:
1. Chat model selector (once added in RT-06) shows human-readable names from `agent_aliases`
2. API endpoint `/api/engine/models` (or `/api/models`) returns `{id, display_name, tier}` tuples
3. Free models grouped separately from paid; local models at the top

---

## Problem

`aria_models/models.yaml` has `agent_aliases` (22 entries) mapping `litellm/model-id` → friendly name.
The chat endpoint doesn't expose this to the frontend. The models table in DB is synced from
models.yaml via `models_sync.py` — but the sync might not include `agent_aliases` display names.

---

## Root Cause

`agent_aliases` was added to `models.yaml` for display purposes but was never wired into
the chat UI model picker. The models DB table exists but the chat frontend doesn't query it.

---

## Fix Plan

### Backend — ensure models endpoint returns display_name
```python
# src/api/routers/engine_*.py (or models router) — verify response includes display_name
# GET /api/engine/models should return:
# [{"id": "litellm/kimi", "display_name": "Kimi K2.5 (Moonshot Paid)", "tier": "paid"}, ...]
```

### Frontend chat — group models by tier in picker
```javascript
// In engine_chat.html — model picker (added via RT-06 or standalone)
async function loadModels() {
    const res = await fetch('/api/models?limit=50');
    const data = await res.json();
    
    const grouped = { local: [], free: [], paid: [] };
    (data.models || data).forEach(m => {
        if (grouped[m.tier]) grouped[m.tier].push(m);
    });
    
    const sel = document.getElementById('model-selector');
    for (const [tier, models] of Object.entries(grouped)) {
        if (!models.length) continue;
        const grp = document.createElement('optgroup');
        grp.label = tier.toUpperCase();
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.litellm_id || m.id;
            opt.textContent = m.display_name || m.id;
            grp.appendChild(opt);
        });
        sel.appendChild(grp);
    }
}
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend reads via API — no direct DB |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml single source of truth | ✅ | Display names come from models.yaml via DB sync |
| 4 | Docker-first testing | ✅ | Browser test |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Verify models API returns display_name:
curl http://localhost:8000/api/models?limit=5 | python3 -m json.tool | grep display_name
# EXPECTED: "display_name": "Kimi K2.5 (Moonshot Paid)"  etc.

# 2. Chat model picker shows friendly names grouped by tier:
# Browser: open /chat, click model selector — sees "LOCAL", "FREE", "PAID" groups
# Names read as "Qwen3 Coder 480B" not "litellm/qwen3-coder-free"
```

---

## Prompt for Agent

Read: `aria_models/models.yaml` (agent_aliases section), `src/api/routers/` (find models endpoint),
`src/web/templates/engine_chat.html` (model picker if exists, else where to add).

Steps:
1. Confirm `/api/models` returns `display_name` per model (check `models_sync.py`)
2. If missing, add `display_name` field to the models DB table + sync
3. Add `loadModels()` JS function in `engine_chat.html`
4. Add `<select id="model-selector">` grouped by tier to chat header (alongside agent selector from RT-06)

Constraints: 3 (models.yaml source of truth), 4 (Docker test).
Dependencies: RT-06 (agent selector UI adds the pattern for this picker), RT-02 (model routing must honour the selection).
