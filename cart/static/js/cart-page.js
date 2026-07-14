(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const list = document.getElementById('cart-list');
  const selectAll = document.getElementById('cart-select-all');
  const selectedLabel = document.getElementById('cart-selected-label');
  const selectedTotal = document.getElementById('cart-selected-total');
  const checkoutBtn = document.getElementById('cart-checkout-btn');
  const detailDialog = document.getElementById('cart-detail-dialog');
  const detailBody = document.getElementById('cart-detail-body');
  const detailClose = document.getElementById('cart-detail-close');

  if (!list) return;

  function t(key, fallback, args) {
    if (window.t) {
      const out = window.t(key, args);
      if (out) return out;
    }
    if (args && fallback && fallback.includes('{count}')) {
      return fallback.replace('{count}', args.count ?? '');
    }
    return fallback;
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

  function rowCheckboxes() {
    return [...list.querySelectorAll('.cart-item-checkbox')];
  }

  function selectedRows() {
    return rowCheckboxes().filter(cb => cb.checked);
  }

  function updateSelectionUI() {
    const selected = selectedRows();
    const count = selected.length;
    let total = 0;
    selected.forEach(cb => {
      const row = cb.closest('.cart-item-row');
      total += Number(row?.dataset.price || 0);
    });

    if (selectedLabel) {
      const tpl = (window.t && window.t('cart_selected_count')) || '已選 {count} 件';
      selectedLabel.textContent = tpl.replace('{count}', String(count));
    }
    if (selectedTotal) selectedTotal.textContent = formatPrice(total);
    if (checkoutBtn) checkoutBtn.disabled = count === 0;

    if (selectAll) {
      const all = rowCheckboxes();
      selectAll.checked = all.length > 0 && count === all.length;
      selectAll.indeterminate = count > 0 && count < all.length;
    }
  }

  selectAll?.addEventListener('change', () => {
    const checked = selectAll.checked;
    rowCheckboxes().forEach(cb => { cb.checked = checked; });
    updateSelectionUI();
  });

  list.addEventListener('change', (e) => {
    if (e.target.classList.contains('cart-item-checkbox')) updateSelectionUI();
  });

  list.addEventListener('click', async (e) => {
    const removeBtn = e.target.closest('.cart-item-remove');
    if (removeBtn) {
      const id = removeBtn.dataset.id;
      if (!confirm(t('cart_remove_confirm', '確定要移除此品項嗎？'))) return;
      try {
        const res = await fetch('/api/cart/' + id, {
          method: 'DELETE',
          headers: { 'X-CSRFToken': csrf || '' },
        });
        const data = await res.json();
        if (data.success) {
          document.getElementById('cart-item-' + id)?.remove();
          if (typeof window.updateCartBadge === 'function') window.updateCartBadge(data.count);
          if (!list.querySelector('.cart-item-row')) window.location.reload();
          else updateSelectionUI();
        } else {
          alert(data.message || 'Remove failed');
        }
      } catch (err) {
        alert(t('generic_error', '發生錯誤'));
      }
      return;
    }

    const detailBtn = e.target.closest('.cart-detail-btn');
    if (detailBtn) {
      openDetailModal(detailBtn.dataset.id);
    }
  });

  checkoutBtn?.addEventListener('click', async () => {
    if (checkoutBtn.disabled) return;
    const ids = selectedRows().map(cb => Number(cb.value));
    checkoutBtn.disabled = true;
    checkoutBtn.classList.add('is-loading');
    try {
      const res = await fetch('/api/cart/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
        body: JSON.stringify({ item_ids: ids }),
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      if (data.success) {
        if (typeof window.updateCartBadge === 'function') {
          const left = list.querySelectorAll('.cart-item-row').length - ids.length;
          window.updateCartBadge(Math.max(0, left));
        }
        window.location.href = '/success';
      } else {
        alert(data.message || 'Checkout failed');
        checkoutBtn.disabled = false;
        checkoutBtn.classList.remove('is-loading');
      }
    } catch (err) {
      alert(t('generic_error', '發生錯誤'));
      checkoutBtn.disabled = false;
      checkoutBtn.classList.remove('is-loading');
    }
  });

  function renderDetail(item) {
    const specs = item.specs || {};
    const b = item.breakdown || {};
    const rows = [
      ['table_purity', '成色', specs.gold],
      ['table_color', '顏色', specs.color || '—'],
      ['table_carat', '克拉', specs.carat],
      ['table_diamond_color', '鑽石顏色', specs.diamond_color],
      ['table_size', '戒圍', specs.ring_size ?? '—'],
      ['step_chain_length', '鍊長', specs.length_cm ? specs.length_cm + ' cm' : '—'],
      ['table_engraving_band', '戒圈刻字', specs.engraving_band || '—'],
      ['table_engraving_girdle', '腰圍刻字', specs.engraving_girdle || '—'],
    ];

    let grid = rows.map(([key, fb, val]) =>
      '<div class="order-detail-item">' +
        '<span class="order-detail-label">' + escapeHtml(t(key, fb)) + '</span>' +
        '<span class="order-detail-value">' + escapeHtml(String(val ?? '—')) + '</span>' +
      '</div>'
    ).join('');

    let pricing = '';
    if (b.manual_override) {
      pricing = '<p class="cart-detail-total">' + escapeHtml(formatPrice(b.total)) + '</p>';
    } else if (b.total != null) {
      pricing =
        '<div class="cart-detail-pricing">' +
          (b.diamond_price != null ? '<div class="cart-detail-price-row"><span>' + escapeHtml(t('price_diamond', '鑽石')) + '</span><span>' + escapeHtml(formatPrice(b.diamond_price)) + '</span></div>' : '') +
          (b.taijin_price != null ? '<div class="cart-detail-price-row"><span>' + escapeHtml(t('price_taijin', '台金')) + '</span><span>' + escapeHtml(formatPrice(b.taijin_price)) + '</span></div>' : '') +
          (b.labor_price != null ? '<div class="cart-detail-price-row"><span>' + escapeHtml(t('price_labor', '工費')) + '</span><span>' + escapeHtml(formatPrice(b.labor_price)) + '</span></div>' : '') +
          (b.chain_price != null ? '<div class="cart-detail-price-row"><span>' + escapeHtml(t('price_chain', '配鍊')) + '</span><span>' + escapeHtml(formatPrice(b.chain_price)) + '</span></div>' : '') +
          '<div class="cart-detail-price-row cart-detail-price-row--total"><span>' + escapeHtml(t('table_price', '總價')) + '</span><strong>' + escapeHtml(formatPrice(b.total)) + '</strong></div>' +
        '</div>';
    }

    const img = item.image_url
      ? '<img class="cart-detail-image" src="' + escapeHtml(item.image_url) + '" alt="">'
      : '<div class="cart-detail-image cart-detail-image--empty">💎</div>';

    detailBody.innerHTML =
      '<div class="cart-detail-layout">' +
        '<div class="cart-detail-media">' + img + '</div>' +
        '<div class="cart-detail-specs">' +
          '<p class="cart-detail-summary">' + escapeHtml(item.summary || '') + '</p>' +
          '<div class="order-detail-grid">' + grid + '</div>' +
          pricing +
        '</div>' +
      '</div>';
  }

  async function openDetailModal(id) {
    if (!detailDialog || !detailBody) return;
    detailBody.innerHTML = '<p class="cart-detail-loading">' + escapeHtml(t('notifications_loading', '載入中…')) + '</p>';
    detailDialog.showModal();
    try {
      const res = await fetch('/api/cart/' + id, {
        headers: { 'X-CSRFToken': csrf || '' },
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      if (data.success && data.item) renderDetail(data.item);
      else detailBody.innerHTML = '<p class="cart-detail-loading">' + escapeHtml(data.message || t('generic_error', '發生錯誤')) + '</p>';
    } catch (err) {
      detailBody.innerHTML = '<p class="cart-detail-loading">' + escapeHtml(t('generic_error', '發生錯誤')) + '</p>';
    }
  }

  detailClose?.addEventListener('click', () => detailDialog?.close());
  detailDialog?.addEventListener('click', (e) => {
    if (e.target === detailDialog) detailDialog.close();
  });

  document.addEventListener('langchange', updateSelectionUI);

  updateSelectionUI();

  const params = new URLSearchParams(window.location.search);
  const detailId = params.get('detail');
  if (detailId) openDetailModal(detailId);
})();
