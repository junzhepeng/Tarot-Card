async function requestAI(readingId) {
    const btn = document.getElementById('ai-btn');
    const loading = document.getElementById('ai-loading');
    const result = document.getElementById('ai-result');

    btn.disabled = true;
    loading.style.display = 'inline';
    result.style.display = 'none';

    try {
        const response = await fetch('/api/ai-reading', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reading_id: readingId }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '请求失败');
        }

        const data = await response.json();
        result.textContent = data.summary;
        result.style.display = 'block';
        btn.textContent = '重新生成 AI 解读';
    } catch (e) {
        alert('AI 解读失败：' + e.message);
    } finally {
        btn.disabled = false;
        loading.style.display = 'none';
    }
}

function showFieldError(errorEl, inputEl) {
    if (errorEl) errorEl.classList.add('show');
    if (inputEl) inputEl.classList.add('input-error');
}

function hideFieldError(errorEl, inputEl) {
    if (errorEl) errorEl.classList.remove('show');
    if (inputEl) inputEl.classList.remove('input-error');
}

function initQuestionForm() {
    const form = document.getElementById('question-form');
    if (!form) return;

    const input = document.getElementById('question-input');
    const error = document.getElementById('question-error');

    input.addEventListener('input', () => hideFieldError(error, input));

    form.addEventListener('submit', (e) => {
        if (!input.value.trim()) {
            e.preventDefault();
            showFieldError(error, input);
            input.focus();
        }
    });
}

function initReadingForm() {
    const form = document.getElementById('reading-form');
    if (!form) return;

    const error = document.getElementById('cards-error');
    const selects = form.querySelectorAll('.card-select');

    selects.forEach((sel) => {
        sel.addEventListener('change', () => {
            sel.classList.remove('input-error');
            const allFilled = [...selects].every((s) => s.value);
            if (allFilled) hideFieldError(error);
        });
    });

    form.addEventListener('submit', (e) => {
        const empty = [...selects].filter((s) => !s.value);
        if (empty.length) {
            e.preventDefault();
            showFieldError(error);
            empty[0].classList.add('input-error');
            empty[0].focus();
            empty[0].closest('.draw-input-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
}

function updateCardPreview(select) {
    const idx = select.dataset.index;
    const preview = document.getElementById(`preview-${idx}`);
    if (!preview) return;

    const option = select.options[select.selectedIndex];
    const imageUrl = option?.dataset?.image;
    const reversed = document.querySelector(`input[name="reversed_${idx}"]`)?.checked;

    if (!imageUrl) {
        preview.innerHTML = '';
        preview.classList.remove('has-preview');
        return;
    }

    preview.classList.add('has-preview');
    preview.innerHTML = `
        <div class="card-face card-face-sm${reversed ? ' is-reversed' : ''}">
            <div class="card-face-inner" style="width:80px;height:120px">
                <img src="${imageUrl}" alt="" class="card-face-img" width="80" height="120" loading="lazy">
            </div>
        </div>`;
}

const RECENT_KEY = 'tarot_recent_cards';
const FAVORITES_KEY = 'tarot_favorite_cards';
const MAX_RECENT = 5;

let cardsCache = null;

function getRecent() {
    try {
        return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    } catch {
        return [];
    }
}

function addRecent(cardId) {
    if (!cardId) return;
    const recent = getRecent().filter((id) => id !== cardId);
    recent.unshift(cardId);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
}

function getFavorites() {
    try {
        return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]');
    } catch {
        return [];
    }
}

function toggleFavorite(cardId) {
    const favs = getFavorites();
    const idx = favs.indexOf(cardId);
    if (idx >= 0) favs.splice(idx, 1);
    else favs.push(cardId);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favs));
}

function filterSelectOptions(select, query) {
    const q = query.trim().toLowerCase();
    [...select.options].forEach((opt) => {
        if (!opt.value) {
            opt.hidden = false;
            return;
        }
        const search = (opt.dataset.search || opt.textContent || '').toLowerCase();
        opt.hidden = q && !search.includes(q);
    });
}

function renderQuickPicks(container, select) {
    if (!container) return;
    const recent = getRecent();
    const favorites = getFavorites();
    const ids = [...new Set([...favorites, ...recent])].slice(0, 8);
    if (!ids.length) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = ids
        .map((id) => {
            const opt = [...select.options].find((o) => o.value === id);
            if (!opt) return '';
            const label = opt.textContent.split('(')[0].trim();
            const isFav = favorites.includes(id);
            return `<button type="button" class="quick-pick-btn${isFav ? ' is-fav' : ''}" data-card-id="${id}" title="${isFav ? '收藏' : '最近使用'}">${label}</button>`;
        })
        .join('');

    container.querySelectorAll('.quick-pick-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            select.value = btn.dataset.cardId;
            select.dispatchEvent(new Event('change'));
            const picker = select.closest('.card-picker');
            const search = picker?.querySelector('.card-search');
            if (search) search.value = '';
            filterSelectOptions(select, '');
        });
        btn.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            toggleFavorite(btn.dataset.cardId);
            renderQuickPicks(container, select);
        });
    });
}

function initCardPicker(picker) {
    if (!picker || picker.dataset.initialized === '1') return;
    const select = picker.querySelector('.card-select, .clarifier-card-select');
    const search = picker.querySelector('.card-search');
    const quickPicks = picker.querySelector('.quick-picks');
    if (!select) return;

    picker.dataset.initialized = '1';

    if (search) {
        search.addEventListener('input', () => filterSelectOptions(select, search.value));
        search.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const visible = [...select.options].find((o) => o.value && !o.hidden);
                if (visible) {
                    select.value = visible.value;
                    select.dispatchEvent(new Event('change'));
                    search.value = '';
                    filterSelectOptions(select, '');
                }
            }
        });
    }

    select.addEventListener('change', () => {
        if (select.value) addRecent(select.value);
        renderQuickPicks(quickPicks, select);
        const idx = select.dataset.index;
        if (idx === 'daily') {
            const reversed = document.querySelector('.daily-form .reversed-check');
            updateClarifierPreview(select, document.getElementById('preview-daily'), reversed);
        } else if (idx !== undefined) {
            updateCardPreview(select);
        }
    });

    renderQuickPicks(quickPicks, select);
}

function initCardPickers() {
    document.querySelectorAll('.card-picker').forEach(initCardPicker);
}

async function loadCardsCache() {
    if (cardsCache) return cardsCache;
    const response = await fetch('/api/cards');
    if (!response.ok) throw new Error('加载牌列表失败');
    cardsCache = await response.json();
    return cardsCache;
}

async function populateClarifierSelect(select) {
    if (select.dataset.populated === '1') return;
    const cards = await loadCardsCache();
    const placeholder = select.querySelector('option[value=""]');
    select.innerHTML = '';
    if (placeholder) {
        select.appendChild(placeholder);
    } else {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '选择澄清牌...';
        select.appendChild(opt);
    }
    cards.forEach((card) => {
        const opt = document.createElement('option');
        opt.value = card.id;
        opt.textContent = `${card.name_zh} (${card.name_en})`;
        opt.dataset.image = card.image_url || `/static/cards/${card.id}.jpg`;
        opt.dataset.search = `${card.name_zh} ${card.name_en} ${card.id} ${card.number || ''} ${card.suit || ''}`.toLowerCase();
        select.appendChild(opt);
    });
    select.dataset.populated = '1';
    const picker = select.closest('.card-picker');
    if (picker) initCardPicker(picker);
}

function updateClarifierPreview(select, preview, reversedCheck) {
    const option = select.options[select.selectedIndex];
    const imageUrl = option?.dataset?.image;
    const reversed = reversedCheck?.checked;

    if (!imageUrl) {
        preview.innerHTML = '';
        preview.classList.remove('has-preview');
        return;
    }

    preview.classList.add('has-preview');
    preview.innerHTML = `
        <div class="card-face card-face-sm${reversed ? ' is-reversed' : ''}">
            <div class="card-face-inner" style="width:80px;height:120px">
                <img src="${imageUrl}" alt="" class="card-face-img" width="80" height="120" loading="lazy">
            </div>
        </div>`;
}

function initClarifierForms() {
    const list = document.getElementById('interpretation-list');
    if (!list) return;

    list.querySelectorAll('.btn-add-clarifier').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const positionIndex = btn.dataset.positionIndex;
            const form = document.getElementById(`clarifier-form-${positionIndex}`);
            if (!form) return;
            const select = form.querySelector('.clarifier-card-select');
            try {
                if (select) {
                    select.disabled = true;
                    await populateClarifierSelect(select);
                    select.disabled = false;
                }
            } catch (err) {
                alert(err.message);
                if (select) select.disabled = false;
                return;
            }
            form.style.display = 'block';
            btn.style.display = 'none';
        });
    });

    list.querySelectorAll('.btn-cancel-clarifier').forEach((btn) => {
        btn.addEventListener('click', () => {
            const form = btn.closest('.clarifier-form');
            const wrap = btn.closest('.clarifier-form-wrap');
            if (!form || !wrap) return;
            form.reset();
            form.style.display = 'none';
            const preview = form.querySelector('.clarifier-preview');
            if (preview) {
                preview.innerHTML = '';
                preview.classList.remove('has-preview');
            }
            wrap.querySelector('.btn-add-clarifier').style.display = '';
        });
    });

    list.querySelectorAll('.clarifier-form').forEach((form) => {
        const select = form.querySelector('.clarifier-card-select');
        const reversedCheck = form.querySelector('.clarifier-reversed-check');
        const preview = form.querySelector('.clarifier-preview');

        select?.addEventListener('change', () => {
            updateClarifierPreview(select, preview, reversedCheck);
        });
        reversedCheck?.addEventListener('change', () => {
            updateClarifierPreview(select, preview, reversedCheck);
        });

        form.addEventListener('submit', (e) => {
            if (!select?.value) {
                e.preventDefault();
                select?.focus();
                return;
            }
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '保存中...';
            }
        });
    });

    list.querySelectorAll('.clarifier-delete-form').forEach((form) => {
        form.addEventListener('submit', (e) => {
            if (!confirm('确定删除这张澄清牌？')) {
                e.preventDefault();
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initQuestionForm();
    initReadingForm();
    initClarifierForms();
    initCardPickers();

    document.querySelectorAll('#reading-form .card-select').forEach((select) => {
        select.addEventListener('change', function () {
            const idx = this.dataset.index;
            const reversed = document.querySelector(`input[name="reversed_${idx}"]`);
            if (reversed && this.value) {
                reversed.parentElement.style.opacity = '1';
            }
        });
    });

    document.querySelectorAll('.reversed-check').forEach((checkbox) => {
        checkbox.addEventListener('change', function () {
            const idx = this.name.replace('reversed_', '');
            const select = document.querySelector(`select[data-index="${idx}"]`);
            if (select) updateCardPreview(select);
        });
    });

    const dailyReversed = document.querySelector('.daily-form input[name="is_reversed"]');
    const dailySelect = document.querySelector('select[data-index="daily"]');
    if (dailyReversed && dailySelect) {
        dailyReversed.addEventListener('change', () => {
            updateClarifierPreview(dailySelect, document.getElementById('preview-daily'), dailyReversed);
        });
    }
});
