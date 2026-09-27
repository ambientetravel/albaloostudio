/* Cruise24 journeys: filter, sort and page through every sailing on journeys.html.
   The first cards are plain HTML (crawlers, no-JS). With JS, the full list comes from
   data/journeys-index.json and is shown 24 at a time. The area and month choice travel in
   the hash as one token, "<area>.<month>" (e.g. #greece.2027-05). */
(function () {
  var grid = document.getElementById('jgrid');
  if (!grid) return;
  var PAGE = 24, shown = PAGE, all = null, list = [];
  var f = {
    area: document.getElementById('f-area'), month: document.getElementById('f-month'),
    line: document.getElementById('f-line'), nights: document.getElementById('f-nights'),
    sort: document.getElementById('f-sort')
  };
  var count = document.getElementById('fcount'), empty = document.getElementById('fempty'), more = document.getElementById('fmore');
  var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function euro(n) { return '€' + Number(n).toLocaleString('en-GB'); }
  function day(iso) { var p = iso.split('-'); return (+p[2]) + ' ' + MON[+p[1] - 1] + ' ' + p[0]; }
  function card(r) {
    var when = r.d ? 'Next departure ' + day(r.d) : 'Departure dates on request';
    var moreDates = r.dc > 1 ? ' · ' + r.dc + ' dates' : '';
    var price = r.p ? '<span class="jc-price">from <b>' + euro(r.p) + '</b><em>per person</em></span>'
                    : '<span class="jc-price"><b style="font-size:1rem">Fare on request</b></span>';
    return '<a class="jcard2" href="' + esc(r.u) + '">' +
      (r.i ? '<img src="' + esc(r.i) + '" alt="" loading="lazy">' : '<div class="noimg"></div>') +
      '<div class="jc-body"><small>' + esc(r.l) + ' · ' + esc(r.s.join(' or ')) + '</small><h3>' + esc(r.t) + '</h3>' +
      '<p class="jc-route">' + esc(r.r.join(' · ')) + '</p><div class="jc-chips">' +
      r.f.map(function (c) { return '<span class="chip">' + esc(c) + '</span>'; }).join('') + '</div>' +
      '<div class="jc-foot"><span>' + r.n + ' nights<br><em>' + esc(when) + moreDates + '</em></span>' + price + '</div></div></a>';
  }
  function readHash() {
    var t = (location.hash || '').replace(/^#/, '').split('.');
    var has = function (sel, v) { return [].some.call(sel.options, function (o) { return o.value === v; }); };
    if (t[0] && has(f.area, t[0])) f.area.value = t[0];
    if (t[1] && has(f.month, t[1])) f.month.value = t[1];
  }
  function writeHash() {
    var tok = (f.area.value || 'all') + '.' + (f.month.value || 'any');
    var want = tok === 'all.any' ? '' : '#' + tok;
    if (location.hash !== want) { try { history.replaceState(null, '', location.pathname + location.search + want); } catch (e) {} }
  }
  function filter() {
    var a = f.area.value, mo = f.month.value, ln = f.line.value, nr = f.nights.value, lo = 0, hi = 999;
    if (nr) { lo = +nr.split('-')[0]; hi = +nr.split('-')[1]; }
    list = all.filter(function (r) {
      return (!a || r.a.indexOf(a) > -1) &&
             (!mo || (mo === 'request' ? !r.m.length : r.m.indexOf(mo) > -1)) &&
             (!ln || r.k === ln) && r.n >= lo && r.n <= hi;
    });
    var key = f.sort.value, D = function (r) { return r.d || '9999'; }, P = function (r) { return r.p || 1e9; };
    list.sort(function (x, y) {
      if (key === 'price') return P(x) - P(y);
      if (key === 'date') return D(x) < D(y) ? -1 : D(x) > D(y) ? 1 : P(x) - P(y);
      return ((y.f.length ? 1 : 0) - (x.f.length ? 1 : 0)) || (D(x) < D(y) ? -1 : D(x) > D(y) ? 1 : P(x) - P(y));
    });
  }
  function render() {
    grid.innerHTML = list.slice(0, shown).map(card).join('');
    count.textContent = list.length + (list.length === 1 ? ' sailing' : ' sailings') + (list.length > shown ? ', showing ' + shown : '');
    empty.hidden = list.length > 0;
    more.hidden = list.length <= shown;
  }
  function apply() { if (!all) return; shown = PAGE; filter(); render(); writeHash(); }
  more.addEventListener('click', function () { shown += PAGE; render(); });
  Object.keys(f).forEach(function (k) { f[k].addEventListener('change', apply); });
  addEventListener('hashchange', function () { readHash(); apply(); });
  readHash();
  more.hidden = true;
  fetch(grid.dataset.index).then(function (r) { return r.json(); }).then(function (d) { all = d; apply(); })
    .catch(function () { more.hidden = true; count.textContent = 'Showing the first sailings. Reload to see them all.'; });
})();
