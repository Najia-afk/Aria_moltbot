/**
 * Aria Blue — Dynamic Model Pricing & Helpers
 *
 * ZERO hardcoded prices. Everything loads from /models/pricing (backed by models.yaml).
 * To add a new provider (Gemini, Claude, etc.) → edit models.yaml only.
 *
 * Usage:
 *   await AriaModels.init();                      // call once on page load
 *   const cost = AriaModels.calculateLogCost(log); // per spend-log entry
 *   const p    = AriaModels.getProvider('kimi');
 *   const pr   = AriaModels.getPricing('kimi');
 */

const AriaModels = {
    _pricing: {},         // model_id → { input, output, cacheRead, tier, litellm_model }
    _config: null,        // full /models/config when loaded
    _ready: false,
    _initPromise: null,

    /**
     * Fetch pricing from API. Call once; subsequent calls are no-ops.
     * Safe to call multiple times — deduplicates automatically.
     */
    async init() {
        if (this._ready) return;
        if (this._initPromise) return this._initPromise;

        this._initPromise = (async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/models/pricing`);
                if (res.ok) {
                    this._pricing = await res.json();
                } else {
                    console.warn('AriaModels: /models/pricing returned', res.status);
                }
            } catch (e) {
                console.warn('AriaModels: failed to load pricing', e);
            }
            this._ready = true;
        })();
        return this._initPromise;
    },

    /**
     * Optionally load full config (/models/config) — heavier, for models page.
     */
    async loadFullConfig() {
        await this.init();
        if (this._config) return this._config;
        try {
            const res = await fetch(`${API_BASE_URL}/models/config`);
            if (res.ok) this._config = await res.json();
        } catch (e) {
            console.warn('AriaModels: failed to load config', e);
        }
        return this._config;
    },

    /**
     * Look up pricing for a model (by any of: model_id, litellm_model, alias).
     * Returns { input, output, tier } per 1M tokens in USD.
     */
    getPricing(modelId) {
        if (!modelId) return { input: 0, output: 0, tier: 'unknown' };
        const m = modelId.toLowerCase();

        // 1. Exact match
        if (this._pricing[m]) return this._pricing[m];

        // 2. Partial match (spend logs sometimes use full litellm model strings)
        for (const [key, val] of Object.entries(this._pricing)) {
            if (m.includes(key.toLowerCase()) || key.toLowerCase().includes(m)) {
                return val;
            }
        }

        // 3. Infer from tier hints
        if (m.includes(':free') || m.includes('local') || m.includes('mlx') || m.includes('ollama')) {
            return { input: 0, output: 0, tier: 'free' };
        }

        // 4. Unknown paid model — conservative default
        return { input: 0.50, output: 1.00, tier: 'unknown' };
    },

    /**
     * Calculate USD cost for a LiteLLM spend log entry.
     */
    calculateLogCost(log) {
        const pricing = this.getPricing(log.model);
        const inputTokens  = log.prompt_tokens || 0;
        const outputTokens = log.completion_tokens || 0;
        return (inputTokens / 1_000_000) * pricing.input
             + (outputTokens / 1_000_000) * pricing.output;
    },

    /**
     * Detect provider from model ID.
     */
    getProvider(modelId) {
        const m = (modelId || '').toLowerCase();
        if (m.includes('kimi') || m.includes('moonshot'))  return 'kimi';
        if (m.includes(':free'))                            return 'openrouter-free';
        if (m.includes('openrouter/'))                      return 'openrouter';
        if (m.includes('gpt') || m.includes('openai'))     return 'openai';
        if (m.includes('claude') || m.includes('anthropic')) return 'anthropic';
        if (m.includes('gemini') || m.includes('google'))  return 'google';
        if (m.includes('local') || m.includes('mlx') || m.includes('ollama')) return 'local';

        // Check tier from loaded pricing data
        const p = this.getPricing(modelId);
        if (p.tier === 'free')  return 'openrouter-free';
        if (p.tier === 'local') return 'local';
        if (p.tier === 'paid')  return 'paid';
        return 'unknown';
    },

    getProviderColor(provider) {
        const colors = {
            'kimi': '#6366f1', 'openrouter': '#f59e0b', 'openrouter-free': '#22c55e',
            'openai': '#10a37f', 'anthropic': '#d97706', 'google': '#4285f4',
            'local': '#22c55e', 'paid': '#6366f1', 'unknown': '#6b7280',
        };
        return colors[provider] || colors['unknown'];
    },
};

// ── Shared formatting helpers (no pricing data, pure display) ───────────────

function formatNumber(num) {
    if (!num && num !== 0) return '0';
    if (num >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1) + 'B';
    if (num >= 1_000_000)     return (num / 1_000_000).toFixed(1) + 'M';
    if (num >= 1_000)         return (num / 1_000).toFixed(1) + 'K';
    return num.toString();
}

function formatMoney(amount, currency) {
    if (amount == null) return '$0.00';
    const sym = (currency === 'CNY' || currency === '¥') ? '¥' : '$';
    if (Math.abs(amount) < 0.01 && amount !== 0) return sym + amount.toFixed(4);
    return sym + amount.toFixed(2);
}

function formatCost(cost) {
    if (!cost || cost === 0) return '$0.00';
    if (cost < 0.01) return '$' + cost.toFixed(4);
    return '$' + cost.toFixed(2);
}

function formatDate(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    const now = new Date();
    const diffMs = now - d;
    if (diffMs < 0) {
        const futureMins = Math.floor(-diffMs / 60000);
        if (futureMins < 1)  return 'in <1m';
        if (futureMins < 60) return `in ${futureMins}m`;
        const futureHrs = Math.floor(futureMins / 60);
        if (futureHrs < 24)  return `in ${futureHrs}h ${futureMins % 60}m`;
        return `in ${Math.floor(futureHrs / 24)}d ${futureHrs % 24}h`;
    }
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1)  return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24)  return `${diffHrs}h ago`;
    return d.toLocaleString();
}

function formatDuration(ms) {
    if (!ms) return '-';
    if (ms < 1000) return ms + 'ms';
    const secs = Math.floor(ms / 1000);
    if (secs < 60) return secs + 's';
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ${secs % 60}s`;
    const hrs = Math.floor(mins / 60);
    return `${hrs}h ${mins % 60}m`;
}

function statusBadge(status) {
    const cls = status === 'ok' || status === 'active' || status === 'success' ? 'active'
              : status === 'error' || status === 'failed' ? 'error'
              : 'completed';
    return `<span class="status-badge ${cls}">${status || 'pending'}</span>`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatPrice(price) {
    if (price === 0) return '<span style="color:var(--success)">FREE</span>';
    if (price < 0.01) return '$' + price.toFixed(4);
    return '$' + price.toFixed(2);
}

// ── Backward-compatible standalone wrappers ─────────────────────────────────
// Templates call these as global functions; they delegate to AriaModels.
// Ensure `await AriaModels.init()` has been called before using pricing functions.

const CNY_TO_USD = 0.137;

function calculateLogCost(log) {
    return AriaModels.calculateLogCost(log);
}

function getProvider(modelId) {
    return AriaModels.getProvider(modelId);
}

function getProviderColor(provider) {
    return AriaModels.getProviderColor(provider);
}

function getModelPricing(modelId) {
    return AriaModels.getPricing(modelId);
}

