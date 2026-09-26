window.ARIAChartHelpers = {
    // Category palette shared with the CSS chart-N tokens (variables.css) so
    // callers that want consistent series colors don't have to hardcode hex.
    palette() {
        const style = getComputedStyle(document.documentElement);
        const vals = [];
        for (let i = 1; i <= 8; i++) {
            const v = style.getPropertyValue(`--chart-${i}`).trim();
            if (v) vals.push(v);
        }
        return vals.length ? vals : ['#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#06b6d4', '#ef4444', '#ec4899', '#64748b'];
    },

    _themeColors() {
        const style = getComputedStyle(document.documentElement);
        return {
            text: style.getPropertyValue('--text-secondary').trim() || '#9ca3af',
            grid: style.getPropertyValue('--border-subtle').trim() || 'rgba(255,255,255,0.05)',
        };
    },

    // Tracks every chart created here so toggleTheme() can live-restyle them
    // without each page needing to re-fetch/re-render its own data.
    _instances: new Set(),

    _applyTheme(chart) {
        const { text, grid } = this._themeColors();
        if (chart.options.plugins?.legend?.labels) {
            chart.options.plugins.legend.labels.color = text;
        }
        for (const axis of ['x', 'y']) {
            const scale = chart.options.scales?.[axis];
            if (!scale) continue;
            if (scale.ticks) scale.ticks.color = text;
            if (scale.grid) scale.grid.color = grid;
        }
        chart.update('none');
    },

    refreshTheme() {
        this._instances.forEach(chart => {
            try { this._applyTheme(chart); } catch (e) { /* chart may be destroyed */ }
        });
    },

    renderChart(charts, canvasId, type, data, extra = {}) {
        if (charts[canvasId]) {
            this._instances.delete(charts[canvasId]);
            charts[canvasId].destroy();
        }
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx) return;

        const isDoughnut = type === 'doughnut';
        const stacked = !!extra.stacked;
        const legendDisplay = typeof extra.legendDisplay === 'boolean' ? extra.legendDisplay : isDoughnut;
        const legendFontSize = extra.legendFontSize || 12;
        const tickFontSize = extra.tickFontSize || 11;
        const { text, grid } = this._themeColors();

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: legendDisplay,
                    position: 'bottom',
                    labels: { color: text, font: { size: legendFontSize } },
                },
            },
            scales: isDoughnut ? {} : {
                x: {
                    stacked,
                    grid: { color: grid },
                    ticks: {
                        color: text,
                        font: { size: tickFontSize },
                        ...(extra.maxTicksLimit ? { maxTicksLimit: extra.maxTicksLimit } : {}),
                    },
                },
                y: {
                    stacked,
                    grid: { color: grid },
                    ticks: { color: text, font: { size: tickFontSize } },
                },
            },
        };

        if (extra.indexAxis) options.indexAxis = extra.indexAxis;

        const chart = new Chart(ctx, { type, data, options });
        charts[canvasId] = chart;
        this._instances.add(chart);
        return chart;
    },
};

window.addEventListener('aria-theme-changed', () => window.ARIAChartHelpers.refreshTheme());