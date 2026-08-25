# -*- coding: utf-8 -*-
"""cruise24.ir page chrome, lifted from the live site rather than reinvented.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Every value here was read off https://cruise24.ir/msc.html on 26 Aug 2026. The
nav, the footer, the stylesheet query string and the legal line are copied
verbatim so a generated page is indistinguishable from a hand-written one. If
the live chrome changes, this file is what goes stale — _build.py --check
compares against the live header and says so rather than shipping a mismatch.
"""

CSS_VERSION = "style.css?v=3fb35d8c"

HEAD = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="https://cruise24.ir/{slug}">
<meta property="og:type" content="website">
<meta property="og:locale" content="fa_IR">
<meta property="og:site_name" content="کروز۲۴">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="https://cruise24.ir/{slug}">
<link rel="icon" href="img/logo.svg" type="image/svg+xml">
<link rel="preload" href="fonts/vazirmatn.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{css}">
{jsonld}
</head>
<body>
"""

HEADER = """<header class="nav">
  <div class="wrap nav__in">
    <a class="nav__logo" href="index.html"><img src="img/logo.svg" alt="" aria-hidden="true" width="20" height="20"><span class="latin">Cruise24</span></a>
    <nav class="nav__links">
      <a href="https://book.cruise24.ir/">جستجوی کروز</a>
      <a href="cruise-lines.html">خطوط کروز</a>
      <a href="index.html#types">انواع کروز</a>
      <a href="index.html#about">دربارهٔ ما</a>
    </nav>
    <div class="nav__end"><a class="btn nav__cta" href="index.html#request">درخواست کروز</a></div>
  </div>
</header>
"""

FOOTER = """<footer class="foot">
  <div class="wrap">
    <nav class="foot__links">
      <a href="index.html">خانه</a>
      <a href="cruise-lines.html">خطوط کروز</a>
      <a href="https://book.cruise24.ir/">جستجوی کروز</a>
      <a href="index.html#request">درخواست کروز</a>
      <a href="mailto:cruise@boutimar.com">تماس</a>
    </nav>
    <hr class="rule" style="margin-block:0 24px">
    <p class="foot__legal">
      قیمت‌ها به <span class="latin">EUR</span>، برای هر نفر، ارزان‌ترین کابینِ موجود، دو نفر در کابین. سرویس‌شارژ جداگانه از سوی خطِ کروز دریافت می‌شود.<br>
      کروز۲۴ یکی از شرکت‌های <a href="https://boutimar.ir" target="_blank" rel="noopener">گروه گردشگری بوتیمار</a> است.
    </p>
  </div>
</footer>
"""

# Everything between </footer> and </body> on a live page. The first version of
# this file stopped at </footer> and closed the document itself, which silently
# dropped BOTH scripts from all fifteen generated pages.
#
# nav.js is not decoration. Line 165 of it does `el('button','navburger')` — it
# CREATES the mobile menu button, which appears in no page's static markup. A
# page without this tag has no mobile navigation at all, on a Farsi site where
# mobile dominates. It also publishes window.CRUISE24_FLEET, the only written
# record of the fleet roster, read by the homepage stat and by the booking
# engine's ship filter. Keep the tag byte-identical rather than trimming it.
NAV_JS = '<script src="nav.js?v=59c1c9e6" defer></script>'

CLOSE = """
</body>
</html>
"""

# The live-count script the existing line pages already carry. msc.html,
# aroya.html, celestyal.html and explora.html are being REPLACED, so shipping
# them without this would be a regression: the figure would freeze at whatever
# the feed said on build day instead of tracking the booking engine.
#
# The static number stays in the markup and is what a reader sees if the fetch
# fails — the catch is deliberately empty for exactly that reason.
LIVE_COUNT = """<script>
/* Persian digits. boutimar.ir sets every figure this way and these pages sit
   beside it, so Latin numerals would read as a different site. Applied only to
   elements we fill ourselves — never to .latin, which holds brand names. */
(function () {
  var FA = ['\u06f0','\u06f1','\u06f2','\u06f3','\u06f4','\u06f5','\u06f6','\u06f7','\u06f8','\u06f9'];
  function fa(n) { return String(n).replace(/[0-9]/g, function (d) { return FA[+d]; }).replace(/,/g, '\u066c'); }
  var P = 'https://book.cruise24.ir/proxy.php';
  function live(params, key) {
    fetch(P + '?limit=1&lang=en' + (params ? '&' + params : ''), { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.meta) return;
        var el = document.querySelector('[data-live="' + key + '"]');
        if (el) el.textContent = fa(Number(j.meta.total).toLocaleString('en-GB'));
      })
      .catch(function () { /* the static fallback in the markup stands */ });
  }
  live('line=%(param)s', '%(key)s');

})();
</script>
"""
