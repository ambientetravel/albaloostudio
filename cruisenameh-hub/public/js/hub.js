/* کروزنامه — hub.js: nav, reveals, did-you-know, filter, search. */
(function () {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const nav = $('#nav'), burger = $('#burger');
  burger && burger.addEventListener('click', () => { const o = nav.classList.toggle('is-open'); burger.setAttribute('aria-expanded', o); });

  /* ---------- hero ----------
     The homepage camera move and every scroll-told section live in story.js. If the
     reader has asked for reduced motion, or story.js never arrived, the page falls
     back to a still hero and plain sections: nothing waits on a script to be seen. */
  const hero = $('#hero'), root = document.documentElement;
  const still = () => { root.classList.remove('js-story'); hero && hero.classList.add('hero--static'); nav && nav.classList.add('is-solid'); };
  if (hero && !root.classList.contains('js-story')) still();
  else if (hero) addEventListener('load', () => { if (!window.__story) still(); });
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
  /* ---------- longform: reading bar, hero + figure parallax, reveals ---------- */
  const bar = $('#readingBar'), art = $('.lf__body');
  if (bar && art && !reduce) {
    const tick = () => {
      const top = art.offsetTop, h = art.offsetHeight - innerHeight;
      const p = h > 0 ? Math.min(1, Math.max(0, (scrollY - top) / h)) : 0;
      bar.style.width = (p * 100).toFixed(2) + '%';
    };
    addEventListener('scroll', tick, { passive: true }); addEventListener('resize', tick); tick();
  }
  const shots = [...$$('[data-hero] img'), ...$$('.figure[data-parallax] img')];
  if (shots.length && !reduce) {
    let raf = 0;
    const move = () => {
      raf = 0;
      shots.forEach(im => {
        const r = im.parentElement.getBoundingClientRect();
        if (r.bottom < -200 || r.top > innerHeight + 200) return;
        const mid = (r.top + r.height / 2 - innerHeight / 2) / innerHeight;
        im.style.transform = `translateY(${(-mid * 8).toFixed(2)}%)`;
      });
    };
    addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(move); }, { passive: true });
    addEventListener('resize', move); move();
  }
  const revealables = $$('[data-reveal]');
  if (revealables.length) {
    if (reduce || !('IntersectionObserver' in window)) revealables.forEach(el => el.classList.add('in'));
    else {
      const io = new IntersectionObserver((es) => es.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      }), { rootMargin: '0px 0px -8% 0px' });
      revealables.forEach(el => io.observe(el));
    }
  }

  window.hubNewsletter = f => { toast('ایمیل ثبت شد. تأیید عضویت را در صندوق ورودی ببینید.'); f.reset(); return false; };
  window.toast = (msg, action) => { const t = document.createElement('div'); t.className = 'toast'; t.innerHTML = `<span>${msg}</span>`; if (action) { const b = document.createElement('button'); b.textContent = action.label; b.onclick = () => { action.fn(); t.remove(); }; t.appendChild(b); } document.body.appendChild(t); setTimeout(() => t.remove(), 6000); };
})();
