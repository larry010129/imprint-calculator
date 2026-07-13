/**
 * Toggle expandable order detail rows (history + admin tables).
 */
(function () {
  function labelFor(expanded) {
    if (typeof window.t === 'function') {
      return window.t(expanded ? 'btn_hide_detail' : 'btn_see_detail');
    }
    return expanded ? '收起' : '查看詳情';
  }

  function setButtonState(btn, expanded) {
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    const span = btn.querySelector('[data-i18n]');
    if (span) {
      span.setAttribute('data-i18n', expanded ? 'btn_hide_detail' : 'btn_see_detail');
      span.textContent = labelFor(expanded);
    } else {
      btn.textContent = labelFor(expanded);
    }
  }

  function toggleDetail(btn) {
    const targetId = btn.dataset.target;
    if (!targetId) return;
    const detailRow = document.getElementById(targetId);
    if (!detailRow) return;

    const willExpand = detailRow.hidden;
    detailRow.hidden = !willExpand;
    setButtonState(btn, willExpand);

    const mainRow = btn.closest('tr.order-row-main');
    if (mainRow) {
      mainRow.classList.toggle('is-detail-open', willExpand);
    }

    if (willExpand) {
      detailRow.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function initDetailGalleries() {
    document.querySelectorAll('.order-detail-gallery').forEach(gallery => {
      const mainImg = gallery.querySelector('.order-detail-main-img');
      const thumbBtns = [...gallery.querySelectorAll('.order-detail-thumb-btn')];

      thumbBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          thumbBtns.forEach(b => b.classList.remove('is-active'));
          btn.classList.add('is-active');
          if (mainImg && btn.dataset.image) mainImg.src = btn.dataset.image;
        });
      });
    });
  }

  const ROW_CLICK_IGNORE = 'button, a, input, select, textarea, label';

  document.addEventListener('click', e => {
    const btn = e.target.closest('.order-detail-btn');
    if (btn) {
      e.preventDefault();
      toggleDetail(btn);
      return;
    }

    const row = e.target.closest('tr.order-row-main');
    if (!row || e.target.closest(ROW_CLICK_IGNORE)) return;

    const detailBtn = row.querySelector('.order-detail-btn');
    if (detailBtn) toggleDetail(detailBtn);
  });

  document.addEventListener('langchange', () => {
    document.querySelectorAll('.order-detail-btn').forEach(btn => {
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      setButtonState(btn, expanded);
    });
  });

  // Image fallback for order thumbnails/previews (replaces inline onerror
  // attributes, which a nonce-based CSP blocks). Error events don't bubble,
  // so listen in the capture phase.
  document.addEventListener('error', e => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    const fallback = img.dataset.fallback;
    if (fallback && img.src !== new URL(fallback, location.href).href) {
      img.src = fallback;
    }
  }, true);

  initDetailGalleries();
})();
