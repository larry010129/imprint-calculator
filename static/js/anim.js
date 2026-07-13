// Animation foundation: page/card reveal staggering + smooth theme-toggle
// crossfade. Respects prefers-reduced-motion via the CSS kill-switch in
// animations.css - this script only ever adds classes/custom properties,
// the actual "do nothing" behavior for reduced motion lives in CSS.
(function () {
  function reducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // Generic count-up used both for elements the server rendered a final
  // number into (data-countup-init, animated 0 -> value once on load) and
  // for values a page updates later, e.g. the calculator total or a
  // refreshed gold quote (call window.animateCountUp(el, newValue) again).
  function animateCountUp(el, targetValue, opts) {
    if (!el || typeof targetValue !== 'number' || isNaN(targetValue)) return;
    opts = opts || {};
    var duration = opts.duration || 450;
    var format = opts.format || function (v) { return Math.round(v).toLocaleString('en-US'); };
    var previous = parseFloat(el.dataset.countupValue);
    var from = isNaN(previous) ? 0 : previous;
    el.dataset.countupValue = String(targetValue);

    if (from === targetValue) {
      el.textContent = format(targetValue);
      return;
    }
    if (reducedMotion()) {
      el.textContent = format(targetValue);
      return;
    }

    if (el._countupRaf) window.cancelAnimationFrame(el._countupRaf);
    var start = null;
    function step(ts) {
      if (start === null) start = ts;
      var progress = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = format(from + (targetValue - from) * eased);
      if (progress < 1) {
        el._countupRaf = window.requestAnimationFrame(step);
      } else {
        el.textContent = format(targetValue);
        el._countupRaf = null;
      }
    }
    el._countupRaf = window.requestAnimationFrame(step);
  }
  window.animateCountUp = animateCountUp;

  function initCountups(root) {
    root.querySelectorAll('[data-countup-init]:not([data-countup-done])').forEach(function (el) {
      var target = parseFloat(el.getAttribute('data-countup-init'));
      if (isNaN(target)) return;
      el.setAttribute('data-countup-done', '1');
      var isCurrency = el.getAttribute('data-countup-format') === 'currency';
      var format = isCurrency
        ? function (v) { return 'NT$ ' + Math.round(v).toLocaleString('en-US'); }
        : undefined;
      el.dataset.countupValue = '0';
      el.textContent = format ? format(0) : '0';
      animateCountUp(el, target, { format: format });
    });
  }

  var STAGGER_SELECTOR =
    '.catalog-tile, .type-card, .records-table-wrap tbody tr, ' +
    '.notifications-feed-item, .notify-panel-item';
  var STAGGER_STEP_MS = 45;
  var STAGGER_MAX_STEPS = 12;

  function applyStagger(root) {
    var items = root.querySelectorAll(STAGGER_SELECTOR);
    for (var i = 0; i < items.length; i++) {
      var el = items[i];
      if (el.style.getPropertyValue('--reveal-delay')) continue;
      var step = Math.min(i, STAGGER_MAX_STEPS);
      el.style.setProperty('--reveal-delay', (step * STAGGER_STEP_MS) + 'ms');
    }
  }

  function init() {
    applyStagger(document);
    initCountups(document);

    // Cards/rows added after load (calculator style cards, notification
    // dropdown list, admin table filters) still get a delay assigned via
    // this observer, batched onto a single animation frame per burst.
    var pending = false;
    var observer = new MutationObserver(function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        applyStagger(document);
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Smooth crossfade around the dark/light theme flip. i18n.js owns the
  // actual class toggle; this only wraps it with a temporary transition
  // window so colors don't hard-cut.
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var root = document.documentElement;
      root.classList.add('theme-transition');
      window.clearTimeout(themeBtn._animTimer);
      themeBtn._animTimer = window.setTimeout(function () {
        root.classList.remove('theme-transition');
      }, 400);
    });
  }

  // Give every <dialog> in the app (admin delete/bulk-delete confirm, and
  // any added later) a fade+scale-out on close to match the fade+scale-in
  // handled purely in CSS via @starting-style. Wrapping the prototype
  // method means individual pages don't need their own animation code -
  // they just keep calling dialog.close() as before.
  if (window.HTMLDialogElement) {
    var CLOSE_ANIM_MS = 160;
    var nativeClose = HTMLDialogElement.prototype.close;

    HTMLDialogElement.prototype.close = function (returnValue) {
      var dialog = this;
      if (!dialog.open || dialog.classList.contains('is-closing') || reducedMotion()) {
        return nativeClose.call(dialog, returnValue);
      }
      dialog.classList.add('is-closing');
      window.setTimeout(function () {
        dialog.classList.remove('is-closing');
        nativeClose.call(dialog, returnValue);
      }, CLOSE_ANIM_MS);
    };

    // Esc closes a <dialog> via the browser's own "cancel" handling rather
    // than the close() method above, which would otherwise skip the exit
    // animation. Intercept it and re-route through our wrapped close().
    document.addEventListener('cancel', function (e) {
      if (e.target instanceof HTMLDialogElement && e.target.open) {
        e.preventDefault();
        e.target.close();
      }
    }, true);
  }
})();
