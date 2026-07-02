// muse cockpit — service worker.
//
// Purpose: make the cockpit an installable PWA (a fetch handler is part of the
// browser's install criteria) and serve the app shell offline. It is
// deliberately conservative:
//
//   * The app shell is PRECACHED on install, so the cockpit works offline after
//     the very first visit (not only from the second visit onward).
//   * Navigation requests are network-first with an offline fallback to the
//     cached shell — a deep link or query-string URL still renders offline
//     instead of a browser error page.
//   * Static assets are stale-while-revalidate, but a response is only cached
//     when its Content-Type matches what the request asked for. The Vercel SPA
//     rewrite returns index.html (HTTP 200) for any missing path; without this
//     check the SW would cache that HTML under a script/style/image URL and
//     poison the cache. Such rewrite responses are served through but never
//     stored.
//   * Live/API paths (/v1/*, /api/*, streaming) are NEVER intercepted, so
//     gateway data and the public chat are always fresh.
//   * Cross-origin requests (e.g. a paired gateway on another host) pass through
//     untouched.
//
// Bumping CACHE invalidates the old shell cache on activate (also clears any
// junk a previous version cached under the SPA rewrite).
const CACHE = 'muse-cockpit-v2';

// The static app shell — enough to boot the cockpit and the atlas offline.
const SHELL = [
  './',
  'index.html',
  'manifest.webmanifest',
  'icon.svg',
  'vendor/react.production.min.js',
  'vendor/react-dom.production.min.js',
  'vendor/dc-runtime.js',
  'vendor/three.module.min.js',
  'vendor/three.core.min.js',
  'atlas/index.html',
  'atlas/style.css',
  'atlas/app.js',
  'atlas/architecture_data.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      // Cache each shell entry individually so one missing/renamed file cannot
      // fail the whole install (cache.addAll rejects atomically).
      await Promise.all(
        SHELL.map((url) =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => {
            /* skip entries that aren't present in this build */
          }),
        ),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
    })(),
  );
});

// Only cache real static assets in the stale-while-revalidate path. The Vercel
// SPA rewrite returns text/html (HTTP 200) for ANY missing path, so an HTML body
// here — for a script/style/image/font, or a programmatic fetch of a mistyped
// asset URL — is a masked miss and must never be stored. HTML documents are
// handled by the navigation branch, so the asset path never needs to cache HTML.
function isCacheableAsset(response) {
  if (!response || response.status !== 200 || response.type !== 'basic') return false;
  const type = (response.headers.get('Content-Type') || '').toLowerCase();
  return !type.includes('text/html');
}

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

  // Navigations: network-first, fall back to the cached shell so deep links and
  // query-string URLs still render offline instead of a browser error page.
  if (req.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          return await fetch(req);
        } catch (e) {
          const cache = await caches.open(CACHE);
          return (
            (await cache.match(req)) ||
            (await cache.match('index.html')) ||
            (await cache.match('./')) ||
            Response.error()
          );
        }
      })(),
    );
    return;
  }

  // Static assets: stale-while-revalidate, but only store type-matching responses.
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req);
      const network = fetch(req)
        .then((res) => {
          if (isCacheableAsset(res)) {
            cache.put(req, res.clone());
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
