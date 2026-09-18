let pendingDeleteIds = [];

function getSelectedCheckboxes() {
    return Array.from(document.querySelectorAll('.history-select:checked'));
}

function updateBulkBar() {
    const selected = getSelectedCheckboxes();
    const count = selected.length;
    const total = document.querySelectorAll('.history-select').length;
    const countEl = document.getElementById('selected-count');
    const bulkBtn = document.getElementById('bulk-delete-btn');
    const selectAll = document.getElementById('select-all');

    if (countEl) countEl.textContent = `已选 ${count} 条`;
    if (bulkBtn) bulkBtn.disabled = count === 0;
    if (selectAll) {
        selectAll.checked = count > 0 && count === total;
        selectAll.indeterminate = count > 0 && count < total;
    }
}

function showDeleteDialog(message, ids) {
    pendingDeleteIds = ids;
    const dialog = document.getElementById('delete-dialog');
    const messageEl = document.getElementById('delete-dialog-message');
    if (!dialog || !messageEl) return;
    messageEl.textContent = message;
    dialog.hidden = false;
    dialog.setAttribute('aria-hidden', 'false');
    document.getElementById('delete-cancel')?.focus();
}

function hideDeleteDialog() {
    pendingDeleteIds = [];
    const dialog = document.getElementById('delete-dialog');
    if (!dialog) return;
    dialog.hidden = true;
    dialog.setAttribute('aria-hidden', 'true');
}

function submitDelete(ids) {
    const form = document.getElementById('bulk-delete-form');
    if (!form || ids.length === 0) return;
    form.innerHTML = '';
    ids.forEach((id) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'reading_id';
        input.value = String(id);
        form.appendChild(input);
    });
    form.submit();
}

function truncate(text, max = 40) {
    const t = (text || '').trim();
    return t.length > max ? `${t.slice(0, max)}…` : t;
}

document.getElementById('select-all')?.addEventListener('change', (e) => {
    const checked = e.target.checked;
    document.querySelectorAll('.history-select').forEach((cb) => {
        cb.checked = checked;
    });
    updateBulkBar();
});

document.querySelectorAll('.history-select').forEach((cb) => {
    cb.addEventListener('change', updateBulkBar);
    cb.addEventListener('click', (e) => e.stopPropagation());
});

document.getElementById('bulk-delete-btn')?.addEventListener('click', () => {
    const selected = getSelectedCheckboxes();
    if (selected.length === 0) return;
    const ids = selected.map((cb) => parseInt(cb.value, 10));
    const message = ids.length === 1
        ? `确定删除「${truncate(selected[0].dataset.question)}」？此操作不可恢复。`
        : `确定删除选中的 ${ids.length} 条占卜记录？此操作不可恢复。`;
    showDeleteDialog(message, ids);
});

document.querySelectorAll('.history-delete-one').forEach((btn) => {
    btn.addEventListener('click', () => {
        const id = parseInt(btn.dataset.id, 10);
        const question = btn.dataset.question || '';
        showDeleteDialog(
            `确定删除「${truncate(question)}」？此操作不可恢复。`,
            [id]
        );
    });
});

document.getElementById('delete-cancel')?.addEventListener('click', hideDeleteDialog);
document.querySelector('[data-dialog-dismiss]')?.addEventListener('click', hideDeleteDialog);
document.getElementById('delete-confirm')?.addEventListener('click', () => {
    const ids = [...pendingDeleteIds];
    hideDeleteDialog();
    submitDelete(ids);
});

document.addEventListener('keydown', (e) => {
    const dialog = document.getElementById('delete-dialog');
    if (dialog?.hidden) return;
    if (e.key === 'Escape') {
        e.preventDefault();
        hideDeleteDialog();
    }
});

updateBulkBar();
