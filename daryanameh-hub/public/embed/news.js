/* دریانامه — news column embed for partner sites.
 *
 * Attributed syndication, deliberately NOT the white-label offers widget: this one
 * carries the دریانامه name, because a wire item is worth nothing without whose fact
 * it is. Teasers only, every headline links home — the canonical copy stays on
 * daryanameh.com so search engines never have to choose between us and a partner.
 *
 *   <script src="https://daryanameh.com/embed/news.js" data-count="5"></script>
 *
 * Optional attributes: data-count (1-10, default 5), data-category, data-theme
 * ("light" | "dark"), data-title. No cookies, no tracking, no dependencies.
 */
(function () {
  var me = document.currentScript;
  if (!me) return;
  var ORIGIN = 'https://daryanameh.com';
  var n = Math.max(1, Math.min(10, parseInt(me.getAttribute('data-count') || '5', 10) || 5));
  var cat = me.getAttribute('data-category') || '';
  var dark = (me.getAttribute('data-theme') || '').toLowerCase() === 'dark';
  var heading = me.getAttribute('data-title') || 'اخبار کروز';

  var box = document.createElement('section');
  box.dir = 'rtl';
  box.lang = 'fa';
  box.style.cssText = 'font-family:Vazirmatn,system-ui,Tahoma,sans-serif;line-height:1.8;max-width:100%;' +
    'color:' + (dark ? '#f5f0e7' : '#141a24');
  me.parentNode.insertBefore(box, me);

  var esc = function (t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  var line = dark ? 'rgba(245,240,231,.18)' : 'rgba(20,26,36,.14)';
  var muted = dark ? 'rgba(245,240,231,.6)' : '#5b6473';

  fetch(ORIGIN + '/news/feed.json', { mode: 'cors' })
    .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
    .then(function (d) {
      var items = (d.items || []).filter(function (i) { return !cat || i.category === cat; }).slice(0, n);
      if (!items.length) { box.remove(); return; }
      box.innerHTML =
        '<h3 style="font-size:1rem;margin:0 0 .8rem;font-weight:600">' + esc(heading) + '</h3>' +
        '<ul style="list-style:none;margin:0;padding:0;border-top:1px solid ' + line + '">' +
        items.map(function (i) {
          return '<li style="border-bottom:1px solid ' + line + ';padding:.7rem 0">' +
            '<a href="' + esc(i.url) + '" target="_blank" rel="noopener" ' +
            'style="color:inherit;text-decoration:none;display:block">' +
            '<span style="display:block;font-size:.72rem;color:' + muted + '">' + esc(i.date) +
            (i.category ? ' · ' + esc(i.category) : '') + '</span>' +
            '<span style="display:block;font-weight:500;margin-top:.15rem">' + esc(i.title) + '</span>' +
            '</a></li>';
        }).join('') +
        '</ul>' +
        '<p style="margin:.7rem 0 0;font-size:.72rem;color:' + muted + '">' +
        '<a href="' + ORIGIN + '/news/" target="_blank" rel="noopener" style="color:inherit">' +
        'به نقل از دریانامه</a></p>';
    })
    .catch(function () { box.remove(); });
})();
