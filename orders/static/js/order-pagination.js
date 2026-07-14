/**
 * Client-side pagination for admin order tables (per tab/status section).
 * Works together with order-search.js: rows carry `data-search-match` set by
 * the search filter, and this module layers a page window on top of that so
 * the two concerns never fight over the shared `hidden` attribute.
 */
(function () {
  const sections = (window.orderSearchConfig && window.orderSearchConfig.sections) || [];
  const controlsList = [...document.querySelectorAll('[data-pagination-for]')];
  if (!sections.length || !controlsList.length) return;

  const STORAGE_KEY = 'adminOrdersPageSize';
  const DEFAULT_PAGE_SIZE = 20;

  function loadStoredPageSize() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'all') return 'all';
    const n = parseInt(stored, 10);
    return Number.isFinite(n) && n > 0 ? n : DEFAULT_PAGE_SIZE;
  }

  const state = {};
  sections.forEach((section) => {
    state[section.key] = { page: 1, pageSize: loadStoredPageSize() };
  });

  function detailRowFor(row) {
    const targetId = row.querySelector('.order-detail-btn')?.dataset.target;
    return targetId ? document.getElementById(targetId) : null;
  }

  function matchingRows(section) {
    const tbody = document.getElementById(section.tbodyId);
    if (!tbody) return [];
    return [...tbody.querySelectorAll('tr.order-row-main[data-search]')]
      .filter((row) => row.dataset.searchMatch !== '0');
  }

  function pageNumbers(current, total) {
    const pages = new Set([1, total, current - 1, current, current + 1]);
    return [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  }

  function pageLink(label, { page, action, current, disabled } = {}) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'admin-page-link' + (current ? ' is-current' : '');
    btn.textContent = label;
    if (disabled) btn.disabled = true;
    if (page !== undefined) btn.dataset.page = String(page);
    if (action) btn.dataset.pageAction = action;
    return btn;
  }

  function renderLinks(container, page, totalPages) {
    container.innerHTML = '';
    container.appendChild(pageLink('‹', { action: 'prev', disabled: page <= 1 }));
    let prev = 0;
    pageNumbers(page, totalPages).forEach((n) => {
      if (n - prev > 1) {
        const ell = document.createElement('span');
        ell.className = 'admin-page-ellipsis';
        ell.textContent = '…';
        container.appendChild(ell);
      }
      container.appendChild(pageLink(String(n), { page: n, current: n === page }));
      prev = n;
    });
    container.appendChild(pageLink('›', { action: 'next', disabled: page >= totalPages }));
  }

  function render(key) {
    const section = sections.find((s) => s.key === key);
    const controls = controlsList.find((el) => el.dataset.paginationFor === key);
    if (!section) return;
    const tbody = document.getElementById(section.tbodyId);
    if (!tbody) return;
    const st = state[key];

    const matches = matchingRows(section);
    const total = matches.length;
    const pageSize = st.pageSize === 'all' ? Math.max(total, 1) : st.pageSize;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (st.page > totalPages) st.page = totalPages;
    if (st.page < 1) st.page = 1;
    const start = (st.page - 1) * pageSize;
    const visibleSet = new Set(matches.slice(start, start + pageSize));

    tbody.querySelectorAll('tr.order-row-main').forEach((row) => {
      const show = visibleSet.has(row);
      row.hidden = !show;
      if (!show) {
        const detail = detailRowFor(row);
        if (detail) {
          detail.hidden = true;
          const btn = row.querySelector('.order-detail-btn');
          if (btn) btn.setAttribute('aria-expanded', 'false');
          row.classList.remove('is-detail-open');
        }
      }
    });

    if (!controls) return;
    controls.hidden = total === 0;
    const linksEl = controls.querySelector('[data-page-links-for]');
    if (linksEl) renderLinks(linksEl, st.page, totalPages);
    const sizeSelect = controls.querySelector('[data-page-size-for]');
    if (sizeSelect && sizeSelect.value !== String(st.pageSize)) sizeSelect.value = String(st.pageSize);
  }

  function refreshAll() {
    sections.forEach((section) => render(section.key));
  }

  function setPageSizeEverywhere(value) {
    const parsed = value === 'all' ? 'all' : parseInt(value, 10);
    sections.forEach((section) => {
      state[section.key].pageSize = parsed;
      state[section.key].page = 1;
    });
    localStorage.setItem(STORAGE_KEY, value);
    controlsList.forEach((controls) => {
      const sel = controls.querySelector('[data-page-size-for]');
      if (sel) sel.value = value;
    });
    refreshAll();
  }

  controlsList.forEach((controls) => {
    const key = controls.dataset.paginationFor;

    const linksEl = controls.querySelector('[data-page-links-for]');
    linksEl?.addEventListener('click', (e) => {
      const btn = e.target.closest('.admin-page-link');
      if (!btn || btn.disabled) return;
      const st = state[key];
      if (btn.dataset.pageAction === 'prev') st.page = Math.max(1, st.page - 1);
      else if (btn.dataset.pageAction === 'next') st.page += 1;
      else if (btn.dataset.page) st.page = parseInt(btn.dataset.page, 10);
      render(key);
    });

    const sizeSelect = controls.querySelector('[data-page-size-for]');
    if (sizeSelect) {
      sizeSelect.value = String(state[key].pageSize);
      sizeSelect.addEventListener('change', () => setPageSizeEverywhere(sizeSelect.value));
    }
  });

  window.AdminOrderPagination = { refresh: render, refreshAll };

  refreshAll();
  document.addEventListener('langchange', refreshAll);
})();
