// Mobile nav + dropdown menus (authenticated app shell).
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('nav-toggle');
  const backdrop = document.getElementById('nav-backdrop');
  const navbar = document.querySelector('.premium-navbar');
  if (!navbar) return;

  const MOBILE_BREAKPOINT = 900;
  const dropdowns = navbar.querySelectorAll('[data-nav-dropdown]');

  function isMobile() {
    return window.innerWidth <= MOBILE_BREAKPOINT;
  }

  function syncBodyMenuState(isOpen) {
    document.body.classList.toggle('nav-menu-open', isOpen && isMobile());
    if (backdrop) {
      backdrop.hidden = !(isOpen && isMobile());
      backdrop.setAttribute('aria-hidden', isOpen && isMobile() ? 'false' : 'true');
    }
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

  function bindCloseOnActivate(el, handler) {
    if (!el) return;
    let lastTouch = 0;
    el.addEventListener('touchend', (e) => {
      e.preventDefault();
      lastTouch = Date.now();
      handler(e);
    }, { passive: false });
    el.addEventListener('click', (e) => {
      if (Date.now() - lastTouch < 500) return;
      handler(e);
    });
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
      e.preventDefault();
      e.stopPropagation();
      setDropdownOpen(dropdown, !dropdown.classList.contains('is-open'));
    });
  });

  bindCloseOnActivate(toggle, (e) => {
    e.stopPropagation();
    toggleMenu();
  });

  bindCloseOnActivate(backdrop, (e) => {
    e.stopPropagation();
    closeMenu();
    toggle?.focus({ preventScroll: true });
  });

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
