/* دریانامه service worker: shell precache, stale-while-revalidate pages, saved pages for offline reading. */
const VERSION_URL = '/precache.json'; let CACHE = 'dn-shell';
self.addEventListener('install', e => { e.waitUntil((async () => { const m = await fetch(VERSION_URL).then(r => r.json()).catch(() => null); if (m) { CACHE = 'dn-' + m.version; const c = await caches.open(CACHE); await Promise.allSettled(m.shell.map(u => c.add(u))); } self.skipWaiting(); })()); });
self.addEventListener('activate', e => { e.waitUntil((async () => { const keys = await caches.keys(); await Promise.all(keys.filter(k => k.startsWith('dn-') && k !== CACHE && k !== 'dn-saved').map(k => caches.delete(k))); self.clients.claim(); })()); });
self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return; const url = new URL(req.url);
  if (url.origin !== location.origin) return; // fonts, CDN, feed: network only
  e.respondWith((async () => {
    const saved = await caches.open('dn-saved'); const hit = await saved.match(req, { ignoreSearch: true }) || await caches.match(req, { ignoreSearch: true });
    const net = fetch(req).then(async r => { if (r.ok && (req.mode === 'navigate' || /\.(css|js|svg|json|png)$/.test(url.pathname))) { const c = await caches.open(CACHE); c.put(req, r.clone()); } return r; }).catch(() => null);
    if (hit) { net; return hit; }
    const r = await net; if (r) return r;
    if (req.mode === 'navigate') return (await caches.match('/offline/', { ignoreSearch: true })) || new Response('آفلاین', { status: 503 });
    return new Response('', { status: 504 });
  })());
});
