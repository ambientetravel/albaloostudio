/* TeamCards front-end: QR rendering + downloads, copy buttons, sheets on the public card,
   the link-block editor, slug check and bulk rows. No framework; qrcode.js is vendored. */
(function () {
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  /* ── QR ── */
  function make(text) { var q = qrcode(0, 'M'); q.addData(text, 'Byte'); q.make(); return q; }
  function svgFor(text, cell) { return make(text).createSvgTag({ cellSize: cell || 6, margin: 2, scalable: true }); }
  function pngFor(text, size, cb) {
    var q = make(text), n = q.getModuleCount(), margin = 4, px = Math.floor(size / (n + margin * 2));
    var c = document.createElement('canvas'); c.width = c.height = px * (n + margin * 2);
    var g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.fillStyle = '#000';
    for (var r = 0; r < n; r++) for (var k = 0; k < n; k++) if (q.isDark(r, k)) g.fillRect((k + margin) * px, (r + margin) * px, px, px);
    c.toBlob(cb, 'image/png');
  }
  function save(blob, name) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  if (window.qrcode) $$('[data-qr]').forEach(function (el) { el.innerHTML = svgFor(el.getAttribute('data-qr')); });

  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-dl-png],[data-dl-svg],[data-copy],[data-open],[data-close]'); if (!t) return;
    if (t.hasAttribute('data-copy')) {
      e.preventDefault();
      var v = t.getAttribute('data-copy'), old = t.textContent;
      (navigator.clipboard ? navigator.clipboard.writeText(v) : Promise.reject()).then(function () { t.textContent = 'Copied ✓'; }, function () { prompt('Copy this link:', v); })
        .then(function () { setTimeout(function () { t.textContent = old; }, 1500); });
      return;
    }
    if (t.hasAttribute('data-open')) { var d = document.getElementById(t.getAttribute('data-open')); if (d && d.showModal) d.showModal(); return; }
    if (t.hasAttribute('data-close')) { t.closest('dialog').close(); return; }
    e.preventDefault();
    var qr = t.closest('.tile').querySelector('[data-qr]'), url = qr.getAttribute('data-qr'), name = 'qr-' + (qr.getAttribute('data-name') || 'card');
    if (t.hasAttribute('data-dl-png')) pngFor(url, 1200, function (b) { save(b, name + '.png'); });
    else save(new Blob([svgFor(url, 10)], { type: 'image/svg+xml' }), name + '.svg');
  });

  /* ── public card sheets: open the exchange form on load when asked, close on backdrop tap ── */
  $$('dialog.sheet').forEach(function (d) {
    d.addEventListener('click', function (e) { if (e.target === d) d.close(); });
    if (d.getAttribute('data-autoopen') === '1' && d.showModal) setTimeout(function () { d.showModal(); }, 250);
  });

  /* ── link-block editor ── */
  var host = $('#blocks');
  if (host) {
    var TYPES = JSON.parse(host.getAttribute('data-types')), SOC = JSON.parse(host.getAttribute('data-socials'));
    var blocks = JSON.parse(host.getAttribute('data-blocks') || '[]');
    // PHP encodes an empty socials map as [], and named keys on an array are dropped by JSON.stringify.
    blocks.forEach(function (b) { if (b.type === 'socials' && (!b.socials || Array.isArray(b.socials))) b.socials = {}; });
    var SYSTEM = { exchange: 1, save: 1 };
    var dragFrom = null;

    function row(b, i) {
      var t = TYPES[b.type] || [b.type, '', ''], body = '';
      if (b.type === 'socials') {
        body = '<div class="socgrid">' + Object.keys(SOC).map(function (k) {
          return '<label>' + esc(SOC[k]) + '<input data-soc="' + k + '" value="' + esc((b.socials || {})[k]) + '" placeholder="' + (k === 'whatsapp' ? '+98…' : 'URL or @handle') + '"></label>';
        }).join('') + '</div>';
      } else if (b.type === 'text') {
        body = '<textarea data-f="value" rows="2" placeholder="Any text shown on the card">' + esc(b.value) + '</textarea>'
          + '<select data-f="style">' + ['heading', 'subheading', 'body'].map(function (s) { return '<option' + (b.style === s ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select>';
      } else {
        body = (SYSTEM[b.type] ? '' : '<input data-f="value" value="' + esc(b.value) + '" placeholder="' + esc(t[1]) + '">')
          + '<input data-f="label" value="' + esc(b.label) + '" placeholder="Button text, e.g. ' + esc(t[2]) + '">'
          + (b.type === 'exchange' ? '<label class="check"><input type="checkbox" data-f="auto_open"' + (b.auto_open ? ' checked' : '') + '> Open the form by itself when the card loads</label>' : '');
      }
      return '<div class="blkrow" draggable="true" data-i="' + i + '"><div class="blkhead"><span class="grip" title="Drag">⋮⋮</span><b>' + esc(t[0]) + '</b>'
        + '<label class="check"><input type="checkbox" data-f="show"' + (b.show ? ' checked' : '') + '> Show</label>'
        + '<span class="blkbtns"><button type="button" class="link" data-mv="-1">↑</button><button type="button" class="link" data-mv="1">↓</button>'
        + (SYSTEM[b.type] ? '' : '<button type="button" class="link danger" data-del>Remove</button>') + '</span></div>' + body + '</div>';
    }
    function render() { host.innerHTML = blocks.map(row).join(''); sync(); }
    function sync() { $('#blocks-json').value = JSON.stringify(blocks); }
    host.addEventListener('input', function (e) {
      var r = e.target.closest('.blkrow'); if (!r) return; var b = blocks[+r.getAttribute('data-i')];
      if (e.target.hasAttribute('data-soc')) { b.socials = b.socials || {}; b.socials[e.target.getAttribute('data-soc')] = e.target.value; }
      else { var f = e.target.getAttribute('data-f'); b[f] = e.target.type === 'checkbox' ? e.target.checked : e.target.value; }
      sync();
    });
    host.addEventListener('click', function (e) {
      var r = e.target.closest('.blkrow'); if (!r) return; var i = +r.getAttribute('data-i');
      if (e.target.hasAttribute('data-mv')) { var j = i + +e.target.getAttribute('data-mv'); if (j < 0 || j >= blocks.length) return; var x = blocks[i]; blocks[i] = blocks[j]; blocks[j] = x; render(); }
      if (e.target.hasAttribute('data-del')) { blocks.splice(i, 1); render(); }
    });
    host.addEventListener('dragstart', function (e) { var r = e.target.closest('.blkrow'); if (r) { dragFrom = +r.getAttribute('data-i'); r.classList.add('dragging'); } });
    host.addEventListener('dragover', function (e) { if (dragFrom !== null) e.preventDefault(); });
    host.addEventListener('drop', function (e) {
      e.preventDefault(); var r = e.target.closest('.blkrow'); if (!r || dragFrom === null) return;
      var to = +r.getAttribute('data-i'), moved = blocks.splice(dragFrom, 1)[0]; blocks.splice(to, 0, moved); dragFrom = null; render();
    });
    host.addEventListener('dragend', function () { dragFrom = null; $$('.dragging').forEach(function (r) { r.classList.remove('dragging'); }); });
    $('#addblock').addEventListener('click', function () {
      var t = $('#addtype').value;
      if (t === 'socials' && blocks.some(function (b) { return b.type === 'socials'; })) { alert('The card already has a social icons block.'); return; }
      blocks.push({ type: t, show: true, label: TYPES[t][2], value: '', style: 'body', socials: {} }); render();
      var last = host.lastElementChild; if (last) { last.scrollIntoView({ behavior: 'smooth', block: 'center' }); var inp = last.querySelector('input:not([type=checkbox]),textarea'); if (inp) inp.focus(); }
    });
    render();
  }

  /* ── card URL availability ── */
  var sc = $('#slugcheck');
  if (sc) sc.addEventListener('click', function () {
    var s = $('#slug'), msg = $('#slugmsg');
    fetch('index.php?p=slugcheck&s=' + encodeURIComponent(s.value) + '&id=' + s.getAttribute('data-id'), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (j) { s.value = j.slug; msg.textContent = j.free ? '✓ available: ' + j.url : '✗ taken — try another'; msg.className = j.free ? 'ok' : 'err'; });
  });

  /* ── bulk create: more rows ── */
  var ar = $('#addrow');
  if (ar) ar.addEventListener('click', function () {
    var tb = $('#bulkrows tbody') || $('#bulkrows'), n = $$('#bulkrows tr').length - 1, tr = document.createElement('tr');
    tr.innerHTML = ['name', 'email', 'mobile', 'title'].map(function (f) { return '<td><input name="rows[' + n + '][' + f + ']"' + (f === 'email' ? ' type="email"' : '') + '></td>'; }).join('')
      + '<td><input type="checkbox" name="rows[' + n + '][admin]" value="1"></td>';
    tb.appendChild(tr);
  });
})();
