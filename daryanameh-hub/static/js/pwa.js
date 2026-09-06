/* دریانامه — pwa.js: service worker registration, install prompt, save-for-offline, saved list. */
(function () {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/sw.js').catch(() => {});
  let deferred; addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e; if (!localStorage.getItem('dn-install-dismissed')) window.toast && toast('دریانامه را مثل یک اپ نصب کنید؛ راهنمای بندرها بدون اینترنت.', { label: 'نصب', fn: () => deferred.prompt() }); try { localStorage.setItem('dn-install-dismissed', '1'); } catch (_) {} });
  document.querySelectorAll('[data-save-offline]').forEach(btn => btn.addEventListener('click', async () => {
    btn.disabled = true; btn.textContent = 'در حال ذخیره…';
    try { const c = await caches.open('dn-saved'); await c.add(location.pathname); const saved = JSON.parse(localStorage.getItem('dn-saved') || '[]'); if (!saved.find(s => s.u === location.pathname)) { saved.push({ u: location.pathname, t: document.title }); localStorage.setItem('dn-saved', JSON.stringify(saved)); } btn.textContent = 'ذخیره شد؛ روی کشتی هم باز می‌شود'; } catch (e) { btn.textContent = 'ذخیره نشد'; btn.disabled = false; }
  }));
  const list = document.getElementById('savedList'); if (list) { try { JSON.parse(localStorage.getItem('dn-saved') || '[]').forEach(s => { const li = document.createElement('li'); li.innerHTML = `<a href="${s.u}"><strong>${s.t}</strong></a>`; list.appendChild(li); }); } catch (_) {} }
})();
