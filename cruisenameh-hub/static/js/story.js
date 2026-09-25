/* کروزنامه — story.js: the homepage, told by scroll.

   One loop, no library. Scroll sets a target; the hero camera eases toward it so a
   flick of the wheel reads as a camera move, not a jump cut. Every other section
   reports two numbers to CSS — how far into view it is, and how far through it the
   reader has travelled — and the stylesheet does the rest.

   Runs only when <html> carries .js-story (set in <head>, skipped for readers who ask
   for reduced motion). Without it every section rests in its finished state. */
(function () {
  const root = document.documentElement;
  if (!root.classList.contains('js-story')) return;
  window.__story = true;

  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
  const seg = (p, a, b) => clamp((p - a) / (b - a));
  const out = t => 1 - Math.pow(1 - t, 3);
  const io3 = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const lerp = (a, b, t) => a + (b - a) * t;
  let vw = innerWidth, vh = innerHeight;
  const nav = $('#nav');

  /* ═══ HERO — quay → hull → through the glass → balcony → cabin → the page ═══════
     Each scene is a still photograph moved by a virtual camera: a focus point in the
     picture (0–1 on each axis) and a zoom. The camera keeps the picture covering the
     frame at every aspect ratio, so the same move works on a phone held upright. */
  const hero = $('#hero');
  const CAM = {
    //        p     fx    fy    zoom
    quay:    [[0,   .50,  .58,  1.00], [.05, .50, .58, 1.02], [.19, .45, .34, 1.22], [.36, .36, .25, 2.7]],
    ship:    [[.29, .56,  .50,  1.06], [.60, .84, .81, 4.6]],
    balcony: [[.56, .14,  .50,  2.3],  [.79, .50, .52, 1.0]],
    cabin:   [[.74, .50,  .33,  1.55], [.93, .50, .52, 1.0]],
  };
  // opacity windows: [fade-in start, fade-in end, fade-out start, fade-out end]
  const SHOW = { quay: [-1, 0, .30, .37], ship: [.29, .36, .56, .60], balcony: [.565, .60, .75, .80], cabin: [.75, .80, 2, 3] };
  const BEAT = [[.13, .17, .25, .29], [.38, .42, .5, .54], [.62, .66, .72, .76]];
  const CH = [0, .31, .575, .77];

  let heroRun = null, heroResize = () => {};
  if (hero) {
    const frame = $('.hero__frame', hero), glass = $('.scene__glass', hero), credit = $('.scene__credit', hero);
    const a = $('.hero__copy--a', hero), b = $('.hero__copy--b', hero), bKids = $$('.hero__copy--b > *', hero);
    const beats = $$('.hero__beat', hero), chs = $$('.hero__chapters li', hero);
    const scenes = $$('.scene', hero).map(fig => ({ fig, id: fig.dataset.scene, img: fig.querySelector('img') }))
      .filter(s => CAM[s.id]);
    let sized = false;
    const size = () => {
      scenes.forEach(s => {
        const iw = s.img.naturalWidth || 1600, ih = s.img.naturalHeight || 900, k = Math.max(vw / iw, vh / ih);
        s.w = iw * k; s.h = ih * k; s.img.style.width = s.w + 'px'; s.img.style.height = s.h + 'px';
      });
      sized = true;
    };
    const camera = (s, p) => {
      const K = CAM[s.id]; let i = 0;
      while (i < K.length - 2 && p > K[i + 1][0]) i++;
      const [p0, x0, y0, z0] = K[i], [p1, x1, y1, z1] = K[Math.min(i + 1, K.length - 1)];
      const t = io3(p1 > p0 ? seg(p, p0, p1) : 1);
      const fx = lerp(x0, x1, t), fy = lerp(y0, y1, t), z = z0 * Math.pow(z1 / z0, t); // log-zoom: constant perceived speed
      const dw = s.w * z, dh = s.h * z;
      const tx = clamp(vw / 2 - fx * dw, vw - dw, 0), ty = clamp(vh / 2 - fy * dh, vh - dh, 0);
      s.img.style.transform = `translate3d(${tx.toFixed(1)}px,${ty.toFixed(1)}px,0) scale(${z.toFixed(4)})`;
    };
    const vis = (w, p) => seg(p, w[0], w[1]) * (1 - seg(p, w[2], w[3]));
    heroResize = () => { sized = false; };
    let chOn = -1, navOn = null;
    heroRun = p => {
      if (!sized) size();
      scenes.forEach(s => { const o = vis(SHOW[s.id], p); s.fig.style.opacity = o.toFixed(3); if (o > 0) camera(s, p); });
      // passing through the lit window: warm light blooms, then the room resolves behind it
      glass.style.opacity = (seg(p, .49, .575) * (1 - seg(p, .585, .67))).toFixed(3);
      const fa = seg(p, .045, .13); a.style.opacity = 1 - fa; a.style.transform = `translate3d(0,${(-40 * fa * fa).toFixed(1)}px,0)`;
      beats.forEach((el, i) => { const w = BEAT[i]; if (!w) return; const o = vis(w, p); el.style.opacity = o.toFixed(3); el.style.transform = `translate3d(0,${(18 * (1 - out(seg(p, w[0], w[1]))) - 18 * seg(p, w[2], w[3])).toFixed(1)}px,0)`; });
      let c = 0; CH.forEach((t, i) => { if (p >= t) c = i; });
      if (c !== chOn) { chs.forEach((li, i) => { li.classList.toggle('is-on', i === c); li.classList.toggle('is-past', i < c); }); chOn = c; }
      hero.style.setProperty('--hp', p.toFixed(4));
      // the page forms: the photograph settles into a framed card, the interface develops on it
      const f = out(seg(p, .86, 1));
      frame.style.clipPath = f > 0 ? `inset(${(f * 2.6).toFixed(2)}vh ${(f * 2.4).toFixed(2)}vw round ${(f * 26).toFixed(1)}px)` : '';
      const fb = seg(p, .84, .95); b.style.opacity = fb.toFixed(3); b.style.visibility = fb > 0 ? 'visible' : 'hidden';
      bKids.forEach((k, i) => { const t = out(seg(p, .845 + i * .024, .925 + i * .024)); k.style.opacity = t.toFixed(3); k.style.transform = `translate3d(0,${(22 * (1 - t)).toFixed(1)}px,0)`; });
      credit.style.opacity = (.55 * (1 - seg(p, .02, .08)) + .55 * seg(p, .9, 1)).toFixed(2);
      const n = p > .9; if (n !== navOn) { nav && nav.classList.toggle('is-hidden', !n); navOn = n; }
    };
    scenes.forEach(s => s.img.complete ? null : s.img.addEventListener('load', () => { sized = false; kick(); }, { once: true }));
  }

  /* ═══ SECTIONS ═════════════════════════════════════════════════════════════════
     --in  0→1 as the section's top travels from the bottom of the screen to 30% down.
     --p   0→1 across the whole passage (for pinned sections: across the pin).
     .st children get their own --t, staggered by data-i, so a grid arrives in order. */
  const secs = $$('[data-story]').map(el => ({
    el, kind: el.dataset.story, pin: el.hasAttribute('data-pin') || el.hasAttribute('data-hpin'),
    items: $$('.st', el).map(n => ({ n, i: +(n.dataset.i || 0), t: -1 })), on: false, last: {},
  }));
  const ob = new IntersectionObserver(es => es.forEach(e => { const s = secs.find(x => x.el === e.target); if (s) { s.on = e.isIntersecting; if (s.on) kick(); } }),
    { rootMargin: '30% 0px 30% 0px' });
  secs.forEach(s => ob.observe(s.el));
  const setv = (s, k, v) => { const r = v.toFixed(3); if (s.last[k] !== r) { s.el.style.setProperty(k, r); s.last[k] = r; } };

  /* voyage: the route draws itself port by port; the visa verdict is the story */
  const voyage = (() => {
    const el = $('#voyage'); if (!el) return null;
    const segs = $$('.vseg', el), stops = $$('.vstop', el), cards = $$('.vcard', el), dots = $$('.voyage__dots i', el), ship = $('.vship', el);
    const len = segs.map(pth => pth.getTotalLength());
    segs.forEach((pth, i) => { pth.style.strokeDasharray = `${len[i]} ${len[i]}`; pth.style.strokeDashoffset = len[i]; });
    let on = -1;
    return p => {
      const t = clamp(seg(p, .04, .9)) * segs.length;
      segs.forEach((pth, i) => { pth.style.strokeDashoffset = (len[i] * (1 - clamp(t - i))).toFixed(1); });
      const k = Math.min(segs.length - 1, Math.floor(t)), f = clamp(t - k), L = len[k] * f;
      const pt = segs[k].getPointAtLength(L), ah = segs[k].getPointAtLength(Math.min(len[k], L + 1)), bh = segs[k].getPointAtLength(Math.max(0, L - 1));
      let ang = Math.atan2(ah.y - bh.y, ah.x - bh.x) * 180 / Math.PI; if (ang > 90 || ang < -90) ang += 180; // keep the hull upright
      ship.setAttribute('transform', `translate(${pt.x.toFixed(1)} ${pt.y.toFixed(1)}) rotate(${ang.toFixed(1)})`);
      const stop = Math.min(stops.length - 1, Math.floor(t + .06));
      if (stop !== on) {
        stops.forEach((g, i) => { g.classList.toggle('is-on', i === stop); g.classList.toggle('is-past', i < stop); });
        cards.forEach((c, i) => { c.classList.toggle('is-on', i === stop); c.classList.toggle('is-past', i < stop); });
        dots.forEach((d, i) => d.classList.toggle('is-on', i <= stop));
        el.dataset.level = cards[stop] && cards[stop].querySelector('.vcard__route--schengen') ? 'schengen' : 'free';
        on = stop;
      }
    };
  })();

  /* ships: the rail is pinned and the page's vertical scroll slides it sideways */
  const hp = secs.find(s => s.kind === 'ships');
  const hpin = hp && (() => {
    const rail = $('[data-rail]', hp.el), bar = $('.hpin__bar span', hp.el); let over = 0, live = false;
    const size = () => {
      live = vw >= 760; hp.el.classList.toggle('hpin--live', live);
      rail.style.transform = ''; over = live ? Math.max(0, rail.scrollWidth - rail.clientWidth) : 0;
      hp.el.style.height = live && over ? `${vh + over + vh * .35}px` : '';
      if (!over) { live = false; hp.el.classList.remove('hpin--live'); }
    };
    size();
    return { size, run: p => { if (!live) return; rail.style.transform = `translate3d(${(over * out(p)).toFixed(1)}px,0,0)`; bar.style.transform = `scaleX(${p.toFixed(3)})`; } };
  })();

  const bar = $('.voyagebar span');
  const sections = () => {
    for (const s of secs) {
      if (!s.on) continue;
      const r = s.el.getBoundingClientRect();
      const inn = clamp((vh - r.top) / (vh * .7));
      const p = s.pin ? clamp(-r.top / Math.max(1, r.height - vh)) : clamp((vh - r.top) / (vh + r.height));
      setv(s, '--in', inn); setv(s, '--p', p);
      for (const it of s.items) {
        const q = it.n.getBoundingClientRect();
        const raw = s.kind === 'ships' && hpin && s.el.classList.contains('hpin--live') ? inn * 1.6 - (it.i % 6) * .14 : (vh * .97 - q.top) / (vh * .34) - (it.i % 4) * .16;
        const t = clamp(raw);
        if (Math.abs(t - it.t) > .002) { it.n.style.setProperty('--t', t.toFixed(3)); it.t = t; }
      }
      if (s.kind === 'voyage' && voyage) voyage(p);
      if (s.kind === 'ships' && hpin) hpin.run(p);
    }
    if (bar) { const max = document.documentElement.scrollHeight - vh; bar.style.transform = `scaleX(${clamp(scrollY / Math.max(1, max)).toFixed(4)})`; }
  };

  /* ═══ LOOP ═══════════════════════════════════════════════════════════════════ */
  let target = 0, cur = -1, raf = 0, solid = null;
  const frame = () => {
    raf = 0;
    if (hero && heroRun) {
      const max = hero.offsetHeight - vh; target = clamp(scrollY / Math.max(1, max));
      const past = scrollY > max + 10; if (past !== solid) { solid = past; nav && nav.classList.toggle('is-solid', past); }
      if (cur < 0 || Math.abs(target - cur) < .0005) cur = target; else cur += (target - cur) * .12;
      if (scrollY < max + vh) heroRun(cur);
      if (cur !== target) kick();
    }
    sections();
  };
  function kick() { if (!raf) raf = requestAnimationFrame(frame); }
  addEventListener('scroll', kick, { passive: true });
  addEventListener('resize', () => {
    vw = innerWidth; vh = innerHeight; heroResize(); cur = -1;
    hpin && hpin.size(); secs.forEach(s => (s.last = {})); kick();
  });
  nav && hero && nav.classList.add('is-hidden');
  kick();
})();
