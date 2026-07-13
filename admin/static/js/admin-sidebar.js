(function () {
  const shell = document.getElementById('adx-admin-shell');
  const sidebar = document.getElementById('adx-admin-sidebar');
  const collapseBtn = document.getElementById('adx-sidebar-collapse');
  if (!shell || !sidebar || !collapseBtn) return;

  const storageKey = 'adx-admin-sidebar-collapsed';

  function setCollapsed(collapsed) {
    shell.classList.toggle('is-collapsed', collapsed);
    collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    try {
      localStorage.setItem(storageKey, collapsed ? '1' : '0');
    } catch (_) {
      /* ignore */
    }
  }

  let collapsed = false;
  try {
    collapsed = localStorage.getItem(storageKey) === '1';
  } catch (_) {
    /* ignore */
  }
  setCollapsed(collapsed);

  collapseBtn.addEventListener('click', () => {
    setCollapsed(!shell.classList.contains('is-collapsed'));
  });
})();
