// Smooth cross-page transitions for same-origin navigation (MPA).
// Chrome uses <meta name="view-transition" content="same-origin"> + CSS.
// Other browsers get a short fade-out before navigating.
(function () {
  'use strict';

  var EXIT_MS = 220;
  var LEAVE_CLASS = 'page-leaving';
  var READY_CLASS = 'page-ready';

  function reducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function viewTransitionsSupported() {
    return CSS.supports && (
      CSS.supports('view-transition-name', 'root') ||
      CSS.supports('view-transition-name', 'none')
    ) && document.querySelector('meta[name="view-transition"][content*="same-origin"]');
  }

  function isInternalNavLink(anchor) {
    if (!anchor || anchor.tagName !== 'A') return false;
    if (anchor.target === '_blank' || anchor.hasAttribute('download')) return false;
    if (anchor.hasAttribute('data-no-transition')) return false;
    var href = anchor.getAttribute('href');
    if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return false;
    if (href.indexOf('mailto:') === 0 || href.indexOf('tel:') === 0) return false;
    try {
      var url = new URL(href, window.location.href);
      return url.origin === window.location.origin;
    } catch (err) {
      return false;
    }
  }

  function markReady() {
    document.documentElement.classList.add(READY_CLASS);
    document.documentElement.classList.remove(LEAVE_CLASS);
  }

  function onLinkClick(event) {
    if (reducedMotion() || viewTransitionsSupported()) return;
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    var anchor = event.target.closest('a');
    if (!isInternalNavLink(anchor)) return;

    var next = new URL(anchor.href, window.location.href);
    if (next.pathname === window.location.pathname && next.search === window.location.search) return;

    event.preventDefault();
    document.documentElement.classList.add(LEAVE_CLASS);
    window.setTimeout(function () {
      window.location.href = anchor.href;
    }, EXIT_MS);
  }

  document.addEventListener('click', onLinkClick, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markReady);
  } else {
    markReady();
  }

  window.addEventListener('pageshow', function () {
    markReady();
  });
})();
