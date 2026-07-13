(function () {
  const badge = document.getElementById('nav-cart-badge');
  if (!badge) return;

  window.updateCartBadge = function (count) {
    const n = Number(count) || 0;
    if (n > 0) {
      badge.textContent = String(n);
      badge.hidden = false;
    } else {
      badge.textContent = '';
      badge.hidden = true;
    }
    if (typeof window.refreshCartPanel === 'function') window.refreshCartPanel();
  };

  async function refreshBadge() {
    try {
      const res = await fetch('/api/cart', {
        headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' },
      });
      if (!res.ok) return;
      const data = await res.json();
      window.updateCartBadge(data.count);
    } catch (_) { /* ignore */ }
  }

  const initial = parseInt(badge.textContent, 10);
  if (!badge.hidden && initial > 0) {
    window.updateCartBadge(initial);
  } else {
    window.updateCartBadge(0);
    refreshBadge();
  }
})();
