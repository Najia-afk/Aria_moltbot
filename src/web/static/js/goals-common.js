function renderGoalCard(goal, options = {}) {
    const view = options.view || 'goals';
    if (view === 'board') {
        return renderBoardGoalCard(goal);
    }
    return renderGoalsPageCard(goal, options.priorityLabels || {});
}

function renderBoardGoalCard(goal) {
    const priorityLabels = { 1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4', 5: 'P5' };
    const progress = Math.round(goal.progress || 0);
    const tags = (goal.tags || []).map(tag => `<span class="goal-tag">#${escapeHtml(tag)}</span>`).join('');
    const dueBadge = goal.due_date ? formatBoardDueBadge(goal.due_date) : '';

    return `<div class="goal-card" draggable="true" data-goal-id="${escapeHtml(goal.goal_id)}"
                ondragstart="onDragStart(event)" ondragend="onDragEnd(event)">
        <div class="goal-card-header">
            <span class="priority-badge priority-${goal.priority}">${priorityLabels[goal.priority] || 'P?'}</span>
            ${dueBadge}
        </div>
        <div class="goal-card-title" title="${escapeHtml(goal.title)}">${escapeHtml(goal.title)}</div>
        <div class="progress-bar-mini"><div class="fill" style="width:${progress}%"></div></div>
        <div class="goal-card-meta">
            <span style="font-size:0.65rem; color:var(--text-muted)">${progress}%</span>
            ${goal.assigned_to ? `<span style="font-size:0.65rem; color:var(--text-muted)">👤 ${escapeHtml(goal.assigned_to)}</span>` : ''}
        </div>
        ${tags ? `<div class="goal-tags">${tags}</div>` : ''}
    </div>`;
}

function renderGoalsPageCard(goal, priorityLabels) {
    const priority = goal.priority || 3;
    const progress = goal.progress || 0;
    const status = goal.status || 'active';
    const priorityInfo = priorityLabels[priority] || priorityLabels[3] || { text: 'Medium', emoji: '🟡' };

    const dueInfo = getGoalsDueInfo(goal.due_date);
    const createdDate = goal.created_at ? new Date(goal.created_at).toLocaleDateString() : 'Unknown';

    return `
        <div class="goal-card priority-${priority}" data-id="${goal.id}">
            <div class="goal-header">
                <h3 class="goal-title">${escapeHtml(goal.title || 'Untitled Goal')}</h3>
                <div class="goal-badges">
                    <span class="priority-badge p${priority}">${priorityInfo.emoji} ${priorityInfo.text}</span>
                    <span class="status-badge ${status}">${status}</span>
                </div>
            </div>

            ${goal.description ? `<p class="goal-description">${escapeHtml(goal.description)}</p>` : ''}

            <div class="goal-progress">
                <div class="progress-header">
                    <span class="progress-label">Progress</span>
                    <span class="progress-value-display">${progress}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progress}%"></div>
                </div>
            </div>

            <div class="goal-meta">
                <div class="goal-dates">
                    <span class="goal-date">📅 Created: ${createdDate}</span>
                    ${dueInfo.text ? `<span class="goal-date ${dueInfo.className}">🎯 ${dueInfo.text}</span>` : ''}
                </div>
                <div class="goal-actions">
                    <button class="goal-action-btn" onclick="openEditGoalModal(${goal.id})" title="Edit">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    ${status !== 'completed' ? `
                    <button class="goal-action-btn complete" onclick="completeGoal(${goal.id})" title="Complete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                    </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function getGoalsDueInfo(dueDate) {
    if (!dueDate) {
        return { className: '', text: '' };
    }

    const target = new Date(dueDate);
    const now = new Date();
    const daysUntil = Math.ceil((target - now) / (1000 * 60 * 60 * 24));

    if (daysUntil < 0) {
        return {
            className: 'overdue',
            text: `Overdue by ${Math.abs(daysUntil)} day${Math.abs(daysUntil) !== 1 ? 's' : ''}`,
        };
    }

    if (daysUntil <= 3) {
        return {
            className: 'due-soon',
            text: daysUntil === 0 ? 'Due today!' : `Due in ${daysUntil} day${daysUntil !== 1 ? 's' : ''}`,
        };
    }

    return {
        className: '',
        text: `Due ${target.toLocaleDateString()}`,
    };
}

function formatBoardDueBadge(dateStr) {
    const due = new Date(dateStr);
    const now = new Date();
    const diff = (due - now) / (1000 * 60 * 60);
    const cls = diff < 0 ? 'overdue' : '';
    let label;
    if (diff < 0) label = 'Overdue';
    else if (diff < 24) label = `${Math.round(diff)}h`;
    else label = `${Math.round(diff / 24)}d`;
    return `<span class="due-badge ${cls}">⏰ ${label}</span>`;
}