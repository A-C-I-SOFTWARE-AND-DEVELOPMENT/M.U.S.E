// musehq.io service-worker MIGRATION kill-switch.
//
// The previous cockpit deployment installed a service worker at this same URL
// (/sw.js) that cached the old single-file shell (cockpit.dc.html). Returning
// PWA/offline visitors would otherwise keep being served that stale shell and
// never see the new OpenCode-layout cockpit. Browsers re-fetch /sw.js on
// navigation; because these bytes differ from the old worker, this one installs,
// deletes every cache the old worker created, unregisters itself, and — ONLY if
// it actually migrated something (there were old caches) — reloads controlled
// clients once so returning users land on fresh network content.
//
// The reload is gated on `deleted > 0`. A first-time visitor has no caches, so
// it never reloads (which would otherwise loop forever: reload → the page
// re-registers /sw.js → activate → reload → …). A returning user reloads exactly
// once: after that reload the caches are already gone, so the freshly-registered
// worker finds nothing to delete and retires silently.
self.addEventListener("install", () => self.skipWaiting())

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      let deleted = 0
      try {
        const keys = await caches.keys()
        await Promise.all(keys.map((k) => caches.delete(k)))
        deleted = keys.length
      } catch {
        /* ignore */
      }
      await self.clients.claim()
      if (deleted > 0) {
        const clients = await self.clients.matchAll({ type: "window" })
        for (const client of clients) client.navigate(client.url)
      }
      await self.registration.unregister()
    })(),
  )
})

// Never intercept fetches — always go to network.
