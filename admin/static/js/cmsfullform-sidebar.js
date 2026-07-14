(function () {
  'use strict';

  const shell = document.getElementById('cms-admin-shell');
  const sidebar = document.getElementById('cms-admin-sidebar');
  const backdrop = document.getElementById('cms-mobile-backdrop');
  const collapseBtn = document.getElementById('cms-sidebar-collapse');
  const desktopToggle = document.getElementById('cms-menu-toggle-desktop');
  const mobileToggle = document.getElementById('cms-menu-toggle-mobile');
  if (!shell || !sidebar) return;

  const storageKey = 'cms-admin-sidebar-state';
  const MOBILE_BP = 1024;

  function isMobile() {
    return window.innerWidth < MOBILE_BP;
  }

  function applyState(state) {
    shell.classList.remove('is-collapsed', 'is-hidden');
    sidebar.classList.remove('is-mobile-open', 'w-[var(--cms-sidebar-collapsed)]', 'w-0', 'border-r-0');
    sidebar.style.width = '';

    if (isMobile()) {
      shell.classList.add('is-hidden');
      if (state === 'mobile-open') {
        sidebar.classList.add('is-mobile-open');
        if (backdrop) backdrop.classList.remove('hidden');
      } else if (backdrop) {
        backdrop.classList.add('hidden');
      }
      return;
    }

    if (backdrop) backdrop.classList.add('hidden');

    if (state === 'collapsed') {
      shell.classList.add('is-collapsed');
      sidebar.style.width = 'var(--cms-sidebar-collapsed)';
    } else if (state === 'hidden') {
      shell.classList.add('is-hidden');
      sidebar.classList.add('w-0', 'border-r-0');
    }

    const collapsed = state === 'collapsed';
    if (collapseBtn) {
      collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      collapseBtn.querySelector('.cms-collapse-icon-open')?.classList.toggle('hidden', collapsed);
      collapseBtn.querySelector('.cms-collapse-icon-closed')?.classList.toggle('hidden', !collapsed);
    }
  }

  function getState() {
    try {
      return localStorage.getItem(storageKey) || 'full';
    } catch (_) {
      return 'full';
    }
  }

  function setState(state) {
    try {
      localStorage.setItem(storageKey, state);
    } catch (_) {
      /* ignore */
    }
    applyState(state);
  }

  function cycleDesktopState() {
    const current = getState();
    if (current === 'full') setState('collapsed');
    else if (current === 'collapsed') setState('hidden');
    else setState('full');
  }

  function toggleMobile() {
    const open = sidebar.classList.contains('is-mobile-open');
    setState(open ? 'full' : 'mobile-open');
  }

  collapseBtn?.addEventListener('click', () => {
    setState(getState() === 'collapsed' ? 'full' : 'collapsed');
  });

  desktopToggle?.addEventListener('click', cycleDesktopState);
  mobileToggle?.addEventListener('click', toggleMobile);
  backdrop?.addEventListener('click', () => setState('full'));

  window.addEventListener('resize', () => applyState(getState()));

  const userDropdown = document.querySelector('.cms-admin-topnav .nav-dropdown');
  const userTrigger = document.getElementById('cms-user-trigger');
  if (userDropdown && userTrigger) {
    userTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = userDropdown.classList.toggle('is-open');
      userTrigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('click', () => {
      userDropdown.classList.remove('is-open');
      userTrigger.setAttribute('aria-expanded', 'false');
    });
  }

  let state = getState();
  if (state === 'mobile-open') state = 'full';
  applyState(state);
})();
