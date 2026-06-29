// muse cockpit — minimal service worker.
//
// Purpose: make the cockpit an installable PWA (a fetch handler is part of the
// browser's install criteria) and serve the app shell offline. It is
// deliberately conservative:
//
//   * Only same-origin GET requests for the static shell are cached
//     (stale-while-revalidate from a versioned cache).
//   * Live/API paths (/v1/*, /api/*, anything streaming) are NEVER intercepted,
//     so gateway data and the public chat are always fresh.
//   * Cross-origin requests (e.g. a paired gateway on another host) pass through
//     untouched.
//
// Bumping CACHE invalidates the old shell cache on activate.
const CACHE = 'muse-cockpit-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never cache POST (chat, pairing, jobs)
  let url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) return; // leave the paired gateway alone
  // Live/API/stream paths must always hit the network — never serve them stale.
  if (
    url.pathname.startsWith('/v1/') ||
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/nexus/') ||
    url.pathname.includes('/stream')
  ) {
    return;
  }
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req);
      const network = fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === 'basic') cache.put(req, res.clone());
          return res;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
