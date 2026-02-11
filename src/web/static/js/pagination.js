/**
 * Shared Pagination Component for Aria Dashboard
 * Usage:
 *   const pager = new AriaPagination('containerId', {
 *     onPageChange: (page, limit) => loadData(page, limit),
 *     limit: 25
 *   });
 *   pager.update({ page: 1, pages: 10, total: 250, limit: 25 });
 */
class AriaPagination {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.onPageChange = options.onPageChange || (() => {});
        this.currentPage = 1;
        this.totalPages = 1;
        this.total = 0;
        this.limit = options.limit || 25;
        this.limitOptions = options.limitOptions || [25, 50, 100];
    }

    update(data) {
        this.currentPage = data.page || 1;
        this.totalPages = data.pages || 1;
        this.total = data.total || 0;
        this.limit = data.limit || this.limit;
        this.render();
    }

    render() {
        if (!this.container) return;
        if (this.totalPages <= 1) {
            this.container.innerHTML = `<div class="pagination-info">Showing ${this.total} items</div>`;
            return;
        }

        const start = (this.currentPage - 1) * this.limit + 1;
        const end = Math.min(this.currentPage * this.limit, this.total);

        let pages = [];
        const range = 2;
        for (let i = 1; i <= this.totalPages; i++) {
            if (i === 1 || i === this.totalPages ||
                (i >= this.currentPage - range && i <= this.currentPage + range)) {
                pages.push(i);
            } else if (pages[pages.length - 1] !== '...') {
                pages.push('...');
            }
        }

        const id = this.container.id;
        this.container.innerHTML = `
            <div class="aria-pagination">
                <span class="pagination-info">
                    ${start}\u2013${end} of ${this.total}
                </span>
                <div class="pagination-controls">
                    <button class="page-btn" ${this.currentPage <= 1 ? 'disabled' : ''}
                            data-pager="${id}" data-page="${this.currentPage - 1}">\u2039</button>
                    ${pages.map(p => p === '...'
                        ? '<span class="page-ellipsis">\u2026</span>'
                        : `<button class="page-btn ${p === this.currentPage ? 'active' : ''}"
                                   data-pager="${id}" data-page="${p}">${p}</button>`
                    ).join('')}
                    <button class="page-btn" ${this.currentPage >= this.totalPages ? 'disabled' : ''}
                            data-pager="${id}" data-page="${this.currentPage + 1}">\u203A</button>
                </div>
                <select class="page-limit-select" data-pager="${id}" data-action="limit">
                    ${this.limitOptions.map(l =>
                        `<option value="${l}" ${l === this.limit ? 'selected' : ''}>${l}/page</option>`
                    ).join('')}
                </select>
            </div>
        `;

        // Attach event listeners
        this.container.querySelectorAll('.page-btn:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => this.goTo(parseInt(btn.dataset.page)));
        });
        const limitSelect = this.container.querySelector('.page-limit-select');
        if (limitSelect) {
            limitSelect.addEventListener('change', (e) => this.changeLimit(parseInt(e.target.value)));
        }
    }

    goTo(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.onPageChange(page, this.limit);
    }

    changeLimit(newLimit) {
        this.limit = newLimit;
        this.currentPage = 1;
        this.onPageChange(1, newLimit);
    }
}
