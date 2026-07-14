// Slide-in, auto-dismiss toasts. Server-rendered flash messages already
// live in #toast-container (see base.html); this wires their entrance,
// auto-dismiss timer, and manual close button. window.showToast() is also
// exposed so other scripts can raise a toast without a page reload.
(function () {
  var AUTO_DISMISS_MS = 5000;
  var EXIT_ANIM_MS = 250;

  function dismiss(toast) {
    if (!toast || toast.dataset.dismissing) return;
    toast.dataset.dismissing = '1';
    window.clearTimeout(toast._autoTimer);
    toast.classList.remove('is-visible');
    toast.classList.add('is-dismissing');
    window.setTimeout(function () {
      toast.remove();
    }, EXIT_ANIM_MS);
  }

  function wire(toast) {
    // Reveal on next frame so the transition from the CSS default (hidden)
    // state actually runs instead of snapping straight to visible.
    requestAnimationFrame(function () {
      toast.classList.add('is-visible');
    });
    toast._autoTimer = window.setTimeout(function () {
      dismiss(toast);
    }, AUTO_DISMISS_MS);

    var closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) closeBtn.addEventListener('click', function () { dismiss(toast); });
  }

  function init() {
    var container = document.getElementById('toast-container');
    if (!container) return;
    container.querySelectorAll('.toast').forEach(wire);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.showToast = function (message, category) {
    var container = document.getElementById('toast-container');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast--' + (category || 'message');
    toast.setAttribute('role', 'status');
    toast.innerHTML =
      '<span class="toast-message"></span>' +
      '<button type="button" class="toast-close" aria-label="關閉通知">&times;</button>';
    toast.querySelector('.toast-message').textContent = message;
    container.appendChild(toast);
    wire(toast);
    return toast;
  };
})();
