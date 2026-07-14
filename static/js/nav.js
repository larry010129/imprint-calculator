// Mobile nav + dropdown menus (authenticated app shell).
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('nav-toggle');
  const navbar = document.querySelector('.premium-navbar');
  if (!navbar) return;

  const MOBILE_BREAKPOINT = 900;
  const dropdowns = navbar.querySelectorAll('[data-nav-dropdown]');

  function isMobile() {
    return window.innerWidth <= MOBILE_BREAKPOINT;
  }

  function syncBodyMenuState(isOpen) {
    document.body.classList.toggle('nav-menu-open', isOpen && isMobile());
  }

  function setMenuOpen(open) {
    navbar.classList.toggle('nav-open', open);
    syncBodyMenuState(open);
    if (toggle) {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? '關閉選單' : '開啟選單');
    }
    if (!open) closeAllDropdowns();
  }

  function closeMenu() {
    setMenuOpen(false);
  }

  function toggleMenu() {
    setMenuOpen(!navbar.classList.contains('nav-open'));
  }

  function dropdownTrigger(dropdown) {
    // Account: whole row toggles on mobile (avatar/name + chevron), not just the tiny button.
    if (dropdown.classList.contains('nav-user-dropdown')) {
      return dropdown.querySelector('.nav-user-trigger')
        || dropdown.querySelector('.nav-user-menu-btn');
    }
    return dropdown.querySelector('.nav-dropdown-trigger');
  }

  function setTriggerExpanded(dropdown, expanded) {
    const trigger = dropdownTrigger(dropdown);
    if (trigger) trigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    const menuBtn = dropdown.querySelector('.nav-user-menu-btn');
    if (menuBtn) menuBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  }

  function closeAllDropdowns(except) {
    dropdowns.forEach((dropdown) => {
      if (dropdown === except) return;
      dropdown.classList.remove('is-open');
      setTriggerExpanded(dropdown, false);
    });
  }

  function setDropdownOpen(dropdown, open) {
    closeAllDropdowns(open ? dropdown : null);
    dropdown.classList.toggle('is-open', open);
    setTriggerExpanded(dropdown, open);
  }

  dropdowns.forEach((dropdown) => {
    const trigger = dropdownTrigger(dropdown);
    if (!trigger) return;

    trigger.addEventListener('mousedown', (e) => {
      if (!isMobile()) e.preventDefault();
    });

    dropdown.addEventListener('mouseenter', () => {
      if (isMobile()) return;
      closeAllDropdowns();
      dropdowns.forEach((other) => {
        if (other === dropdown) return;
        const otherTrigger = dropdownTrigger(other);
        if (otherTrigger && document.activeElement === otherTrigger) {
          otherTrigger.blur();
        }
      });
    });

    trigger.addEventListener('click', (e) => {
      if (!isMobile()) return;
      // Re-pressing the same account/shop/admin tab retracts its list.
      e.preventDefault();
      e.stopPropagation();
      setDropdownOpen(dropdown, !dropdown.classList.contains('is-open'));
    });
  });

  if (toggle) {
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleMenu();
    });
  }

  navbar.querySelectorAll('.nav-links > a, .nav-dropdown-item[href], .nav-user a.nav-cart-link').forEach((el) => {
    el.addEventListener('click', () => {
      if (isMobile()) closeMenu();
    });
  });

  document.addEventListener('click', (e) => {
    if (!isMobile()) {
      if (!e.target.closest('[data-nav-dropdown]')) {
        closeAllDropdowns();
      }
      return;
    }
    // Phone: tap outside the open panel closes hamburger + any accordion lists.
    if (navbar.classList.contains('nav-open') && !navbar.contains(e.target)) {
      closeMenu();
      return;
    }
    if (!e.target.closest('[data-nav-dropdown]')) {
      closeAllDropdowns();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllDropdowns();
      if (isMobile()) closeMenu();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > MOBILE_BREAKPOINT) {
      closeMenu();
      closeAllDropdowns();
    }
  });
});
