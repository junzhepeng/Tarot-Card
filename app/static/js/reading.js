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

document.addEventListener('DOMContentLoaded', () => {
    initQuestionForm();
    initReadingForm();

    document.querySelectorAll('.card-select').forEach((select) => {
        select.addEventListener('change', function () {
            const idx = this.dataset.index;
            const reversed = document.querySelector(`input[name="reversed_${idx}"]`);
            if (reversed && this.value) {
                reversed.parentElement.style.opacity = '1';
            }
        });
    });
});
