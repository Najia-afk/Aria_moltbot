/**
 * Shared helpers for Aria Blue pages.
 * Depends on pricing.js (AriaModels, calculateLogCost, formatMoney).
 */

window.ARIA_DEBUG = (new URLSearchParams(window.location.search).has('debug')) ||
                    (localStorage.getItem('aria_debug') === '1');

function ariaLog(...args) {
    if (window.ARIA_DEBUG) {
        console.log('[ARIA]', ...args);
    }
}

function ariaWarn(...args) {
    if (window.ARIA_DEBUG) {
        console.warn('[ARIA]', ...args);
    }
}

/**
 * Fetch with timeout and HTTP status check.
 * Returns response JSON or throws with useful error message.
 */
async function fetchWithTimeout(url, options = {}, timeout = 15000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
        const resp = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(id);
        if (!resp.ok) {
            const text = await resp.text().catch(() => '');
            throw new Error(`HTTP ${resp.status}: ${text.slice(0, 100)}`);
        }
        return await resp.json();
    } catch (e) {
        clearTimeout(id);
        if (e.name === 'AbortError') throw new Error('Request timed out');
        throw e;
    }
}

async function fetchWithRetry(url, options = {}) {
    const { retries = 2, timeout = 10000, onError = null, ...fetchOptions } = options;
    let lastError;

    for (let attempt = 0; attempt <= retries; attempt++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        try {
            const response = await fetch(url, {
                ...fetchOptions,
                signal: controller.signal,
            });
            clearTimeout(timeoutId);

            if (!response.ok) {
                const text = await response.text().catch(() => '');
                const error = new Error(`HTTP ${response.status}: ${text.slice(0, 120)}`);
                error.status = response.status;
                throw error;
            }

            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            lastError = error.name === 'AbortError' ? new Error('Request timed out') : error;

            const canRetry = attempt < retries && (!lastError.status || lastError.status >= 500);
            if (!canRetry) break;

            await new Promise(resolve => setTimeout(resolve, 500 * (2 ** attempt)));
        }
    }

    if (onError) onError(lastError);
    throw lastError;
}

async function fetchAriaData(url, options = {}) {
    const {
        timeout = 10000,
        retries = 1,
        ...fetchOptions
    } = options;

    const response = await fetchWithRetry(url, {
        retries,
        timeout,
        ...fetchOptions,
    });
    return await response.json();
}

/**
 * Show an error state with optional retry button in a container.
 * @param {string|Element} container - CSS selector or DOM element
 * @param {string} message - Error message to display
 * @param {Function} [retryFn] - Optional callback for retry button
 */
function showErrorState(container, message, retryFn) {
    const el = typeof container === 'string' ? document.querySelector(container) : container;
    if (!el) return;
    const esc = (window.escapeHtml && typeof window.escapeHtml === 'function')
        ? window.escapeHtml
        : (value) => String(value ?? '');
    const retryBtn = retryFn
        ? `<button onclick="(${retryFn.toString()})()" class="btn btn-sm btn-outline-primary mt-2">⟳ Retry</button>`
        : '';
    el.innerHTML = `
        <div class="text-center text-muted py-3">
            <div class="mb-2">⚠️ ${esc(message)}</div>
            ${retryBtn}
        </div>
    `;
}

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
    const [logsResp, globalResp] = await Promise.all([
        fetch(`${apiUrl}/litellm/spend?limit=${limit}&lite=true`),
        fetch(`${apiUrl}/litellm/global-spend`),
    ]);

    const rawLogs = await logsResp.json();
    const logs = rawLogs.logs || (Array.isArray(rawLogs) ? rawLogs : []);

    let global = null;
    try {
        global = await globalResp.json();
    } catch (_) {
        global = null;
    }

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

    if (global && typeof global === 'object' && !global.error) {
        totalSpend = Number(global.spend || 0);
        inputTokens = Number(global.input_tokens || 0);
        outputTokens = Number(global.output_tokens || 0);
        totalTokens = Number(global.total_tokens || (inputTokens + outputTokens));
        const apiRequests = Number(global.api_requests || 0);
        return {
            logs,
            totalSpend,
            todaySpend,
            weekSpend,
            monthSpend,
            inputTokens,
            outputTokens,
            totalTokens,
            requestCount: apiRequests,
        };
    }

    return { logs, totalSpend, todaySpend, weekSpend, monthSpend, inputTokens, outputTokens, totalTokens, requestCount: logs.length };
}
