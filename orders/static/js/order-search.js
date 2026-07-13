/**
 * Instant client-side order filter + empty-state handling (history + admin).
 * Submitting the search form reloads with ?q= for server-side paginated search.
 */
(function () {
  const input = document.getElementById('order-search-input');
  const form = document.querySelector('.order-search-bar');
  if (!input) return;

  const sections = (window.orderSearchConfig && window.orderSearchConfig.sections) || [];

  function normalize(value) {
    return (value || '').toLowerCase().trim();
  }

  function detailRowFor(mainRow) {
    const targetId = mainRow.querySelector('.order-detail-btn')?.dataset.target;
    return targetId ? document.getElementById(targetId) : null;
  }

  function updateCounts() {
    const q = normalize(input.value);

    sections.forEach(section => {
      const tbody = document.getElementById(section.tbodyId);
      if (!tbody) return;

      const allRows = [...tbody.querySelectorAll('tr.order-row-main')];
      /* Use the search-match flag (not `hidden`) so an extra layer like
         pagination can hide rows without corrupting these counts. */
      const visibleRows = allRows.filter(r => r.dataset.searchMatch !== '0');

      const countEl = section.countId ? document.getElementById(section.countId) : null;
      const emptyRow = section.emptyId ? document.getElementById(section.emptyId) : null;
      const searchEmpty = section.searchEmptyId ? document.getElementById(section.searchEmptyId) : null;

      if (countEl) countEl.textContent = q ? visibleRows.length : allRows.length;
      if (emptyRow) emptyRow.hidden = allRows.length > 0;
      if (searchEmpty) searchEmpty.hidden = !(allRows.length > 0 && visibleRows.length === 0 && q);
    });

    if (typeof window.orderSearchConfig?.onFilterChange === 'function') {
      window.orderSearchConfig.onFilterChange();
    }
  }

  function applyFilter() {
    const q = normalize(input.value);

    document.querySelectorAll('tr.order-row-main[data-search]').forEach(row => {
      const blob = row.dataset.search || '';
      const match = !q || blob.includes(q);
      row.dataset.searchMatch = match ? '1' : '0';
      row.hidden = !match;

      const detailRow = detailRowFor(row);
      if (detailRow && !match) {
        detailRow.hidden = true;
        const btn = row.querySelector('.order-detail-btn');
        if (btn) {
          btn.setAttribute('aria-expanded', 'false');
          row.classList.remove('is-detail-open');
        }
      }
    });

    updateCounts();
  }

  input.addEventListener('input', applyFilter);

  form?.addEventListener('submit', e => {
    e.preventDefault();
    const url = new URL(form.action || window.location.href, window.location.origin);
    const params = new URLSearchParams(new FormData(form));
    params.set('page', '1');
    if (!params.get('q')) params.delete('q');
    window.location.href = `${url.pathname}?${params.toString()}`;
  });

  applyFilter();
})();
