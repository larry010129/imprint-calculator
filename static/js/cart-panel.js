(function () {
  const wrap = document.getElementById('nav-cart-wrap');
  const trigger = document.getElementById('nav-cart-trigger');
  const panel = document.getElementById('cart-panel');
  const body = document.getElementById('cart-panel-body');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;

  if (!wrap || !trigger || !panel || !body) return;

  let loaded = false;

  function t(key, fallback) {
    return (window.t && window.t(key)) || fallback;
  }

  function escapeHtml(text) {
    const el = document.createElement('span');
    el.textContent = text || '';
    return el.innerHTML;
  }

  function formatPrice(n) {
    if (n == null) return '—';
    return 'NT$ ' + Number(n).toLocaleString('zh-TW', { maximumFractionDigits: 0 });
  }

  function renderEmpty() {
    body.innerHTML = '<p class="cart-panel-empty">' + escapeHtml(t('cart_panel_empty', '購物車目前是空的。')) + '</p>';
  }

  function renderItem(item) {
    const li = document.createElement('li');
    li.className = 'cart-panel-item';
    li.dataset.id = item.id;

    const thumb = item.image_url
      ? '<img class="cart-panel-thumb" src="' + escapeHtml(item.image_url) + '" alt="" loading="lazy">'
      : '<span class="cart-panel-thumb cart-panel-thumb--empty" aria-hidden="true">💎</span>';

    const meta = [item.specs?.category, item.specs?.carat ? item.specs.carat + ' ct' : null]
      .filter(Boolean).join(' · ');

    li.innerHTML =
      '<a class="cart-panel-link" href="/cart">' +
        thumb +
        '<span class="cart-panel-content">' +
          '<span class="cart-panel-title">' + escapeHtml(item.summary || '') + '</span>' +
          (meta ? '<span class="cart-panel-meta">' + escapeHtml(meta) + '</span>' : '') +
          '<span class="cart-panel-price">' + escapeHtml(formatPrice(item.total_price)) + '</span>' +
        '</span>' +
      '</a>' +
      '<div class="cart-panel-actions">' +
        '<a class="cart-panel-action" href="/cart?detail=' + item.id + '">' + escapeHtml(t('cart_detail', '明細')) + '</a>' +
        '<a class="cart-panel-action" href="' + escapeHtml(item.edit_url || '/cart/' + item.id + '/edit') + '">' + escapeHtml(t('cart_edit', '編輯')) + '</a>' +
      '</div>';

    return li;
  }

  function renderList(items) {
    if (!items.length) {
      renderEmpty();
      return;
    }
    const ul = document.createElement('ul');
    ul.className = 'cart-panel-list';
    items.forEach(item => ul.appendChild(renderItem(item)));
    body.innerHTML = '';
    body.appendChild(ul);
  }

  async function loadCart() {
    body.innerHTML = '<p class="cart-panel-loading">' + escapeHtml(t('notifications_loading', '載入中…')) + '</p>';
    try {
      const res = await fetch('/api/cart', {
        headers: { 'X-CSRFToken': csrf || '' },
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      renderList(data.items || []);
      if (typeof window.updateCartBadge === 'function') window.updateCartBadge(data.count);
      loaded = true;
    } catch (err) {
      console.error(err);
      body.innerHTML = '<p class="cart-panel-empty">' + escapeHtml(t('generic_error', '發生錯誤')) + '</p>';
    }
  }

  function openPanel() {
    panel.classList.add('is-open');
    trigger.setAttribute('aria-expanded', 'true');
    if (!loaded) loadCart();
  }

  function closePanel() {
    panel.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
  }

  wrap.addEventListener('mouseenter', () => openPanel());

  wrap.addEventListener('mouseleave', () => {
    closePanel();
  });

  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) {
      closePanel();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePanel();
  });

  document.addEventListener('langchange', () => {
    if (panel.classList.contains('is-open') || wrap.matches(':hover')) {
      loaded = false;
      loadCart();
    }
  });

  window.refreshCartPanel = function () {
    loaded = false;
    if (panel.classList.contains('is-open') || wrap.matches(':hover')) loadCart();
  };
})();
