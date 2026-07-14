(function () {
  const opts = window.AP_OPTIONS || { golds: [], carats: [], chainCarats: [], goldLabels: {}, editMode: false };
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  // ── Category tabs ─────────────────────────────────────────────────────────
  const tabBtns = document.querySelectorAll('.ap-category-tabs .admin-tab-btn');
  const panels = document.querySelectorAll('.ap-tab-panel');
  const newBtn = document.getElementById('ap-new-btn');
  const newBtnBase = newBtn?.getAttribute('href') || '/admin/products/new';

  function categoryFromTab(tabKey) {
    return tabKey?.startsWith('cat-') ? tabKey.slice(4) : '';
  }

  function setActiveCategoryTab(tabKey) {
    tabBtns.forEach(btn => {
      const active = btn.dataset.tab === tabKey;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    panels.forEach(p => { p.hidden = p.dataset.tabPanel !== tabKey; });
    const cat = categoryFromTab(tabKey);
    if (newBtn && cat) {
      newBtn.href = `${newBtnBase}?category=${encodeURIComponent(cat)}`;
    }
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => setActiveCategoryTab(btn.dataset.tab));
  });

  const initialTab = opts.defaultCategory
    ? `cat-${opts.defaultCategory}`
    : tabBtns[0]?.dataset.tab;
  if (initialTab) setActiveCategoryTab(initialTab);

  // ── Product drag ordering ───────────────────────────────────────────────
  let draggedRow = null;
  document.querySelectorAll('.ap-table tbody').forEach(tbody => {
    tbody.querySelectorAll('tr[data-id]').forEach(row => {
      row.addEventListener('dragstart', () => {
        draggedRow = row;
        row.classList.add('is-dragging');
      });
      row.addEventListener('dragend', async () => {
        row.classList.remove('is-dragging');
        draggedRow = null;
        const rows = [...tbody.querySelectorAll('tr[data-id]')];
        if (!rows.length) return;
        try {
          const res = await fetch('/admin/products/reorder', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrf(),
            },
            body: JSON.stringify({
              category: rows[0].dataset.category,
              ids: rows.map(item => Number(item.dataset.id)),
            }),
          });
          const data = await res.json();
          if (!res.ok || !data.success) throw new Error(data.message || '排序失敗');
        } catch (error) {
          alert(error.message || '排序失敗，請重新整理後再試。');
          window.location.reload();
        }
      });
      row.addEventListener('dragover', event => {
        event.preventDefault();
        if (!draggedRow || draggedRow === row) return;
        const box = row.getBoundingClientRect();
        tbody.insertBefore(draggedRow, event.clientY < box.top + box.height / 2 ? row : row.nextSibling);
      });
    });
  });

  // ── Publish / unpublish toggle ──────────────────────────────────────────
  document.querySelectorAll('.ap-toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const action = btn.dataset.action; // 'publish' | 'unpublish'
      try {
        const res = await fetch(`/admin/products/${id}/${action}`, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf() },
        });
        if (res.status === 401) { window.location.href = '/login'; return; }
        const data = await res.json();
        if (data.success) {
          window.location.reload();
        } else {
          alert(data.message || '操作失敗');
        }
      } catch (err) {
        console.error(err);
        alert('發生錯誤，請稍後再試。');
      }
    });
  });

  // ── Delete dialog ────────────────────────────────────────────────────────
  const deleteDialog = document.getElementById('ap-delete-dialog');
  const deleteForm = document.getElementById('ap-delete-form');
  const deleteTarget = document.getElementById('ap-delete-target');
  const deleteCancel = document.getElementById('ap-delete-cancel');
  let deleteId = null;

  document.querySelectorAll('.ap-delete-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      deleteId = btn.dataset.id;
      deleteTarget.textContent = `即將刪除：${btn.dataset.name || ('#' + deleteId)}`;
      deleteDialog?.showModal();
    });
  });
  deleteCancel?.addEventListener('click', () => deleteDialog.close());
  deleteForm?.addEventListener('submit', async e => {
    e.preventDefault();
    if (!deleteId) return;
    try {
      const res = await fetch(`/admin/products/${deleteId}/delete`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf() },
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      if (data.success) {
        deleteDialog.close();
        if (data.message) alert(data.message);
        window.location.reload();
      } else {
        alert(data.message || '刪除失敗');
      }
    } catch (err) {
      console.error(err);
      alert('發生錯誤，請稍後再試。');
    }
  });

  // ── Create/edit form: close button ──────────────────────────────────────
  document.getElementById('ap-form-close-btn')?.addEventListener('click', () => {
    window.location.href = '/admin/products';
  });

  // ── Variant rows: add / remove, and carat options follow category ──────
  const grid = document.getElementById('ap-variant-grid');
  const categorySelect = document.getElementById('ap-category-select');

  function caratOptionsFor(category) {
    return category === 'chain' ? opts.chainCarats : opts.carats;
  }

  function buildVariantRow(category) {
    const row = document.createElement('div');
    row.className = 'ap-variant-row';

    const goldSelect = document.createElement('select');
    goldSelect.name = 'variant_gold';
    goldSelect.setAttribute('aria-label', '金屬成色');
    opts.golds.forEach(g => {
      const o = document.createElement('option');
      o.value = g;
      o.textContent = opts.goldLabels[g] || g;
      goldSelect.appendChild(o);
    });

    const caratSelect = document.createElement('select');
    caratSelect.name = 'variant_carat';
    caratSelect.className = 'ap-carat-select';
    caratSelect.setAttribute('aria-label', '克拉／分');
    caratOptionsFor(category).forEach(c => {
      const o = document.createElement('option');
      o.value = c;
      o.textContent = c;
      caratSelect.appendChild(o);
    });

    const weightInput = document.createElement('input');
    weightInput.type = 'number';
    weightInput.name = 'variant_weight';
    weightInput.step = '0.0001';
    weightInput.min = '0.0001';
    weightInput.placeholder = '例如 0.85';
    weightInput.setAttribute('aria-label', '金重（錢）');

    const priceInput = document.createElement('input');
    priceInput.type = 'number';
    priceInput.name = 'variant_price';
    priceInput.step = '1';
    priceInput.min = '0';
    priceInput.placeholder = '自動試算';
    priceInput.setAttribute('aria-label', '手動定價');

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'ap-remove-row-btn';
    removeBtn.title = '移除';
    removeBtn.setAttribute('aria-label', '移除此款式');
    removeBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/></svg>';
    removeBtn.addEventListener('click', () => row.remove());

    row.append(goldSelect, caratSelect, weightInput, priceInput, removeBtn);
    return row;
  }

  document.getElementById('ap-add-variant-btn')?.addEventListener('click', () => {
    grid.appendChild(buildVariantRow(categorySelect.value));
  });

  grid?.querySelectorAll('.ap-remove-row-btn').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.ap-variant-row')?.remove());
  });

  // When category changes, refresh every row's carat <select> options
  // (carrying over the previous value where it's still valid for the new set).
  categorySelect?.addEventListener('change', () => {
    const newOptions = caratOptionsFor(categorySelect.value);
    grid.querySelectorAll('select[name="variant_carat"]').forEach(sel => {
      const prevValue = sel.value;
      sel.innerHTML = '';
      newOptions.forEach(c => {
        const o = document.createElement('option');
        o.value = c;
        o.textContent = c;
        sel.appendChild(o);
      });
      if (newOptions.includes(prevValue)) sel.value = prevValue;
    });
  });

  // ── Image dropzones: multi-image preview + per-image remove ─────────────
  document.querySelectorAll('.ap-image-dropzone').forEach(zone => {
    const input = zone.querySelector('.ap-image-input');
    const gallery = zone.querySelector('.ap-image-gallery');
    const pending = zone.querySelector('.ap-image-pending');
    const empty = zone.querySelector('.ap-image-empty');

    function syncEmptyState() {
      if (!empty) return;
      const hasExisting = gallery.querySelectorAll('.ap-image-existing:not(.is-marked-remove)').length > 0;
      const hasPending = pending?.children.length > 0;
      empty.style.display = (hasExisting || hasPending) ? 'none' : '';
    }

    zone.querySelectorAll('.ap-remove-image-checkbox').forEach(cb => {
      cb.addEventListener('change', () => {
        const card = cb.closest('.ap-image-existing');
        card?.classList.toggle('is-marked-remove', cb.checked);
        const img = card?.querySelector('.ap-image-preview');
        if (img) img.style.opacity = cb.checked ? '0.35' : '';
        syncEmptyState();
      });
    });

    zone.querySelectorAll('.ap-image-order-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const item = btn.closest('.ap-image-existing');
        if (!item) return;
        const direction = Number(btn.dataset.direction);
        const siblings = [...gallery.querySelectorAll('.ap-image-existing')];
        const index = siblings.indexOf(item);
        const target = siblings[index + direction];
        if (!target) return;
        if (direction < 0) gallery.insertBefore(item, target);
        else gallery.insertBefore(target, item);
      });
    });

    input?.addEventListener('change', () => {
      if (!pending) return;
      pending.innerHTML = '';
      Array.from(input.files || []).forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'ap-image-pending-item';
        const wrap = document.createElement('div');
        wrap.className = 'ap-image-preview-wrap ap-image-preview-wrap--thumb';
        const img = document.createElement('img');
        img.className = 'ap-image-preview';
        img.src = URL.createObjectURL(file);
        img.alt = '';
        wrap.appendChild(img);
        const label = document.createElement('span');
        label.className = 'ap-image-pending-label';
        label.textContent = `待上傳 #${index + 1}`;
        item.append(wrap, label);
        pending.appendChild(item);
      });
      syncEmptyState();
    });

    syncEmptyState();
  });

  // Open the form section automatically in create/edit mode (server also
  // adds the is-open class). Skip auto-scroll on phones — it leaves odd gaps.
  if (opts.editMode && window.innerWidth > 900) {
    document.getElementById('ap-form-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Pre-select category when arriving from a tab-specific "新增商品" link.
  const urlCategory = new URLSearchParams(window.location.search).get('category');
  if (urlCategory && categorySelect) {
    categorySelect.value = urlCategory;
    categorySelect.dispatchEvent(new Event('change'));
  }

  if (grid && !grid.querySelector('.ap-variant-row:not(.ap-variant-row--head)')) {
    grid.appendChild(buildVariantRow(categorySelect?.value || opts.defaultCategory));
  }

  // ── AJAX form submit: preserve all entered values on validation error ──
  const form = document.getElementById('ap-form');
  const formErrors = document.getElementById('ap-form-errors');
  const submitBtn = document.getElementById('ap-submit-btn');
  const draftToggle = document.getElementById('ap-draft-toggle');
  const publishedField = document.getElementById('ap-is-published');
  const publishHelp = document.getElementById('ap-publish-help');
  const submitNote = document.querySelector('#ap-submit-note span');
  const editorStatus = document.getElementById('ap-editor-status');
  const editorStatusText = document.getElementById('ap-editor-status-text');

  function willPublish() {
    return !draftToggle?.checked;
  }

  function syncPublishedField() {
    if (publishedField) {
      publishedField.value = willPublish() ? '1' : '0';
    }
  }

  function updatePublishAction() {
    if (!submitBtn) return;

    syncPublishedField();
    const publish = willPublish();
    const isCreate = submitBtn.dataset.mode === 'create';
    const wasPublished = submitBtn.dataset.initialPublished === 'true';
    let buttonText;
    let helpText;
    let noteText;
    let statusText;

    if (isCreate) {
      buttonText = publish ? '建立並上架' : '儲存草稿';
      helpText = publish
        ? '關閉時提交後會直接上架。'
        : '開啟時只儲存草稿，不會顯示於訂製頁面。';
      noteText = publish
        ? '提交後會直接上架並顯示於訂製頁面。'
        : '商品將儲存為草稿，不會立即上架。';
      statusText = publish ? '將上架' : '草稿';
    } else if (publish) {
      buttonText = wasPublished ? '儲存變更' : '儲存並上架';
      helpText = '關閉時提交後會直接上架。';
      noteText = wasPublished
        ? '儲存後變更會套用至已上架商品。'
        : '儲存後商品將立即上架。';
      statusText = wasPublished ? '已上架' : '將上架';
    } else {
      buttonText = wasPublished ? '儲存並下架' : '儲存草稿';
      helpText = '開啟時只儲存草稿，不會顯示於訂製頁面。';
      noteText = wasPublished
        ? '儲存後商品將從訂製頁面下架。'
        : '商品將保持草稿狀態。';
      statusText = wasPublished ? '將下架' : '草稿';
    }

    submitBtn.textContent = buttonText;
    if (publishHelp) publishHelp.textContent = helpText;
    if (submitNote) submitNote.textContent = noteText;
    if (editorStatus && editorStatusText) {
      editorStatus.classList.toggle('ap-editor-status--live', publish);
      editorStatus.classList.toggle('ap-editor-status--draft', !publish);
      editorStatus.classList.remove('ap-editor-status--new');
      editorStatusText.textContent = statusText;
    }
  }

  draftToggle?.addEventListener('change', updatePublishAction);
  updatePublishAction();

  function clearFormErrors() {
    document.querySelectorAll('.ap-field-error').forEach(el => { el.textContent = ''; });
    if (formErrors) {
      formErrors.hidden = true;
      formErrors.textContent = '';
    }
  }

  function showFormErrors(errors, message) {
    clearFormErrors();
    Object.entries(errors || {}).forEach(([field, messages]) => {
      const target = document.querySelector(`[data-error-for="${field}"]`);
      if (target) target.textContent = (messages || []).join(' ');
    });
    const general = errors?.form || [];
    if (formErrors && (message || general.length)) {
      formErrors.textContent = [message, ...general].filter(Boolean).join(' ');
      formErrors.hidden = false;
    }
    document.querySelector('.ap-field-error:not(:empty), #ap-form-errors:not([hidden])')
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  form?.addEventListener('submit', async event => {
    event.preventDefault();
    clearFormErrors();
    syncPublishedField();
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.classList.add('is-loading');
    }
    try {
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf() },
        body: new FormData(form),
      });
      const data = await res.json();
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      if (res.ok && data.success) {
        window.location.href = data.redirect || '/admin/products';
        return;
      }
      showFormErrors(data.errors, data.message || '儲存失敗');
    } catch (error) {
      console.error(error);
      showFormErrors({}, '發生錯誤，請稍後再試。');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.classList.remove('is-loading');
      }
    }
  });
})();
