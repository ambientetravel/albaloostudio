/* Cruise24 journeys: filter and sort the sailing cards on journeys.html.
   Every card is plain HTML with data-* attributes, so the page reads fine without
   this script; this only hides and reorders. The choice travels in the URL hash as
   one token, "<area>.<month>" (e.g. #greece.2027-05), because a hash is the one part
   of the address that survives everywhere this page is shown. */
(function () {
  var grid = document.getElementById('jgrid');
  if (!grid) return;
  var cards = [].slice.call(grid.children);
  var f = {
    area: document.getElementById('f-area'), month: document.getElementById('f-month'),
    line: document.getElementById('f-line'), nights: document.getElementById('f-nights'),
    sort: document.getElementById('f-sort')
  };
  var count = document.getElementById('fcount'), empty = document.getElementById('fempty');

  function readHash() {
    var t = (location.hash || '').replace(/^#/, '').split('.');
    var has = function (sel, v) { return [].some.call(sel.options, function (o) { return o.value === v; }); };
    if (t[0] && has(f.area, t[0])) f.area.value = t[0];
    if (t[1] && has(f.month, t[1])) f.month.value = t[1];
  }
  function writeHash() {
    var tok = (f.area.value || 'all') + '.' + (f.month.value || 'any');
    var want = tok === 'all.any' ? '' : '#' + tok;
    if (location.hash !== want) {
      try { history.replaceState(null, '', location.pathname + location.search + want); } catch (e) {}
    }
  }
  function apply() {
    var a = f.area.value, mo = f.month.value, ln = f.line.value, nr = f.nights.value;
    var lo = 0, hi = 999;
    if (nr) { lo = +nr.split('-')[0]; hi = +nr.split('-')[1]; }
    var shown = 0;
    cards.forEach(function (c) {
      var d = c.dataset, n = +d.nights;
      var ok = (!a || (' ' + d.areas + ' ').indexOf(' ' + a + ' ') > -1) &&
               (!mo || (' ' + d.months + ' ').indexOf(' ' + mo + ' ') > -1) &&
               (!ln || d.line === ln) && n >= lo && n <= hi;
      c.hidden = !ok;
      if (ok) shown++;
    });
    var key = f.sort.value;
    cards.slice().sort(function (x, y) {
      var X = x.dataset, Y = y.dataset;
      if (key === 'price') return X.price - Y.price;
      if (key === 'date') return X.date < Y.date ? -1 : X.date > Y.date ? 1 : X.price - Y.price;
      return (Y.focus - X.focus) || (X.date < Y.date ? -1 : X.date > Y.date ? 1 : X.price - Y.price);
    }).forEach(function (c) { grid.appendChild(c); });
    count.textContent = shown + (shown === 1 ? ' sailing' : ' sailings');
    empty.hidden = shown > 0;
    writeHash();
  }
  readHash();
  Object.keys(f).forEach(function (k) { f[k].addEventListener('change', apply); });
  addEventListener('hashchange', function () { readHash(); apply(); });
  apply();
})();
