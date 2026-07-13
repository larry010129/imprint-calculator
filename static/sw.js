const CACHE_NAME = 'diamond-calculator-static-v9';
const CORE_ASSETS = [
  '/static/favicon.svg',
  '/static/css/style.css?v=10',
  '/static/css/app-theme.css?v=15',
  '/static/css/animations.css?v=2',
  '/admin/static/css/admin-dashboard.css?v=16',
  '/static/js/i18n.js',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isNavigation = request.mode === 'navigate';
  const isApi = url.pathname.startsWith('/api/');
  if (isNavigation || isApi) {
    event.respondWith(fetch(request));
    return;
  }

  if (url.pathname.startsWith('/static/') || /\/static\//.test(url.pathname)) {
    const isCodeAsset = url.pathname.endsWith('.css') || url.pathname.endsWith('.js');
    if (isCodeAsset) {
      event.respondWith(
        fetch(request).then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        }).catch(() => caches.match(request))
      );
      return;
    }

    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
        }
        return response;
      }))
    );
  }
});
