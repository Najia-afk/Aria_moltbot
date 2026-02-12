/**
 * Shared utility helpers for Aria web UI.
 * Included globally via base.html — no need to redefine in individual templates.
 */

// ── HTML Escaping ───────────────────────────────────────────────────────────

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

// ── Date / Time Formatting ──────────────────────────────────────────────────

function formatRelativeTime(date) {
    if (!(date instanceof Date)) date = new Date(date);
    const now = new Date();
    const diff = now - date;

    if (diff < 0) {
        const absDiff = Math.abs(diff);
        const seconds = Math.floor(absDiff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours   = Math.floor(minutes / 60);
        const days    = Math.floor(hours / 24);

        if (seconds < 60) return 'in <1m';
        if (minutes < 60) return `in ${minutes}m`;
        if (hours < 24)   return `in ${hours}h ${minutes % 60}m`;
        if (days < 7)     return `in ${days}d ${hours % 24}h`;
        return date.toLocaleDateString();
    }

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours   = Math.floor(minutes / 60);
    const days    = Math.floor(hours / 24);

    if (seconds < 60) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24)   return `${hours}h ago`;
    if (days < 7)     return `${days}d ago`;
    return date.toLocaleDateString();
}

function formatDate(isoString) {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString();
}

function formatDateTime(isoString) {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString();
}

function formatTime(ts) {
    if (!ts) return '';
    return new Date(ts).toLocaleString();
}

function showToast(message, type = 'info') {
    const existingToast = document.getElementById('toast');
    if (existingToast) {
        existingToast.textContent = message;
        existingToast.className = `toast ${type} show`;
        setTimeout(() => {
            existingToast.classList.remove('show');
        }, 3000);
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 24px;
        background: ${type === 'error' ? 'var(--danger)' : 'var(--success)'};
        color: white;
        border-radius: var(--radius-md);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function closeModal(id) {
    if (!id) return;
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('active');
    }
}
