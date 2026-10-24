/*
 * HeyDrop feature capture — paste into Chrome DevTools Console while logged in at heydrop.app.
 *
 * What it records (only in YOUR browser, nothing is sent anywhere):
 *   • every screen you visit: path, title, headings, buttons, menu links, form fields
 *     (name / type / label / placeholder / required / select options), colours and fonts
 *   • every API call the app makes: method, path, status, and the SHAPE of request and
 *     response JSON (field names + types). Values are replaced with their type, so contact
 *     names/emails are NOT captured unless you turn that on (see below).
 *
 * What it never records: request/response headers, cookies, tokens, passwords.
 *
 * How to use:
 *   1. Open heydrop.app, log in, press F12 (Mac: Cmd+Option+J) → Console tab.
 *   2. If Chrome says "Don't paste code…", type:  allow pasting   and press Enter.
 *   3. Paste this whole file, press Enter. You'll see "HeyDrop capture ON".
 *   4. Click through EVERYTHING: dashboard, cards, card editor (open each tab), wallet,
 *      contacts/leads, a contact's detail, filters, export, team, settings, integrations,
 *      billing page, the public card page, the lead form.
 *   5. Type  HDX.download()  and press Enter. A file heydrop-capture-<date>.json downloads.
 *   6. Send that file to Claude (drop it into the albaloostudio repo or attach it).
 *
 * If a page fully reloads, the capture so far is kept — paste the script again to continue.
 * HDX.status() shows counts.  HDX.reset() clears it.
 * HDX.values(true) also keeps real values (only for your own test data — it will include PII).
 */
(function () {
  if (window.HDX && window.HDX.__on) { console.log('HeyDrop capture already running.', window.HDX.status()); return; }
  var KEY = 'hdx_capture_v1';
  var SECRET = /^pass$|password|passwd|token|secret|^auth$|authori[sz]ation|session|cookie|api[_-]?key|^otp|verifier|signature|card_?number|^cc_?num|cvc|cvv|iban/i;
  var keepValues = false;

  function load() { try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch (e) { return null; } }
  var S = load() || { started: new Date().toISOString(), origin: location.origin, screens: {}, api: {}, storageKeys: [], notes: [] };
  function persist() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { console.warn('HDX: storage full — run HDX.download() now.'); } }

  // Replace ids in paths so /contacts/8f3a…/edit and /contacts/91b2…/edit collapse into one endpoint.
  function normPath(u) {
    try { var x = new URL(u, location.href); } catch (e) { return String(u); }
    var path = x.pathname.replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, '/:uuid').replace(/\/[0-9a-f]{20,}/gi, '/:id').replace(/\/\d+(?=\/|$)/g, '/:n');
    var q = []; x.searchParams.forEach(function (v, k) { if (!SECRET.test(k)) q.push(k); });
    return (x.origin === location.origin ? '' : x.origin) + path + (q.length ? '?' + q.sort().join('&') : '');
  }

  function shape(v, depth) {
    depth = depth || 0;
    if (depth > 6) return '…';
    if (v === null) return 'null';
    if (Array.isArray(v)) return v.length ? [shape(v[0], depth + 1), '×' + v.length] : [];
    if (typeof v === 'object') {
      var o = {};
      Object.keys(v).slice(0, 80).forEach(function (k) { o[k] = SECRET.test(k) ? '[redacted]' : shape(v[k], depth + 1); });
      return o;
    }
    if (keepValues) return v;
    if (typeof v === 'string') {
      if (/^\S+@\S+\.\S+$/.test(v)) return 'string:email';
      if (/^https?:\/\//.test(v)) return 'string:url';
      if (/^\d{4}-\d\d-\d\dT/.test(v)) return 'string:datetime';
      if (/^#[0-9a-f]{3,8}$/i.test(v)) return 'string:color ' + v;   // colours are design, not PII
      if (/^\+?[\d\s()-]{7,}$/.test(v)) return 'string:phone';
      return 'string(' + v.length + ')';
    }
    return typeof v;
  }

  function parseBody(b) {
    if (!b) return null;
    if (typeof b === 'string') { try { return shape(JSON.parse(b)); } catch (e) { return 'text(' + b.length + ')'; } }
    if (b instanceof FormData) { var o = {}; b.forEach(function (v, k) { o[k] = v instanceof File ? 'file:' + v.type : (SECRET.test(k) ? '[redacted]' : shape(v)); }); return o; }
    if (b instanceof URLSearchParams) { var p = {}; b.forEach(function (v, k) { p[k] = SECRET.test(k) ? '[redacted]' : shape(v); }); return p; }
    return Object.prototype.toString.call(b);
  }

  function record(method, url, status, reqBody, resText, ctype) {
    var key = method.toUpperCase() + ' ' + normPath(url);
    var e = S.api[key] || (S.api[key] = { count: 0, statuses: {}, request: null, response: null, contentType: '', firstSeenOn: location.pathname });
    e.count++; e.statuses[status] = (e.statuses[status] || 0) + 1;
    if (reqBody && !e.request) e.request = reqBody;
    if (ctype) e.contentType = ctype.split(';')[0];
    if (resText && /json/.test(ctype || '') && !e.response) { try { e.response = shape(JSON.parse(resText)); } catch (x) {} }
    persist();
  }

  // fetch
  var ofetch = window.fetch;
  window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || String(input);
    var method = (init && init.method) || (input && input.method) || 'GET';
    var body = parseBody(init && init.body);
    return ofetch.apply(this, arguments).then(function (res) {
      try { var ct = res.headers.get('content-type') || ''; res.clone().text().then(function (t) { record(method, url, res.status, body, t, ct); }); } catch (e) {}
      return res;
    });
  };
  // XHR
  var oopen = XMLHttpRequest.prototype.open, osend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__hdx = { m: m, u: u }; return oopen.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (b) {
    var x = this, meta = x.__hdx || {}, body = parseBody(b);
    x.addEventListener('loadend', function () {
      var t = ''; try { t = (x.responseType === '' || x.responseType === 'text') ? x.responseText : (x.responseType === 'json' ? JSON.stringify(x.response) : ''); } catch (e) {}
      record(meta.m || 'GET', meta.u || '', x.status, body, t, x.getResponseHeader('content-type') || '');
    });
    return osend.apply(this, arguments);
  };

  function txt(el) { return (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120); }
  function uniq(a) { return a.filter(function (v, i) { return v && a.indexOf(v) === i; }); }
  function labelFor(el) {
    if (el.id) { var l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) return txt(l); }
    var p = el.closest('label'); if (p) return txt(p);
    return el.getAttribute('aria-label') || '';
  }

  function snapshot(reason) {
    var path = normPath(location.href);
    var root = document.querySelector('main') || document.body;
    var cs = getComputedStyle(document.body);
    var colors = {};
    Array.prototype.slice.call(document.querySelectorAll('button, a, h1, h2, header, nav, [class*="card"]'), 0, 200).forEach(function (el) {
      var s = getComputedStyle(el); [s.backgroundColor, s.color].forEach(function (c) { if (c && c !== 'rgba(0, 0, 0, 0)') colors[c] = (colors[c] || 0) + 1; });
    });
    var snap = {
      at: new Date().toISOString(), reason: reason, title: document.title,
      headings: uniq(Array.prototype.map.call(root.querySelectorAll('h1,h2,h3,h4'), txt)).slice(0, 60),
      buttons: uniq(Array.prototype.map.call(document.querySelectorAll('button,[role=button],input[type=submit]'), function (b) { return txt(b) || b.value || b.getAttribute('aria-label') || ''; })).slice(0, 120),
      links: uniq(Array.prototype.map.call(document.querySelectorAll('nav a, aside a, header a, [role=navigation] a, [role=tab]'), function (a) { return txt(a) + ' → ' + normPath(a.href || ''); })).slice(0, 120),
      tabs: uniq(Array.prototype.map.call(document.querySelectorAll('[role=tab]'), txt)),
      fields: Array.prototype.map.call(document.querySelectorAll('input, select, textarea'), function (f) {
        if (f.type === 'hidden') return null;
        return { tag: f.tagName.toLowerCase(), type: f.type || '', name: f.name || '', label: labelFor(f), placeholder: f.placeholder || '', required: !!f.required,
                 options: f.tagName === 'SELECT' ? Array.prototype.map.call(f.options, function (o) { return o.text; }).slice(0, 40) : undefined };
      }).filter(Boolean).slice(0, 150),
      tableHeaders: uniq(Array.prototype.map.call(document.querySelectorAll('th,[role=columnheader]'), txt)).slice(0, 60),
      fonts: uniq([cs.fontFamily].concat(Array.prototype.map.call(document.querySelectorAll('h1,h2,button'), function (e) { return getComputedStyle(e).fontFamily; }))).slice(0, 6),
      topColors: Object.keys(colors).sort(function (a, b) { return colors[b] - colors[a]; }).slice(0, 14),
      images: uniq(Array.prototype.map.call(document.querySelectorAll('img[alt], svg[aria-label]'), function (i) { return i.getAttribute('alt') || i.getAttribute('aria-label'); })).slice(0, 40)
    };
    var prev = S.screens[path];
    // Keep the richest snapshot of each screen (dialogs and tabs add fields after load).
    if (!prev || snap.fields.length + snap.buttons.length >= prev.fields.length + prev.buttons.length) S.screens[path] = snap;
    S.storageKeys = uniq(S.storageKeys.concat(Object.keys(localStorage).filter(function (k) { return k !== KEY; })));
    persist();
  }

  // SPA navigation + dialogs opening → re-snapshot (debounced).
  var timer;
  function soon(reason) { clearTimeout(timer); timer = setTimeout(function () { snapshot(reason); }, 1200); }
  ['pushState', 'replaceState'].forEach(function (fn) { var o = history[fn]; history[fn] = function () { var r = o.apply(this, arguments); soon(fn); return r; }; });
  window.addEventListener('popstate', function () { soon('popstate'); });
  new MutationObserver(function (m) { if (m.some(function (x) { return x.addedNodes.length; })) soon('dom'); }).observe(document.body, { childList: true, subtree: true });
  snapshot('start');

  window.HDX = {
    __on: true,
    status: function () { var s = { screens: Object.keys(S.screens).length, endpoints: Object.keys(S.api).length, since: S.started }; console.table(s); return s; },
    note: function (t) { S.notes.push({ at: location.pathname, text: String(t) }); persist(); return 'noted'; },
    values: function (on) { keepValues = !!on; return 'keep real values: ' + keepValues + (on ? ' — the file will contain personal data, share it carefully' : ''); },
    download: function () {
      snapshot('download');
      var out = JSON.stringify(Object.assign({ tool: 'heydrop-capture v1', userAgent: navigator.userAgent, keptValues: keepValues }, S), null, 2);
      var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([out], { type: 'application/json' }));
      a.download = 'heydrop-capture-' + new Date().toISOString().slice(0, 10) + '.json'; document.body.appendChild(a); a.click(); a.remove();
      return HDX.status();
    },
    reset: function () { localStorage.removeItem(KEY); S = { started: new Date().toISOString(), origin: location.origin, screens: {}, api: {}, storageKeys: [], notes: [] }; return 'cleared'; }
  };
  console.log('%cHeyDrop capture ON', 'background:#0b3954;color:#fff;padding:4px 8px;border-radius:4px',
    '— click through every screen, then run HDX.download(). Use HDX.note("…") to add a remark about the current screen.');
})();
