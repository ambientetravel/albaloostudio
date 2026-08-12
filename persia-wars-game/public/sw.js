/*
 * Offline shell.
 *
 * Navigations are NETWORK-FIRST, assets are cache-first. That split matters:
 * Vite fingerprints asset filenames, so a cached `index.html` from an older
 * build points at JavaScript that no longer exists on the server. Serving that
 * stale HTML gives every returning player a white screen until they clear their
 * site data — which is exactly what happened the first time a new build was
 * pushed to the test server.
 *
 * So: always try the network for the document, fall back to cache only when
 * genuinely offline. Hashed assets can be cached hard, because a new build
 * requests new filenames.
 */
const CACHE = 'persia-at-war-v2';

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(['./', './index.html'])).catch(() => {}));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;

  // The document: network first, so a fresh build is always picked up.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put('./index.html', copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match('./index.html').then((hit) => hit ?? Response.error())),
    );
    return;
  }

  // Everything else: cache first. Filenames are content-hashed.
  event.respondWith(
    caches.match(req).then(
      (hit) =>
        hit ??
        fetch(req)
          .then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
            return res;
          })
          .catch(() => Promise.reject(new Error('offline'))),
    ),
  );
});
