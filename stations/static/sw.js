const STATIC_CACHE = 'naijafuel-static-v1';
const DYNAMIC_CACHE = 'naijafuel-dynamic-v1';

// 1. Static assets to cache immediately on install
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/app.js',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

// Install Event: Cache static files
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(urlsToCache))
  );
});

// Activate Event: Clean up old caches to save phone storage
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== STATIC_CACHE && key !== DYNAMIC_CACHE).map(key => caches.delete(key))
    ))
  );
});

// Fetch Event: The "Brain" of the caching strategy
self.addEventListener('fetch', event => {
  const url = event.request.url;

  // STRATEGY 1: Map Tiles (Cache First)
  // Map images are huge. If we have them in cache, use them. Don't waste data re-downloading.
  if (url.includes('tile.openstreetmap.org')) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        if (cachedResponse) return cachedResponse;
        return fetch(event.request).then(response => {
          return caches.open(DYNAMIC_CACHE).then(cache => {
            cache.put(event.request, response.clone());
            return response;
          });
        });
      })
    );
    return;
  }

  // STRATEGY 2: API Requests (Network First, Cache Fallback)
  // Try to get fresh data from the internet. If offline, show the last cached data.
  if (url.includes('/api/')) {
    event.respondWith(
      fetch(event.request).then(response => {
        return caches.open(DYNAMIC_CACHE).then(cache => {
          cache.put(event.request, response.clone());
          return response;
        });
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  // STRATEGY 3: Everything else (Network First)
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});