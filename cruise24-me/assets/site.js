/* AmbiMare — shared behaviour for every page. */

/* Resolve data-media / data-poster to local files from media/index.json (written by download_media.py).
   Falls back to the original URL when no index exists, so the page previews before download. */
(async function(){
  let index = {};
  try { const r = await fetch('media/index.json'); if (r.ok) index = await r.json(); } catch(e){}
  if (Object.keys(index).length) { const n = document.querySelector('.preview-note'); if (n) n.remove(); }
  const local = u => (u && index[u]) ? index[u] : u;
  const mobile = window.matchMedia('(max-width: 700px)').matches;
  document.querySelectorAll('[data-media]').forEach(el => {
    let u = el.dataset.media;
    if (mobile && el.dataset.mediaMobile) u = el.dataset.mediaMobile;
    const src = local(u);
    if (el.tagName === 'IMG') { el.addEventListener('error', () => el.classList.add('missing'), {once:true}); el.src = src; return; }
    if (el.dataset.poster) el.poster = local(el.dataset.poster);
    el.src = src; el.addEventListener('error', () => el.classList.add('missing'), {once:true});
    if (el.classList.contains('hero-video')) { el.addEventListener('canplay', () => el.classList.add('ready'), {once:true}); el.play().catch(()=>{}); }
  });
  // play non-hero videos only while visible
  const io = new IntersectionObserver(es => es.forEach(e => { const v = e.target; if (e.isIntersecting) v.play().catch(()=>{}); else v.pause(); }), {rootMargin:'200px'});
  document.querySelectorAll('video:not(.hero-video):not(.dest video):not(.region video)').forEach(v => io.observe(v));
  document.querySelectorAll('.dest, .region').forEach(d => { const v = d.querySelector('video'); if (!v) return; d.addEventListener('mouseenter', () => v.play().catch(()=>{})); d.addEventListener('mouseleave', () => v.pause()); });
})();

/* Nav: scrolled state, burger, close on tap. Same on every page. */
(function(){
  const nav = document.getElementById('nav'), burger = document.getElementById('burger');
  if (!nav || !burger) return;
  burger.addEventListener('click', () => burger.setAttribute('aria-expanded', nav.classList.toggle('open')));
  document.querySelectorAll('#menu a').forEach(a => a.addEventListener('click', () => nav.classList.remove('open')));
  const onScroll = () => nav.classList.toggle('scrolled', scrollY > 40); addEventListener('scroll', onScroll, {passive:true}); onScroll();
  const here = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('#menu a').forEach(a => { if ((a.getAttribute('href') || '').split('#')[0] === here) a.setAttribute('aria-current', 'page'); });
})();

/* Inner pages: soft reveal of rows and cards when GSAP is present; plain otherwise. */
(function(){
  if (document.body.dataset.page === 'home') return;
  const els = document.querySelectorAll('.post, .ship-row, .rlist li, .days li, .article, .region, .office, .hours > div');
  if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  gsap.registerPlugin(ScrollTrigger);
  els.forEach(el => gsap.fromTo(el, {opacity:0, y:14}, {opacity:1, y:0, duration:.7, ease:'power3.out', scrollTrigger:{trigger:el, start:'top 90%', once:true}}));
  const r = document.getElementById('route');
  if (r) gsap.to(r, {strokeDashoffset:0, ease:'none', scrollTrigger:{trigger:'.map', start:'top 85%', end:'center 55%', scrub:.5}});
})();

/* Contact page: arriving from a sailing page as contact.html#<sailing id>, name that
   sailing in the message so the planner knows what the question is about. */
(function(){
  if (document.body.dataset.page !== 'contact') return;
  var id = (location.hash || '').replace(/^#/, '');
  var box = document.querySelector('form.form textarea');
  if (!id || !box || box.value) return;
  fetch('data/journeys-index.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    var s = d && d.filter(function (x) { return x.id === id; })[0];
    if (!s || box.value) return;
    var dep = s.d ? ', departing ' + s.d : '';
    box.value = 'About: ' + s.t + ' (' + s.l + ', ' + s.s.join(' or ') + ', ' + s.n + ' nights' + dep + '). Ref ' + s.id + '.\n\n';
    box.focus();
  }).catch(function () {});
})();

/* Request forms: post to api/enquiry.php and say "thank you" only when the
   server confirms it stored the request. A failure is shown as a failure. */
(function(){
  document.querySelectorAll('form[data-enquiry]').forEach(function (form) {
    var note = form.querySelector('.note'), btn = form.querySelector('button[type=submit]');
    var idle = note ? note.textContent : '', label = btn ? btn.textContent : '';
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!form.reportValidity()) return;
      var data = new FormData(form);
      data.append('page', location.pathname);
      if (document.body.dataset.page === 'contact') data.append('sailing', (location.hash || '').replace(/^#/, ''));
      btn.disabled = true; btn.textContent = 'Sending…';
      note.classList.remove('ok', 'err'); note.textContent = idle;
      fetch(form.getAttribute('action'), { method: 'POST', body: data, headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, body: j }; }); })
        .then(function (res) {
          if (res.body && res.body.ok) {
            form.reset();
            note.classList.add('ok');
            note.textContent = 'Thank you. Your request has reached us, and a planner will reply within one working day.';
            btn.textContent = 'Sent';
            return;
          }
          var msg = res.status === 429 ? 'Too many requests from this connection. Please wait a few minutes and send it again.'
                  : res.status === 400 ? 'Please check your name and email address, then send it again.'
                  : 'Your request did not go through. Please try again in a moment.';
          throw { user: msg };
        })
        .catch(function (err) {
          note.classList.add('err');
          note.textContent = (err && err.user) || 'Your request did not go through. Please check your connection and try again.';
          btn.disabled = false; btn.textContent = label;
        });
    });
  });
})();
