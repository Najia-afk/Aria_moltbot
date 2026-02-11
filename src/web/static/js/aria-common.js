/**
 * Shared balance + spend fetching for Aria Blue pages.
 * Depends on pricing.js (AriaModels, calculateLogCost, formatMoney).
 */

/**
 * Fetch provider balances and return { data, totalUSD }.
 */
async function fetchBalances(apiUrl) {
    const response = await fetch(`${apiUrl}/providers/balances`);
    const data = await response.json();
    let totalUSD = 0;

    if (data.kimi?.status === 'ok') {
        totalUSD += data.kimi.available || 0;
    }
    if (data.openrouter?.status === 'ok') {
        const limit = data.openrouter.limit;
        const usage = data.openrouter.usage || 0;
        if (limit !== null && limit !== undefined) {
            const remaining = limit - usage;
            if (remaining > 0) totalUSD += remaining;
        }
    }

    return { data, totalUSD };
}

/**
 * Fetch spend logs and calculate totals.
 * Returns { logs, totalSpend, todaySpend, weekSpend, monthSpend, inputTokens, outputTokens, totalTokens, requestCount }.
 */
async function fetchSpendSummary(apiUrl, limit = 50) {
    const resp = await fetch(`${apiUrl}/litellm/spend?limit=${limit}&lite=true`);
    const raw = await resp.json();
    const logs = raw.logs || (Array.isArray(raw) ? raw : []);

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekStart = new Date(now); weekStart.setDate(now.getDate() - 7);
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

    let totalSpend = 0, todaySpend = 0, weekSpend = 0, monthSpend = 0;
    let inputTokens = 0, outputTokens = 0, totalTokens = 0;

    logs.forEach(log => {
        const cost = calculateLogCost(log);
        const logDate = new Date(log.startTime || log.created_at);
        totalSpend += cost;
        inputTokens += log.prompt_tokens || 0;
        outputTokens += log.completion_tokens || 0;
        totalTokens += log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
        if (logDate >= todayStart) todaySpend += cost;
        if (logDate >= weekStart) weekSpend += cost;
        if (logDate >= monthStart) monthSpend += cost;
    });

    return { logs, totalSpend, todaySpend, weekSpend, monthSpend, inputTokens, outputTokens, totalTokens, requestCount: logs.length };
}
