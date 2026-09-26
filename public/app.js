// Progressive enhancement for the listing generator and copy buttons.
(() => {
  'use strict';

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return;
      } catch {
        // Permission denied or unsupported: fall through to the legacy path.
      }
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    if (!ok) throw new Error('copy failed');
  }

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-copy-text]');
    if (!button) return;
    const original = button.textContent;
    try {
      await copyText(button.dataset.copyText);
      button.textContent = 'Copied!';
      button.classList.add('copied');
    } catch {
      button.textContent = 'Press Ctrl+C';
    }
    setTimeout(() => {
      button.textContent = original;
      button.classList.remove('copied');
    }, 1600);
  });

  // Live character counter for textareas marked with data-counter.
  for (const field of document.querySelectorAll('[data-counter]')) {
    const counter = field.parentElement.querySelector('.counter');
    const update = () => {
      if (counter) counter.textContent = `${field.value.length} / ${field.maxLength}`;
    };
    field.addEventListener('input', update);
    update();
  }

  const form = document.getElementById('generate-form');
  if (!form) return;

  const result = document.getElementById('result');
  const errorBox = form.querySelector('.form-error');
  const submit = form.querySelector('button[type="submit"]');
  const loadingMessages = [
    'Choosing the keywords shoppers search for',
    'Writing a title that ranks',
    'Crafting your description',
    'Picking the best tags',
    'Checking marketplace limits',
  ];

  function setCredits(n) {
    if (typeof n !== 'number') return;
    for (const el of document.querySelectorAll('[data-credits]')) el.textContent = String(n);
  }

  function showError(message) {
    errorBox.innerHTML = '';
    errorBox.append(document.createTextNode(message));
    errorBox.hidden = false;
  }

  function showLoading() {
    let i = 0;
    result.innerHTML = '<div class="result-loading"><p><strong class="msg"></strong><span class="dots"></span></p><p class="muted">This usually takes 10 to 30 seconds.</p></div>';
    const msg = result.querySelector('.msg');
    msg.textContent = loadingMessages[0];
    return setInterval(() => {
      i = (i + 1) % loadingMessages.length;
      msg.textContent = loadingMessages[i];
    }, 3500);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.hidden = true;

    const payload = Object.fromEntries(new FormData(form).entries());
    submit.disabled = true;
    submit.innerHTML = '<span class="spinner" aria-hidden="true"></span> Writing…';
    const previous = result.innerHTML;
    const ticker = showLoading();
    if (window.matchMedia('(max-width: 900px)').matches) {
      result.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      });
      const data = await res.json().catch(() => ({}));
      setCredits(data.credits);

      if (res.status === 401) {
        window.location.href = '/login?next=/app';
        return;
      }
      if (!res.ok) {
        result.innerHTML = previous;
        showError(data.error || 'Something went wrong. Please try again.');
        if (data.outOfCredits) document.getElementById('buy')?.scrollIntoView({ behavior: 'smooth' });
        return;
      }
      result.innerHTML = data.html;
    } catch {
      result.innerHTML = previous;
      showError('Network error. Check your connection and try again.');
    } finally {
      clearInterval(ticker);
      submit.disabled = false;
      submit.textContent = submit.dataset.label;
    }
  });
})();
