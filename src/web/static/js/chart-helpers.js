window.ARIAChartHelpers = {
    renderChart(charts, canvasId, type, data, extra = {}) {
        if (charts[canvasId]) charts[canvasId].destroy();
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx) return;

        const isDoughnut = type === 'doughnut';
        const stacked = !!extra.stacked;
        const legendDisplay = typeof extra.legendDisplay === 'boolean' ? extra.legendDisplay : isDoughnut;
        const legendFontSize = extra.legendFontSize || 12;
        const tickFontSize = extra.tickFontSize || 11;

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: legendDisplay,
                    position: 'bottom',
                    labels: { color: '#9ca3af', font: { size: legendFontSize } },
                },
            },
            scales: isDoughnut ? {} : {
                x: {
                    stacked,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: {
                        color: '#9ca3af',
                        font: { size: tickFontSize },
                        ...(extra.maxTicksLimit ? { maxTicksLimit: extra.maxTicksLimit } : {}),
                    },
                },
                y: {
                    stacked,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9ca3af', font: { size: tickFontSize } },
                },
            },
        };

        if (extra.indexAxis) options.indexAxis = extra.indexAxis;

        charts[canvasId] = new Chart(ctx, { type, data, options });
    },
};