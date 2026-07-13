(function () {
  const wrap = document.getElementById('nav-notify-wrap');
  const btn = document.getElementById('nav-notify-btn');
  const panel = document.getElementById('notify-panel');
  const body = document.getElementById('notify-panel-body');
  const badge = document.getElementById('nav-notify-badge');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;

  if (!wrap || !btn || !panel || !body) return;

  let loaded = false;

  function t(key, fallback) {
    return (window.t && window.t(key)) || fallback;
  }

  function setBadge(count) {
    if (!badge) return;
    const previous = badge.hidden ? 0 : (parseInt(badge.textContent, 10) || 0);
    if (count > 0) {
      badge.textContent = String(count);
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
    if (count > previous) {
      badge.classList.remove('is-pulsing');
      // Force a reflow so re-adding the class restarts the animation even
      // if a previous pulse is still finishing.
      void badge.offsetWidth;
      badge.classList.add('is-pulsing');
    }
  }

  function iconForKind(kind) {
    if (kind === 'order_removed') return '✕';
    return '🔔';
  }

  function renderItem(note) {
    const li = document.createElement('li');
    li.className = 'notify-panel-item' + (note.unread ? ' notify-panel-item--unread' : '');
    li.dataset.id = note.id;

    const detailUrl = '/notifications#notification-' + note.id;
    li.innerHTML =
      '<a class="notify-panel-link" href="' + detailUrl + '">' +
        '<span class="notify-panel-icon notify-panel-icon--' + note.kind + '" aria-hidden="true">' + iconForKind(note.kind) + '</span>' +
        '<span class="notify-panel-content">' +
          '<span class="notify-panel-title">' + escapeHtml(note.title) + '</span>' +
          '<span class="notify-panel-message">' + escapeHtml(note.message) + '</span>' +
          '<span class="notify-panel-time">' + escapeHtml(note.time) + '</span>' +
        '</span>' +
        (note.unread ? '<span class="notify-panel-dot" aria-label="未讀"></span>' : '<span class="notify-panel-dot notify-panel-dot--read" aria-hidden="true"></span>') +
      '</a>' +
      '<button type="button" class="notify-panel-discard" data-id="' + note.id + '" aria-label="' + escapeHtml(t('notification_discard', '刪除')) + '">' +
        escapeHtml(t('notification_discard', '刪除')) +
      '</button>';

    li.querySelector('.notify-panel-discard')?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      deleteNotification(note.id, li);
    });

    return li;
  }

  function escapeHtml(text) {
    const el = document.createElement('span');
    el.textContent = text || '';
    return el.innerHTML;
  }

  function renderEmpty() {
    body.innerHTML = '<p class="notify-panel-empty">' + escapeHtml(t('notifications_empty', '目前沒有通知。')) + '</p>';
  }

  function renderList(notes) {
    if (!notes.length) {
      renderEmpty();
      return;
    }
    const ul = document.createElement('ul');
    ul.className = 'notify-panel-list';
    notes.forEach(note => ul.appendChild(renderItem(note)));
    body.innerHTML = '';
    body.appendChild(ul);
  }

  async function loadRecent() {
    body.innerHTML = '<p class="notify-panel-loading">' + escapeHtml(t('notifications_loading', '載入中…')) + '</p>';
    try {
      const res = await fetch('/api/notifications/recent', {
        headers: { 'X-CSRFToken': csrf || '' },
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      renderList(data.notifications || []);
      setBadge(data.unread_count || 0);
      loaded = true;
    } catch (err) {
      console.error(err);
      body.innerHTML = '<p class="notify-panel-empty">' + escapeHtml(t('notifications_load_error', '無法載入通知。')) + '</p>';
    }
  }

  async function deleteNotification(id, rowEl) {
    const msg = t('notification_delete_confirm', '確定要刪除此通知嗎？');
    if (!confirm(msg)) return;

    try {
      const res = await fetch('/notifications/delete/' + id, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf || '',
        },
      });
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      if (data.success) {
        rowEl?.remove();
        setBadge(data.unread_count || 0);
        if (!body.querySelector('.notify-panel-item')) renderEmpty();
      } else {
        alert(data.message || 'Delete failed');
      }
    } catch (err) {
      console.error(err);
      alert('Error deleting notification.');
    }
  }

  function openPanel() {
    panel.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    if (!loaded) loadRecent();
  }

  function closePanel() {
    panel.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
  }

  function togglePanel() {
    if (panel.classList.contains('is-open')) closePanel();
    else openPanel();
  }

  wrap.addEventListener('mouseenter', () => {
    openPanel();
  });

  wrap.addEventListener('mouseleave', () => {
    closePanel();
  });

  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) {
      closePanel();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePanel();
  });

  document.addEventListener('langchange', () => {
    if (panel.classList.contains('is-open') || wrap.matches(':hover')) {
      loaded = false;
      loadRecent();
    }
  });
})();
