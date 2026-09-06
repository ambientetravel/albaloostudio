/* دریانامه — hub.js: cinematic hero, nav, reveals, did-you-know, filter, search. */
(function () {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const nav = $('#nav'), burger = $('#burger');
  burger && burger.addEventListener('click', () => { const o = nav.classList.toggle('is-open'); burger.setAttribute('aria-expanded', o); });

  /* ---------- hero: Galataport -> hull -> balcony -> through the door -> cabin -> UI ----------
     Scroll-driven, no library. The section is 480vh tall; a sticky 100vh stage scrubs a
     keyframed timeline against scroll progress, damped so it reads like a camera move. */
  const hero = $('#hero');
  if (hero && !reduce) {
    const sticky = $('.hero__sticky', hero), scenes = $$('.scene', hero), imgs = scenes.map(s => s.querySelector('img'));
    const door = $('.scene__door', hero), a = $('.hero__copy--a', hero), b = $('.hero__copy--b', hero), bKids = $$('.hero__copy--b > *', hero);
    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v)), seg = (p, s, e) => clamp((p - s) / (e - s), 0, 1);
    const out = t => 1 - Math.pow(1 - t, 3), inn = t => t * t * t;
    nav.classList.add('is-hidden');
    let target = 0, cur = -1, raf = 0, solid = false;
    const render = p => {
      // 1. Galataport: push toward the moored ship, first copy dissolves.
      const s0 = seg(p, 0, .34);
      imgs[0].style.transform = `scale(${1.04 + .3 * s0}) translate(${-4 * s0}%, ${3 * s0}%)`;
      scenes[0].style.opacity = 1 - seg(p, .72, .75);
      const fa = seg(p, .08, .2); a.style.opacity = 1 - fa; a.style.transform = `translateY(${-30 * inn(fa)}px)`;
      // 2. The hull: cross-dissolve, keep pushing into the rows of balconies.
      scenes[1].style.opacity = seg(p, .2, .3) * (1 - seg(p, .58, .63));
      const s1 = seg(p, .2, .54); imgs[1].style.transform = `scale(${1.08 + .5 * s1}) translateY(${-6 * s1}%)`;
      // 3. The balcony: on the deck, the door frame ahead of us.
      scenes[2].style.opacity = seg(p, .54, .62) * (1 - seg(p, .8, .82));
      imgs[2].style.transform = `scale(${1.02 + .26 * out(seg(p, .54, .74))})`;
      // 4. Through the door: ink closes over the frame, then lifts on the cabin.
      door.style.opacity = seg(p, .68, .745) * (1 - seg(p, .76, .86));
      const s3 = out(seg(p, .745, .9)); scenes[3].style.opacity = s3; imgs[3].style.transform = `scale(${1.14 - .14 * s3})`;
      // 5. The interface develops inside the cabin.
      const fb = seg(p, .84, .94); b.style.opacity = fb; b.style.transform = `translateY(${24 * (1 - out(fb))}px)`;
      bKids.forEach((k, i) => { const t = out(seg(p, .85 + i * .022, .93 + i * .022)); k.style.opacity = t; k.style.transform = `translateY(${16 * (1 - t)}px)`; });
      p > .9 ? nav.classList.remove('is-hidden') : nav.classList.add('is-hidden');
    };
    const tick = () => { const max = hero.offsetHeight - innerHeight; target = clamp(scrollY / Math.max(1, max), 0, 1); const past = scrollY > max + 10; if (past !== solid) { solid = past; nav.classList.toggle('is-solid', past); } if (Math.abs(target - cur) > .0004) { cur = cur < 0 ? target : cur + (target - cur) * .14; render(cur); } raf = requestAnimationFrame(tick); };
    tick(); addEventListener('resize', () => { cur = -1; });
  } else if (hero) { hero.classList.add('hero--static'); nav && nav.classList.add('is-solid'); }
  if (!hero && nav) nav.classList.add('is-solid');

  /* ---------- reveals ---------- */
  const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && (e.target.classList.add('is-in'), io.unobserve(e.target))), { rootMargin: '0px 0px -8% 0px' });
  $$('.reveal').forEach(el => io.observe(el));

  /* ---------- did you know ---------- */
  const slider = $('#dyk-slider');
  if (slider) {
    const items = $$('.dyk__item', slider), dots = $('#dyk-dots'); let i = 0, t;
    items.forEach((_, n) => { const d = document.createElement('i'); n === 0 && d.classList.add('is-on'); d.addEventListener('click', () => go(n)); dots.appendChild(d); });
    const go = n => { items[i].classList.remove('is-on'); dots.children[i].classList.remove('is-on'); i = n % items.length; items[i].classList.add('is-on'); dots.children[i].classList.add('is-on'); clearInterval(t); t = setInterval(() => go(i + 1), 6000); };
    t = setInterval(() => go(i + 1), 6000);
  }

  /* ---------- listing filter ---------- */
  $$('[data-filter]').forEach(inp => { const list = $(inp.dataset.filter); inp.addEventListener('input', () => { const q = inp.value.trim().toLowerCase(); $$('[data-text]', list).forEach(el => el.hidden = q && !el.dataset.text.toLowerCase().includes(q)); }); });

  /* ---------- hero search over the sitemap of built pages ---------- */
  let idx = null;
  const loadIdx = () => idx || (idx = fetch('/data/search.json').then(r => r.json()).catch(() => []));
  const results = $('#searchResults'), input = $('.hero__search input');
  if (input) {
    input.addEventListener('input', async () => {
      const q = input.value.trim(); if (q.length < 2) { results.hidden = true; return; }
      const list = await loadIdx(); const hits = list.filter(p => (p.t + ' ' + (p.l || '') + ' ' + (p.k || '')).toLowerCase().includes(q.toLowerCase())).slice(0, 8);
      results.innerHTML = hits.map(h => `<a href="${h.u}">${h.t}<small>${h.c}</small></a>`).join('') || '<a>چیزی پیدا نشد</a>';
      results.hidden = false;
    });
    document.addEventListener('click', e => { if (!e.target.closest('.hero__search')) results.hidden = true; });
    window.hubSearch = f => { const q = f.q.value.trim(); if (!q) return false; loadIdx().then(l => { const h = l.find(p => (p.t + ' ' + (p.l || '')).toLowerCase().includes(q.toLowerCase())); location.href = h ? h.u : '/ports/'; }); return false; };
  }
  window.hubNewsletter = f => { toast('ایمیل ثبت شد. تأیید عضویت را در صندوق ورودی ببینید.'); f.reset(); return false; };
  window.toast = (msg, action) => { const t = document.createElement('div'); t.className = 'toast'; t.innerHTML = `<span>${msg}</span>`; if (action) { const b = document.createElement('button'); b.textContent = action.label; b.onclick = () => { action.fn(); t.remove(); }; t.appendChild(b); } document.body.appendChild(t); setTimeout(() => t.remove(), 6000); };
})();
