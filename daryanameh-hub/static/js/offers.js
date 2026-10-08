/* دریانامه — offers.js: refresh the offers grid from the live sailing feed, visa from /data/visa.json. */
(async function () {
  const grid = document.getElementById('offersFull') || document.getElementById('offersHome'); if (!grid) return;
  const fa = n => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
  const cfg = await fetch('/data/offers.json').then(r => r.json()).catch(() => null);
  const visa = await fetch('/data/visa.json').then(r => r.json()).catch(() => null);
  const feedUrl = grid.dataset.feed || 'https://boutimar.ir/api/cruises.php';
  const classify = ports => { if (!visa) return 'unknown'; const p = ports || []; if (p.some(x => visa.hard.includes(x))) return 'hard'; if (p.some(x => visa.schengen.includes(x))) return 'schengen'; const real = p.filter(x => !/روز دریا|در دریا/.test(x)); if (real.length && real.every(x => visa.free.includes(x))) return 'free'; if (real.some(x => visa.easy.includes(x))) return 'easy'; return 'unknown'; };
  let rows; try { rows = await fetch(feedUrl, { mode: 'cors' }).then(r => r.ok ? r.json() : null); } catch (e) { rows = null; }
  if (!Array.isArray(rows)) return; // keep the build-time render; never invent
  const limit = +grid.dataset.limit || 8, book = grid.dataset.book || 'https://cruise24.ir/', label = grid.dataset.bookLabel || 'دیدن قیمت در کروز۲۴';
  const offers = rows.filter(s => s.priceFrom).sort((a, b) => a.priceFrom - b.priceFrom).slice(0, limit);
  if (!offers.length) return;
  grid.innerHTML = offers.map(o => { const lv = classify(o.ports), vl = visa ? visa.labels[lv] : ''; const dates = o.dates || []; return `<article class="offer"><p class="kicker">${o.line || ''} · ${o.ship || ''}</p><h3>${o.region || o.title || ''}</h3><p class="offer__ports">${(o.ports || []).slice(0, 5).join(' · ')}${(o.ports || []).length > 5 ? ' · …' : ''}</p><div class="offer__meta">${o.nights ? `<span>${fa(o.nights)} شب</span>` : ''}<span class="pill pill--${lv}">${vl}</span>${dates.length ? `<span>${fa(dates.length)} تاریخ؛ نزدیک‌ترین ${fa(dates[0])}</span>` : ''}</div><div class="offer__foot"><span class="price">از ${fa(o.priceFrom)} ${o.currency || 'EUR'}</span><a class="btn btn--sm" href="${book}" rel="sponsored noopener" target="_blank">${label}</a></div></article>`; }).join('');
  const st = document.getElementById('offersStatus'); if (st) st.textContent = 'منبع: فید زنده · ' + new Date().toLocaleDateString('fa-IR');
})();
