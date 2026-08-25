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
</body>
</html>
"""
