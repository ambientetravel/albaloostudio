/* TeamCards: render every [data-qr] with the vendored qrcode-generator, and the PNG/SVG downloads. */
(function () {
  function make(text) { var q = qrcode(0, 'M'); q.addData(text, 'Byte'); q.make(); return q; }

  function svgFor(text, cell) {
    return make(text).createSvgTag({ cellSize: cell || 6, margin: 2, scalable: true });
  }

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

  document.querySelectorAll('[data-qr]').forEach(function (el) { el.innerHTML = svgFor(el.getAttribute('data-qr')); });

  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-dl-png],[data-dl-svg]'); if (!t) return;
    e.preventDefault();
    var qr = t.closest('.tile').querySelector('[data-qr]'), url = qr.getAttribute('data-qr'), name = 'qr-' + (qr.getAttribute('data-name') || 'card');
    if (t.hasAttribute('data-dl-png')) pngFor(url, 1200, function (b) { save(b, name + '.png'); });
    else save(new Blob([svgFor(url, 10)], { type: 'image/svg+xml' }), name + '.svg');
  });
})();
