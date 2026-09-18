const PRESETS = window.LAYOUT_PRESETS || {};

let initialSnapshot = null;
let allowLeave = false;
let pendingNavigation = null;

function buildLayout(preset, count) {
    count = Math.max(count, 1);
    if (preset === 'line') {
        return { cols: count, rows: 1, coords: Array.from({ length: count }, (_, i) => [i, 0]) };
    }
    if (preset === 'cross' && count === 5) {
        return { cols: 3, rows: 3, coords: [[1, 0], [0, 1], [1, 1], [2, 1], [1, 2]] };
    }
    if (preset === 'pyramid') {
        const coords = [];
        let row = 0;
        let remaining = count;
        while (remaining > 0) {
            const rowWidth = Math.min(row + 1, remaining);
            for (let c = 0; c < rowWidth; c++) coords.push([c, row]);
            remaining -= rowWidth;
            row += 1;
        }
        const maxCol = coords.length ? Math.max(...coords.map((c) => c[0])) + 1 : 1;
        return { cols: maxCol, rows: row, coords };
    }
    if (preset === 'columns') {
        const leftCount = Math.ceil(count / 2);
        const coords = [];
        for (let i = 0; i < count; i++) {
            const col = i < leftCount ? 0 : 1;
            const row = i < leftCount ? i : i - leftCount;
            coords.push([col, row]);
        }
        const rows = Math.max(leftCount, count - leftCount);
        return { cols: 2, rows, coords };
    }
    if (preset === 'horseshoe' && count === 7) {
        return { cols: 4, rows: 3, coords: [[0, 1], [0, 0], [1, 0], [2, 0], [3, 0], [3, 1], [3, 2]] };
    }
    const cols = Math.min(Math.max(count, 1), 4);
    const rows = Math.ceil(count / cols);
    const coords = Array.from({ length: count }, (_, i) => [i % cols, Math.floor(i / cols)]);
    return { cols, rows, coords };
}

function getSelectedPreset() {
    const checked = document.querySelector('input[name="layout_preset"]:checked');
    return checked ? checked.value : 'grid';
}

function getPositionCount() {
    return document.querySelectorAll('#position-rows .builder-position-row').length;
}

function getPositionLabels() {
    return Array.from(document.querySelectorAll('#position-rows input[name="label"]')).map(
        (el, i) => el.value.trim() || `坑位 ${i + 1}`
    );
}

function captureFormState() {
    const form = document.getElementById('builder-form');
    if (!form) return '';
    const positions = Array.from(document.querySelectorAll('#position-rows .builder-position-row')).map((row) => ({
        label: row.querySelector('input[name="label"]')?.value ?? '',
        hint: row.querySelector('input[name="hint"]')?.value ?? '',
    }));
    return JSON.stringify({
        name_zh: form.name_zh?.value ?? '',
        description: form.description?.value ?? '',
        tips: form.tips?.value ?? '',
        scene: form.scene?.value ?? '',
        layout_preset: getSelectedPreset(),
        positions,
    });
}

function isDirty() {
    if (allowLeave || initialSnapshot === null) return false;
    return captureFormState() !== initialSnapshot;
}

function saveSnapshot() {
    initialSnapshot = captureFormState();
}

function showLeaveDialog(targetUrl) {
    pendingNavigation = targetUrl;
    const dialog = document.getElementById('leave-dialog');
    if (!dialog) return;
    dialog.hidden = false;
    dialog.setAttribute('aria-hidden', 'false');
    document.getElementById('leave-cancel')?.focus();
}

function hideLeaveDialog() {
    pendingNavigation = null;
    const dialog = document.getElementById('leave-dialog');
    if (!dialog) return;
    dialog.hidden = true;
    dialog.setAttribute('aria-hidden', 'true');
}

function confirmLeave() {
    const target = pendingNavigation;
    allowLeave = true;
    hideLeaveDialog();
    if (target) {
        window.location.href = target;
    }
}

function shouldInterceptLink(link) {
    if (!link || !isDirty()) return false;
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return false;
    if (link.target === '_blank' || link.hasAttribute('download')) return false;
    try {
        const url = new URL(link.href, window.location.href);
        if (url.origin !== window.location.origin) return false;
        if (url.pathname === window.location.pathname && url.search === window.location.search) {
            return false;
        }
    } catch (_) {
        return false;
    }
    return true;
}

function initUnsavedGuard() {
    const form = document.getElementById('builder-form');
    if (!form) return;

    saveSnapshot();

    form.addEventListener('submit', () => {
        allowLeave = true;
    });

    document.addEventListener('click', (event) => {
        const link = event.target.closest('a[href]');
        if (!shouldInterceptLink(link)) return;
        event.preventDefault();
        event.stopPropagation();
        showLeaveDialog(link.href);
    }, true);

    document.getElementById('leave-cancel')?.addEventListener('click', hideLeaveDialog);
    document.getElementById('leave-confirm')?.addEventListener('click', confirmLeave);
    document.querySelector('[data-leave-dismiss]')?.addEventListener('click', hideLeaveDialog);

    document.addEventListener('keydown', (event) => {
        const dialog = document.getElementById('leave-dialog');
        if (dialog?.hidden) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            hideLeaveDialog();
        }
    });

    window.addEventListener('beforeunload', (event) => {
        if (!isDirty()) return;
        event.preventDefault();
        event.returnValue = '';
    });
}

function addPositionRow(label = '', hint = '') {
    const container = document.getElementById('position-rows');
    const count = container.children.length + 1;
    const row = document.createElement('div');
    row.className = 'builder-position-row';
    row.innerHTML = `
        <span class="position-num">${count}</span>
        <input type="text" name="label" class="form-input" placeholder="坑位名称（如：过去）" value="${label}">
        <input type="text" name="hint" class="form-input" placeholder="此位置回答什么问题" value="${hint}">`;
    container.appendChild(row);
    row.querySelectorAll('input').forEach((input) => {
        input.addEventListener('input', updatePreview);
    });
    updatePreview();
}

function removeLastPosition() {
    const container = document.getElementById('position-rows');
    if (container.children.length > 1) {
        container.lastElementChild.remove();
        renumberPositions();
        updatePreview();
    }
}

function renumberPositions() {
    document.querySelectorAll('#position-rows .position-num').forEach((el, i) => {
        el.textContent = i + 1;
    });
}

function updatePreview() {
    const preset = getSelectedPreset();
    const count = getPositionCount();
    const labels = getPositionLabels();
    const layout = buildLayout(preset, count);
    const preview = document.getElementById('layout-preview');
    if (!preview) return;

    preview.style.gridTemplateColumns = `repeat(${layout.cols}, 1fr)`;
    preview.innerHTML = '';

    labels.forEach((label, index) => {
        const coord = layout.coords[index] || [index % layout.cols, Math.floor(index / layout.cols)];
        const slot = document.createElement('div');
        slot.className = 'layout-slot builder-slot';
        slot.style.gridColumn = `${coord[0] + 1}`;
        slot.style.gridRow = `${coord[1] + 1}`;
        slot.innerHTML = `
            <span class="slot-label">${index + 1}. ${label}</span>
            <div class="slot-card builder-slot-card">${label}</div>`;
        preview.appendChild(slot);
    });
}

function applySpreadData(data, namePrefix = '') {
    document.getElementById('name_zh').value = namePrefix + (data.name_zh || '');
    document.getElementById('description').value = data.description || '';
    document.getElementById('tips').value = data.tips || '';
    if (data.scene) {
        document.getElementById('scene').value = data.scene;
    }
    const container = document.getElementById('position-rows');
    container.innerHTML = '';
    (data.positions || []).forEach((pos) => addPositionRow(pos.label, pos.hint));
    const layoutPreset = data.layout_preset || data.layout?.preset;
    if (layoutPreset && document.querySelector(`input[value="${layoutPreset}"]`)) {
        document.querySelector(`input[value="${layoutPreset}"]`).checked = true;
    }
    updatePreview();
}

async function loadTemplate() {
    const templateId = window.TEMPLATE_ID;
    if (!templateId) return;
    try {
        const res = await fetch(`/api/spreads/${templateId}`);
        if (!res.ok) return;
        const spread = await res.json();
        applySpreadData(
            {
                name_zh: spread.name_zh,
                description: spread.description,
                tips: spread.tips,
                layout_preset: spread.layout?.preset,
                positions: spread.positions,
            },
            '我的'
        );
    } catch (_) {
        /* ignore */
    }
}

function loadEditData() {
    if (!window.EDIT_DATA) return;
    applySpreadData(window.EDIT_DATA);
}

document.getElementById('add-position')?.addEventListener('click', () => addPositionRow());
document.getElementById('remove-position')?.addEventListener('click', removeLastPosition);
document.querySelectorAll('input[name="layout_preset"]').forEach((input) => {
    input.addEventListener('change', updatePreview);
});

const DEFAULT_POSITIONS = [
    ['过去', '影响当前的根源'],
    ['现在', '你此刻的状态'],
    ['未来', '可能的发展趋势'],
];

document.addEventListener('DOMContentLoaded', async () => {
    if (window.EDIT_DATA) {
        loadEditData();
    } else if (!window.TEMPLATE_ID) {
        DEFAULT_POSITIONS.forEach(([label, hint]) => addPositionRow(label, hint));
    } else {
        await loadTemplate();
    }
    initUnsavedGuard();
});
