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

  function closeMenu() {
    navbar.classList.remove('nav-open');
    syncBodyMenuState(false);
    if (toggle) {
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', '開啟選單');
    }
    closeAllDropdowns();
  }

  function toggleMenu() {
    const isOpen = navbar.classList.toggle('nav-open');
    syncBodyMenuState(isOpen);
    if (toggle) {
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      toggle.setAttribute('aria-label', isOpen ? '關閉選單' : '開啟選單');
    }
    if (!isOpen) closeAllDropdowns();
  }

  function dropdownTrigger(dropdown) {
    if (dropdown.classList.contains('nav-user-dropdown')) {
      return dropdown.querySelector('.nav-user-menu-btn');
    }
    return dropdown.querySelector('.nav-dropdown-trigger');
  }

  function closeAllDropdowns(except) {
    dropdowns.forEach((dropdown) => {
      if (dropdown === except) return;
      dropdown.classList.remove('is-open');
      const trigger = dropdownTrigger(dropdown);
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
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
      const willOpen = !dropdown.classList.contains('is-open');
      closeAllDropdowns(willOpen ? dropdown : null);
      dropdown.classList.toggle('is-open', willOpen);
      trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
  });

  if (toggle) {
    toggle.addEventListener('click', toggleMenu);
  }

  navbar.querySelectorAll('.nav-links > a, .nav-dropdown-item[href], .nav-user a.nav-cart-link').forEach((el) => {
    el.addEventListener('click', () => {
      if (isMobile()) closeMenu();
    });
  });

  document.addEventListener('click', (e) => {
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
